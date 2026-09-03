from __future__ import annotations

from typing import Any

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
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Discover separately loadable corpora inside a collection resource."""
        return service.list_members(
            resource_id,
            query=query,
            offset=offset,
            limit=limit,
        )

    @mcp.tool()
    def prepare_corpus(
        resource_id: str,
        member_id: str | None = None,
        version: str | None = None,
        modules: list[str] | None = None,
    ) -> dict[str, Any]:
        """Acquire/cache a corpus version and optional registered feature modules.

        For ordinary corpora, version selects a Text-Fabric dataset version such
        as '2021' or 'c'. Module values are Agora feature-module resource IDs
        associated with this corpus. The order is significant: when modules
        contain the same non-warp TF feature name, later selected modules take
        precedence, matching Text-Fabric module ordering.
        """
        kwargs: dict[str, Any] = {"member_id": member_id, "modules": modules}
        if version is not None:
            kwargs["version"] = version
        return service.prepare(resource_id, **kwargs)

    @mcp.tool()
    def load_corpus(
        resource_id: str,
        member_id: str | None = None,
        version: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
    ) -> dict[str, Any]:
        """Acquire and load a corpus version with optional registered feature modules."""
        kwargs: dict[str, Any] = {
            "member_id": member_id,
            "features": features,
            "modules": modules,
        }
        if version is not None:
            kwargs["version"] = version
        return service.load(resource_id, **kwargs)
