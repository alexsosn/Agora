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
        """List Agora's available Context-Fabric corpora and collections.

        Filters are optional. Use kind='collection' to discover collection
        resources whose member corpora are loaded independently.
        """
        return service.list_resources(
            query,
            language=language,
            discipline=discipline,
            kind=kind,
        )

    @mcp.tool()
    def describe_available_corpus(resource_id: str) -> dict[str, Any]:
        """Describe one available Agora corpus or collection resource."""
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
    ) -> dict[str, Any]:
        """Acquire/cache a corpus without loading it into Context-Fabric yet."""
        return service.prepare(resource_id, member_id=member_id)

    @mcp.tool()
    def load_corpus(
        resource_id: str,
        member_id: str | None = None,
        features: str | list[str] | None = None,
    ) -> dict[str, Any]:
        """Acquire and load a corpus into the running Context-Fabric MCP server."""
        return service.load(
            resource_id,
            member_id=member_id,
            features=features,
        )
