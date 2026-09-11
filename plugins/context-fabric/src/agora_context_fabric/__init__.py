"""Agora's Context-Fabric resource resolver and MCP integration."""

from .catalog import Catalog, ResourceSpec
from .resolver import (
    CollectionMember,
    ContextFabricResolver,
    PreparedCorpus,
    member_id_from_path,
    select_dataset_root,
)

# Keep the mature Git/cache implementation in gitstore while layering the
# prepare/load operation deadline in a small subclass. Rebinding the module
# export preserves the historical import path used by callers; existing
# resolver references only depend on the store interface and accept the subclass.
from . import gitstore as _gitstore_module
from .gitstore_long_ops import GitStore

_gitstore_module.GitStore = GitStore

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
    "GitStore",
    "member_id_from_path",
    "select_dataset_root",
]

del _gitstore_module
del _service_module
