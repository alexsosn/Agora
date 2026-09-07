#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.cold_compile import ColdCompileSupervisor
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.load_safety import cfm_marker, current_cfm_version
from agora_context_fabric.resolver import PreparedCorpus
from agora_context_fabric.service import ContextFabricService


_RESOURCE = ResourceSpec(
    id="cold-smoke",
    name="Cold-load smoke fixture",
    plugin="context-fabric",
    provider="context-fabric",
    kind="corpus",
    repository="unused/cold-smoke",
    languages=("test",),
    disciplines=("testing",),
)


class _Resolver:
    def __init__(self, store: GitStore, prepared: PreparedCorpus):
        self.store = store
        self.prepared = prepared

    def prepare_with_modules(self, resource_id: str, **_kwargs):
        if resource_id != self.prepared.resource_id:
            raise KeyError(resource_id)
        return self.prepared


def _write_fixture(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "otype.tf").write_text(
        "@node\n@valueType=str\n\nword\nword\n3\tsentence\n",
        encoding="utf-8",
    )
    (path / "oslots.tf").write_text(
        "@edge\n@valueType=int\n\n3\t1-2\n",
        encoding="utf-8",
    )
    (path / "otext.tf").write_text(
        "@config\n"
        "@fmt:text-orig-full={word}\n"
        "@sectionFeatures=sentence_id\n"
        "@sectionTypes=sentence\n"
        "@structureFeatures=\n"
        "@structureTypes=\n",
        encoding="utf-8",
    )
    (path / "word.tf").write_text(
        "@node\n@valueType=str\n\nalpha\nbeta\n",
        encoding="utf-8",
    )
    (path / "sentence_id.tf").write_text(
        "@node\n@valueType=str\n\n3\tS1\n",
        encoding="utf-8",
    )


def run_smoke() -> dict[str, object]:
    from cfabric_mcp import corpus_manager

    with tempfile.TemporaryDirectory(prefix="agora-cold-load-smoke-") as tmp:
        root = Path(tmp)
        store = GitStore(
            root / "cache",
            snapshot_soft_limit_bytes=1024**3,
            min_free_bytes=0,
        )
        revision = "a" * 40
        path = (
            store.snapshots_dir
            / "cold-smoke"
            / revision
            / "corpora"
            / "tf"
            / "1.0"
        )
        _write_fixture(path)
        store.touch_cache_object(path)
        prepared = PreparedCorpus(
            "cold-smoke",
            None,
            "agora-cold-smoke@1.0",
            "tf/1.0",
            path,
            "1.0",
            revision,
        )
        cfm_version = current_cfm_version()
        supervisor = ColdCompileSupervisor(
            cfm_version=cfm_version,
            poll_interval=0.05,
            terminate_grace_seconds=1.0,
        )
        service = ContextFabricService(
            Catalog([_RESOURCE]),
            _Resolver(store, prepared),
            corpus_manager,
            cold_compiler=supervisor,
            cfm_version=cfm_version,
        )

        result = service.load(
            "cold-smoke",
            features=["word"],
            max_compile_gb=0.25,
            max_compile_minutes=2,
        )
        marker = cfm_marker(path, cfm_version)
        if not marker.is_file():
            raise RuntimeError(f"cold worker produced no completion marker: {marker}")
        if result.get("logical_name") != "agora-cold-smoke@1.0":
            raise RuntimeError(f"unexpected logical name: {result.get('logical_name')!r}")
        if result.get("corpus") is None:
            raise RuntimeError("parent warm load returned no corpus information")
        if service.cache_status()["active_loads"]:
            raise RuntimeError("cold load remained active after synchronous success")

        unloaded = service.unload("agora-cold-smoke@1.0")
        if not unloaded.get("was_loaded"):
            raise RuntimeError("successful cold-load smoke could not be unloaded")

        return {
            "status": "ok",
            "logical_name": result["logical_name"],
            "cfm_version": cfm_version,
            "completion_marker": marker.name,
            "unloaded": True,
        }


def main() -> int:
    print(json.dumps(run_smoke(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
