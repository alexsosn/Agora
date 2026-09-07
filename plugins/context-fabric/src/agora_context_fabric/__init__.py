"""Agora's Context-Fabric resource resolver and MCP integration."""

from .catalog import Catalog, ResourceSpec
from .resolver import (
    CollectionMember,
    ContextFabricResolver,
    PreparedCorpus,
    member_id_from_path,
    select_dataset_root,
)

# Keep the mature service/load lifecycle implementation in service.py while
# layering Agora-owned source-selection policy in a small subclass. Rebinding
# the module export preserves the historical import path used by callers.
from . import service as _service_module
from .service_source_modes import ContextFabricService

_service_module.ContextFabricService = ContextFabricService

__all__ = [
    "Catalog",
    "ResourceSpec",
    "CollectionMember",
    "ContextFabricResolver",
    "PreparedCorpus",
    "ContextFabricService",
    "member_id_from_path",
    "select_dataset_root",
]

del _service_module
