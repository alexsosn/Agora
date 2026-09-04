from __future__ import annotations

from typing import Any

from .resolver import PreparedCorpus
from .service import ContextFabricService


class ResolutionAwareContextFabricService(ContextFabricService):
    """Add source-resolution provenance to normal Context-Fabric tool results."""

    @staticmethod
    def _prepared_dict(
        prepared: PreparedCorpus,
        *,
        cache_residency: str,
    ) -> dict[str, Any]:
        result = ContextFabricService._prepared_dict(
            prepared,
            cache_residency=cache_residency,
        )
        result["source_revision_verified"] = prepared.source_revision_verified
        result["resolution"] = prepared.resolution
        for rendered, module in zip(result["modules"], prepared.modules, strict=True):
            rendered["source_revision_verified"] = module.source_revision_verified
            rendered["resolution"] = module.resolution
        return result
