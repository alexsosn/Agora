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


def _registered_target(
    plugin_id: str,
    *,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> tuple[dict, Path]:
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
    return plugin, installer.installation_path(plugin, root)


def _not_installed(plugin_id: str) -> installer.MaterializerInstallError:
    return installer.MaterializerInstallError(
        f"materializer plugin {plugin_id!r} is not installed for the current runtime; "
        f"install {plugin_id} explicitly before running it"
    )


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
    plugin, target = _registered_target(
        plugin_id,
        install_root=install_root,
        registry_path=registry_path,
    )
    if not target.exists():
        raise _not_installed(plugin_id)

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


def resolve_cacheability_authorization(
    plugin_id: str,
    materializer_id: str,
    *,
    install_root: Path | None = None,
    registry_path: Path | None = None,
) -> dict:
    """Return cacheability policy for the verified installed execution identity.

    This is an authorization read, not an installation path. It never fetches,
    installs, repairs, imports, or executes plugin code. The installer runtime
    lock is held while the managed environment is re-verified, the current
    registry/manifest binding is checked, and the execution identity from that
    exact verified receipt snapshot is compared with reviewed cacheability
    policy.
    """
    plugin, target = _registered_target(
        plugin_id,
        install_root=install_root,
        registry_path=registry_path,
    )
    if not target.exists():
        raise _not_installed(plugin_id)

    lock_path = target.parent / f".{target.name}.lock"
    with installer._lock(lock_path):
        receipt = installer._verified_environment_receipt(plugin, target)
        if receipt is None:
            raise installer.MaterializerInstallError(
                f"materializer plugin {plugin_id!r} installation failed integrity verification; "
                "refusing to authorize cache reuse"
            )

        runtime = (target / "runtime").resolve()
        manifest = installer._contained(runtime, plugin["manifest"], "managed runtime manifest")
        if not manifest.is_file():
            raise installer.MaterializerInstallError(
                f"verified managed runtime manifest is missing for materializer plugin {plugin_id!r}"
            )
        manifest = manifest.resolve()

        current_plugin, current_target = _registered_target(
            plugin_id,
            install_root=install_root,
            registry_path=registry_path,
        )
        current_manifest = installer._contained(
            runtime,
            current_plugin["manifest"],
            "current managed runtime manifest",
        ).resolve()
        if current_target != target or current_manifest != manifest:
            raise installer.MaterializerInstallError(
                f"materializer plugin {plugin_id!r} registry binding changed while acquiring its runtime lock"
            )
        installer._validate_binding(current_plugin, runtime)
        if materializer_id not in current_plugin["materializers"]:
            raise installer.MaterializerInstallError(
                f"materializer {materializer_id!r} is not approved by registry plugin {plugin_id!r}"
            )

        execution_identity = receipt["execution_identity_sha256"]
        policy = installer.compare_cacheability_policy(
            current_plugin,
            materializer_id,
            verified_execution_identity=execution_identity,
        )
        if receipt.get("schema_version") != 3 and policy["reuse_allowed"]:
            # Receipt v2 remains a supported integrity/execution compatibility
            # format, but its identity includes ephemeral install provenance.
            # Suppress only positive reusable authorization; an explicit
            # non-reusable registry disposition remains authoritative and visible.
            policy = {
                "mode": "unknown",
                "reuse_allowed": False,
                "attestation_sha256": None,
            }
        return {
            **policy,
            "plugin_id": current_plugin["id"],
            "materializer_id": materializer_id,
            "plugin_ref": current_plugin["ref"],
            "execution_identity_sha256": execution_identity,
        }


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
    """Run one materializer from a verified, already-installed registry plugin.

    The installer runtime lock is held from the final integrity and registry
    binding checks through converter completion so an explicit concurrent repair
    cannot replace the managed environment after it has been approved for this
    execution.
    """
    _plugin, target = _registered_target(
        plugin_id,
        install_root=install_root,
        registry_path=registry_path,
    )
    # Merely attempting to run an uninstalled plugin must not create managed
    # directories or the installer's persistent lock marker.
    if not target.exists():
        raise _not_installed(plugin_id)

    lock_path = target.parent / f".{target.name}.lock"
    with installer._lock(lock_path):
        manifest = resolve_installed_manifest(
            plugin_id,
            install_root=install_root,
            registry_path=registry_path,
        )
        current_plugin, current_target = _registered_target(
            plugin_id,
            install_root=install_root,
            registry_path=registry_path,
        )
        expected_runtime = (target / "runtime").resolve()
        if current_target != target or manifest.parent != expected_runtime:
            raise installer.MaterializerInstallError(
                f"materializer plugin {plugin_id!r} registry binding changed while acquiring its runtime lock"
            )
        # The environment hash proves the installed bytes are intact; this
        # binding check separately proves those bytes still declare exactly the
        # materializers approved by the current registry entry.
        installer._validate_binding(current_plugin, expected_runtime)
        if materializer_id not in current_plugin["materializers"]:
            raise installer.MaterializerInstallError(
                f"materializer {materializer_id!r} is not approved by registry plugin {plugin_id!r}"
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
