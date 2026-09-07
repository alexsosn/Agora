from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from . import service as _service_module
from .gitstore import GitStore, SourcePolicyState


_BaseContextFabricService = _service_module.ContextFabricService


class ContextFabricService(_BaseContextFabricService):
    """Source-policy-aware Context-Fabric service compatibility layer.

    The mature load/cache lifecycle remains in ``service.py``. This subclass
    scopes acquisition policy around those operations, pins collection work to
    the revision selected at the start of the operation, and adds provenance to
    the existing response shape without reimplementing load/compile semantics.
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

    def _resolve_collection_revision(
        self,
        resource,
        source_revision: str | None,
    ) -> str:
        _repo, revision = self.resolver._collection_repo(resource, source_revision)
        return revision

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
    ) -> dict[str, Any]:
        mode = self._validate_source_request(source_mode, source_revision)
        resource = self.catalog.get(resource_id)
        with self._source_context(mode) as policy:
            effective_revision = source_revision
            if self._managed_collection_resolution(resource):
                effective_revision = self._resolve_collection_revision(
                    resource,
                    source_revision,
                )
            result = _BaseContextFabricService.prepare(
                self,
                resource_id,
                member_id=member_id,
                version=version,
                source_revision=effective_revision,
                modules=modules,
            )
            return self._annotate_source_provenance(
                result,
                policy,
                resource_id=resource_id,
                explicit_revision=source_revision is not None,
            )

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
    ) -> dict[str, Any]:
        mode = self._validate_source_request(source_mode, source_revision)
        resource = self.catalog.get(resource_id)
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
            return self._annotate_source_provenance(
                result,
                policy,
                resource_id=resource_id,
                explicit_revision=source_revision is not None,
            )

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
        )
        compatible = dict(result)
        compatible["features"] = features
        return compatible
