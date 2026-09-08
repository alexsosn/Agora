#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from scripts import agora_install_materializer as installer


def resolve_installed_manifest(
    plugin_id: str,
    *,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    """Resolve an already-installed registered plugin to its verified manifest.

    This is intentionally read-only: it never fetches, installs, repairs, or
    executes packaging code. The current registry pin and runtime identity must
    already have a valid managed installation.
    """
    registry = (
        installer.load_registry()
        if registry_path is None
        else installer.load_registry(Path(registry_path))
    )
    try:
        plugin = installer.select_plugin(registry, plugin_id)
    except KeyError as exc:
        raise installer.MaterializerInstallError(
            f"unknown materializer plugin {plugin_id!r}"
        ) from exc

    root = installer.default_install_root() if install_root is None else Path(install_root)
    target = installer.installation_path(plugin, root)
    if not target.exists():
        raise installer.MaterializerInstallError(
            f"materializer plugin {plugin_id!r} is not installed for the current runtime; "
            f"install {plugin_id} explicitly before running it"
        )

    if not installer._environment_current(plugin, target):
        raise installer.MaterializerInstallError(
            f"materializer plugin {plugin_id!r} installation failed integrity verification; "
            "refusing to repair or reinstall it implicitly"
        )

    runtime = (target / "runtime").resolve()
    manifest = installer._contained(runtime, plugin["manifest"], "managed runtime manifest")
    if not manifest.is_file():
        raise installer.MaterializerInstallError(
            f"verified managed runtime manifest is missing for materializer plugin {plugin_id!r}"
        )
    return manifest.resolve()
