from __future__ import annotations

import copy
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from . import service as _service_module
from .gitstore import GitStore, SourcePolicyState
from .load_safety import compile_budget_bytes, compile_timeout_seconds, source_tf_bytes
from .operation import OperationControl, current_operation, operation_scope


_BaseContextFabricService = _service_module.ContextFabricService


class ContextFabricService(_BaseContextFabricService):
    """Source-policy-aware Context-Fabric service compatibility layer.

    The mature load/cache lifecycle remains in ``service.py``. This subclass
    scopes acquisition policy around those operations, pins collection work to
    the revision selected at the start of the operation, and adds provenance,
    long-operation staging, and pre-execution disclosure without reimplementing
    load/compile semantics.
    """

    @staticmethod
    def _validate_source_request(
        source_mode: str | None,
        source_revision: str | None,
    ) -> str:
        mode = GitStore.validate_source_mode(source_mode)
        if source_revision is not None and mode == "require-fresh":
            raise ValueError(
                "source_revision and source_mode='require-fresh' are incompatible: "
                "an explicit immutable revision already fixes source identity"
            )
        return mode

    def _source_context(self, mode: str):
        if self.store is None:
            if mode != "prefer-fresh":
                raise RuntimeError(
                    f"source_mode={mode!r} requires the managed Context-Fabric Git cache"
                )
            return nullcontext(None)
        source_policy = getattr(self.store, "source_policy", None)
        if not callable(source_policy):
            if mode != "prefer-fresh":
                raise RuntimeError(
                    f"source_mode={mode!r} requires the managed Context-Fabric Git cache"
                )
            return nullcontext(None)
        return source_policy(mode)

    def _cache_transition_context(self):
        if self.store is None:
            return nullcontext()
        cache_transition = getattr(self.store, "cache_transition", None)
        if not callable(cache_transition):
            return nullcontext()
        return cache_transition()

    def _managed_collection_resolution(self, resource) -> bool:
        return (
            resource.kind == "collection"
            and self.store is not None
            and callable(getattr(self.resolver, "_collection_repo", None))
        )

    @staticmethod
    def _provenance(
        policy: SourcePolicyState | None,
        resource_id: str,
        *,
        explicit_revision: bool,
    ) -> dict[str, Any]:
        if explicit_revision:
            return {
                "source_resolution": "explicit-revision",
                "source_revision_verified": False,
            }
        if policy is None:
            return {}
        selection = policy.selections.get(resource_id)
        if selection is None:
            return {}
        return {
            "source_resolution": selection.source_resolution,
            "source_revision_verified": selection.source_revision_verified,
        }

    def _annotate_source_provenance(
        self,
        result: dict[str, Any],
        policy: SourcePolicyState | None,
        *,
        resource_id: str,
        explicit_revision: bool,
    ) -> dict[str, Any]:
        annotated = dict(result)
        annotated.update(
            self._provenance(
                policy,
                resource_id,
                explicit_revision=explicit_revision,
            )
        )
        modules = annotated.get("modules")
        if isinstance(modules, list) and policy is not None:
            annotated_modules: list[Any] = []
            for module in modules:
                if not isinstance(module, dict):
                    annotated_modules.append(module)
                    continue
                item = dict(module)
                module_id = item.get("id")
                if isinstance(module_id, str):
                    item.update(
                        self._provenance(
                            policy,
                            module_id,
                            explicit_revision=False,
                        )
                    )
                annotated_modules.append(item)
            annotated["modules"] = annotated_modules
        return annotated

    def _module_load_preflight(
        self,
        result: dict[str, Any],
        resource,
    ) -> dict[str, Any] | None:
        modules = result.get("modules")
        if not isinstance(modules, list) or not modules:
            return None

        path = Path(str(result["path"]))
        source_bytes = source_tf_bytes(path)
        managed_compile = self.cold_compiler is not None and self.cfm_version is not None
        warm = self._is_warm(path) if managed_compile else None
        module_order = [
            str(module["id"])
            for module in modules
            if isinstance(module, dict) and isinstance(module.get("id"), str)
        ]
        return {
            "cache_kind": "overlay",
            "module_order": module_order,
            # Feature files are overlaid in caller order. If two modules expose
            # the same filename, the later module replaces the earlier one.
            "module_order_semantics": "ordered-last-wins",
            # This is a point-in-time observation. load_corpus rechecks the
            # marker under the exact-object compile lock before compiling.
            "exact_combination_warm": warm,
            "full_compile_required": (not warm) if warm is not None else None,
            "cfm_version": self.cfm_version,
            "source_bytes": source_bytes,
            # These are the server defaults. Explicit load_corpus overrides may
            # choose stricter per-load values without changing the host reserve.
            "compile_budget_bytes": compile_budget_bytes(source_bytes),
            "compile_timeout_seconds": compile_timeout_seconds(),
            "min_free_bytes": (
                int(getattr(self.store, "min_free_bytes", 0))
                if self.store is not None
                else None
            ),
            # Small annotation modules still compose a complete TF source tree,
            # so a cold exact combination can require a parent-scale compile.
            "cost_expectation": "parent-scale-possible",
            "parent_historical_load_cost": (
                copy.deepcopy(resource.load_cost) if resource.load_cost else None
            ),
        }

    def _resolve_collection_revision(
        self,
        resource,
        source_revision: str | None,
    ) -> str:
        _repo, revision = self.resolver._collection_repo(resource, source_revision)
        return revision

    def _reserve_active_load(self, prepared, **kwargs):
        load_id, cancel_event = super()._reserve_active_load(prepared, **kwargs)
        operation = current_operation()
        if operation is None:
            return load_id, cancel_event

        # Base service owns active-load bookkeeping. Swap only the event before
        # the compiler receives it so protocol cancellation and cancel_load use
        # the same cooperative token rather than two unrelated cancellation paths.
        with self._active_loads_lock:
            record = self._active_loads.get(load_id)
            if record is not None:
                record["cancel_event"] = operation.cancel_event
        operation.stage("loading/compiling")
        return load_id, operation.cancel_event

    def _parent_warm_load(self, prepared, new_lease, *, features):
        operation = current_operation()
        if operation is not None:
            operation.raise_if_cancelled()
            operation.stage("loading/compiling")
        return super()._parent_warm_load(
            prepared,
            new_lease,
            features=features,
        )

    def list_members(
        self,
        resource_id: str,
        *,
        query: str = "",
        source_revision: str | None = None,
        source_mode: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        # Preserve the historical validation-before-resolution contract.
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if limit > 100:
            raise ValueError("limit must be <= 100")
        mode = self._validate_source_request(source_mode, source_revision)
        resource = self.catalog.get(resource_id)
        with self._source_context(mode) as policy:
            effective_revision = source_revision
            if self._managed_collection_resolution(resource):
                effective_revision = self._resolve_collection_revision(
                    resource,
                    source_revision,
                )
            result = _BaseContextFabricService.list_members(
                self,
                resource_id,
                query=query,
                source_revision=effective_revision,
                offset=offset,
                limit=limit,
            )
            return self._annotate_source_provenance(
                result,
                policy,
                resource_id=resource_id,
                explicit_revision=source_revision is not None,
            )

    def list_collection_members(
        self,
        resource_id: str,
        *,
        query: str = "",
        source_revision: str | None = None,
        source_mode: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        result = self.list_members(
            resource_id,
            query=query,
            source_revision=source_revision,
            source_mode=source_mode,
            offset=offset,
            limit=limit,
        )
        compatible = dict(result)
        compatible["items"] = compatible.pop("members")
        return compatible

    def prepare(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        source_mode: str | None = None,
        modules: list[str] | None = None,
        operation: OperationControl | None = None,
    ) -> dict[str, Any]:
        if operation is not None:
            operation.stage("resolving")
        with operation_scope(operation):
            mode = self._validate_source_request(source_mode, source_revision)
            resource = self.catalog.get(resource_id)
            if operation is not None:
                operation.raise_if_cancelled()
                operation.stage("acquiring/materializing")
            with self._source_context(mode) as policy:
                effective_revision = source_revision
                if self._managed_collection_resolution(resource):
                    effective_revision = self._resolve_collection_revision(
                        resource,
                        source_revision,
                    )
                # Resolver preparation already uses a shared transition while it
                # creates/touches snapshots and overlays. Keep one outer shared
                # transition through the user-visible preflight projection as well,
                # so an exclusive prune cannot detach the returned overlay between
                # preparation and source/warm-state measurement.
                with self._cache_transition_context():
                    result = _BaseContextFabricService.prepare(
                        self,
                        resource_id,
                        member_id=member_id,
                        version=version,
                        source_revision=effective_revision,
                        modules=modules,
                    )
                    if operation is not None:
                        operation.raise_if_cancelled()
                    annotated = self._annotate_source_provenance(
                        result,
                        policy,
                        resource_id=resource_id,
                        explicit_revision=source_revision is not None,
                    )
                    preflight = self._module_load_preflight(annotated, resource)
                    if preflight is not None:
                        annotated["load_preflight"] = preflight
                    if operation is not None:
                        operation.stage("ready")
                    return annotated

    def load(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        source_mode: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
        max_compile_gb: float | None = None,
        max_compile_minutes: float | None = None,
        operation: OperationControl | None = None,
    ) -> dict[str, Any]:
        if operation is not None:
            operation.stage("resolving")
        with operation_scope(operation):
            mode = self._validate_source_request(source_mode, source_revision)
            resource = self.catalog.get(resource_id)
            if operation is not None:
                operation.raise_if_cancelled()
                operation.stage("acquiring/materializing")
            with self._source_context(mode) as policy:
                effective_revision = source_revision
                if self._managed_collection_resolution(resource):
                    effective_revision = self._resolve_collection_revision(
                        resource,
                        source_revision,
                    )
                result = _BaseContextFabricService.load(
                    self,
                    resource_id,
                    member_id=member_id,
                    version=version,
                    source_revision=effective_revision,
                    features=features,
                    modules=modules,
                    max_compile_gb=max_compile_gb,
                    max_compile_minutes=max_compile_minutes,
                )
                annotated = self._annotate_source_provenance(
                    result,
                    policy,
                    resource_id=resource_id,
                    explicit_revision=source_revision is not None,
                )
                if operation is not None:
                    # Final upstream warm load is not forcibly interruptible, but
                    # no request reports ready until that synchronous call returns.
                    operation.stage("ready")
                return annotated

    def load_resource(
        self,
        resource_id: str,
        *,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        source_mode: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
        max_compile_gb: float | None = None,
        max_compile_minutes: float | None = None,
        operation: OperationControl | None = None,
    ) -> dict[str, Any]:
        result = self.load(
            resource_id,
            member_id=member_id,
            version=version,
            source_revision=source_revision,
            source_mode=source_mode,
            features=features,
            modules=modules,
            max_compile_gb=max_compile_gb,
            max_compile_minutes=max_compile_minutes,
            operation=operation,
        )
        compatible = dict(result)
        compatible["features"] = features
        return compatible
