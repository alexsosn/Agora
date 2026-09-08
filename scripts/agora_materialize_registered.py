#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host


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


def materialize_registered(
    *,
    plugin_id: str,
    materializer_id: str,
    output: Path,
    source: Path | None = None,
    sandbox: str = "required",
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    """Run one materializer from a verified, already-installed registry plugin."""
    manifest = resolve_installed_manifest(
        plugin_id,
        install_root=install_root,
        registry_path=registry_path,
    )
    return host.materialize(
        manifest_path=manifest,
        materializer_id=materializer_id,
        output=Path(output),
        source=None if source is None else Path(source),
        sandbox=sandbox,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run an already-installed Agora materializer by immutable registry plugin ID. "
            "This command never installs or repairs materializers."
        )
    )
    parser.add_argument("--plugin", required=True, help="registered materializer plugin id")
    parser.add_argument("--materializer", required=True, help="materializer id declared by the plugin")
    parser.add_argument("--output", required=True, type=Path, help="destination artifact directory")
    parser.add_argument("--source", type=Path, help="optional user-local source directory")
    parser.add_argument(
        "--install-root",
        type=Path,
        help="managed materializer installation root (defaults to Agora data home)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        help="materializer registry path (defaults to the canonical Agora registry)",
    )
    parser.add_argument(
        "--sandbox",
        choices=("required", "off"),
        default="required",
        help="require an OS sandbox (default); 'off' is an explicit development-only override",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = materialize_registered(
        plugin_id=args.plugin,
        materializer_id=args.materializer,
        output=args.output,
        source=args.source,
        sandbox=args.sandbox,
        install_root=args.install_root,
        registry_path=args.registry,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
