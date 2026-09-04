from __future__ import annotations

from typing import Any

from .gitstore import GIB
from .network import use_network_mode
from .service import ContextFabricService


def register_tools(mcp: Any, service: ContextFabricService) -> None:
    """Register Agora resource-management tools on a FastMCP-compatible server."""

    @mcp.tool()
    def list_available_corpora(
        query: str = "",
        language: str | None = None,
        discipline: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        """List Agora's directly loadable Context-Fabric corpora and collections.

        By default feature modules are excluded so every returned item can be
        passed to prepare_corpus/load_corpus. Use kind='feature-module' to
        discover optional modules explicitly. Parent corpus descriptions expose
        modules compatible with the default selected version and all registered
        modules with their compatible parent versions.
        """
        return service.list_resources(
            query,
            language=language,
            discipline=discipline,
            kind=kind,
        )

    @mcp.tool()
    def describe_available_corpus(resource_id: str) -> dict[str, Any]:
        """Describe one available Agora corpus, collection, or feature module."""
        return service.describe_resource(resource_id)

    @mcp.tool()
    def list_collection_members(
        resource_id: str,
        query: str = "",
        source_revision: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Discover separately loadable corpora inside one collection snapshot.

        The response contains the immutable `source_revision` used for discovery.
        Pass it back for later pages and then to prepare_corpus/load_corpus to
        keep the entire workflow on the same upstream collection revision. If it
        is omitted, discovery follows the collection's current configured state.
        """
        kwargs: dict[str, Any] = {
            "query": query,
            "offset": offset,
            "limit": limit,
        }
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        return service.list_members(resource_id, **kwargs)

    @mcp.tool()
    def prepare_corpus(
        resource_id: str,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        modules: list[str] | None = None,
        network_mode: str = "auto",
    ) -> dict[str, Any]:
        """Acquire/cache a corpus version and optional registered feature modules.

        `network_mode` controls source resolution: `auto` refreshes upstream and
        falls back only for connectivity failures when the exact materialized
        snapshot is already cached; `offline` performs no Git network operation;
        `require-fresh` refuses stale fallback. The result reports `resolution`
        and `source_revision_verified`.

        For collection members, pass the `source_revision` returned by
        list_collection_members to resolve the member at exactly that cached
        upstream commit. Omitting it preserves floating/current collection
        behavior. Prepared paths are cache-resident but evictable after this call
        returns; use load_corpus when a corpus must stay protected for active use.
        """
        kwargs: dict[str, Any] = {"member_id": member_id, "modules": modules}
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        with use_network_mode(network_mode):
            return service.prepare(resource_id, **kwargs)

    @mcp.tool()
    def load_corpus(
        resource_id: str,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
        network_mode: str = "auto",
    ) -> dict[str, Any]:
        """Acquire and load a corpus; its final cache path is leased until unload.

        `network_mode` has the same `auto`/`offline`/`require-fresh` semantics as
        prepare_corpus. Cached fallback is explicit in the returned `resolution`
        and `source_revision_verified` fields.

        For a collection member, reuse the discovery `source_revision` to load
        exactly that cached collection snapshot. The response includes
        `logical_name`; pass that value to unload_corpus. Module-enabled loads
        lease the composed overlay, not every source input.
        """
        kwargs: dict[str, Any] = {
            "member_id": member_id,
            "features": features,
            "modules": modules,
        }
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        with use_network_mode(network_mode):
            return service.load(resource_id, **kwargs)

    @mcp.tool()
    def unload_corpus(logical_name: str) -> dict[str, Any]:
        """Unload an Agora-loaded corpus and release its cache lease.

        Use the exact `logical_name` returned by load_corpus. Repeating unload is
        safe and reports `was_loaded=false` when nothing remains loaded.
        """
        return service.unload(logical_name)

    @mcp.tool()
    def corpus_cache_status() -> dict[str, Any]:
        """Report Context-Fabric cache usage, object kinds, limits, and active leases."""
        return service.cache_status()

    @mcp.tool()
    def prune_corpus_cache(target_gb: float | None = None) -> dict[str, Any]:
        """LRU-prune unused Context-Fabric cache objects.

        `target_gb` is a soft logical cache-size target. Active objects are never
        forced out; the result explicitly reports whether the requested target
        and free-space guardrail were achieved.
        """
        if target_gb is not None and target_gb < 0:
            raise ValueError("target_gb must be >= 0")
        target_bytes = None if target_gb is None else int(target_gb * GIB)
        return service.prune_cache(target_bytes=target_bytes)

    @mcp.tool()
    def remove_cached_corpus(
        resource_id: str,
        member_id: str | None = None,
        source_revision: str | None = None,
    ) -> dict[str, Any]:
        """Remove matching unused cache objects for a registered resource.

        For corpus resources this includes unused derived overlays. Active
        matches are skipped and reported. `source_revision` filters source
        snapshots and overlays by the parent corpus revision.
        """
        return service.remove_cached(
            resource_id,
            member_id=member_id,
            source_revision=source_revision,
        )
