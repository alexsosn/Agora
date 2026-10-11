"""Live #237: registered Burns with real original source and immutable CUC.

Only the CI runner downloads Burns' licensed Workbooks and caches generated
local artifacts. Neither source PDFs, generated CSV, nor TF are redistributed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from tf.fabric import Fabric

from scripts.agora_compose_feature_module import (
    _bundled_context_fabric_resolver,
    materialize_requested_feature_module,
)

CUC_COMMIT = "0408967b1808c1f22c69e299d302b1e7b5e26354"
WARP = ("otype.tf", "oslots.tf", "otext.tf")


def _hash_warp(root: Path) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in WARP}


def main() -> None:
    csv = Path(os.environ["BURNS_CSV_DIR"]).resolve(strict=True)
    install_root = Path(os.environ["BURNS_INSTALL_ROOT"]).resolve(strict=True)
    cache = Path(os.environ["AGORA_CORPUS_CACHE"]).resolve()
    assert len(list(csv.glob("*/*.csv"))) >= 45, "full Burns source CSV set is missing"
    resolver = _bundled_context_fabric_resolver(cache_dir=cache)
    prepared_parent = resolver.prepare("cuc", version="0.2.8")
    assert prepared_parent.source_revision == CUC_COMMIT, prepared_parent.source_revision
    assert prepared_parent.version == "0.2.8"
    before = _hash_warp(prepared_parent.path)

    parent_api = Fabric(locations=[str(prepared_parent.path)], modules=[""],
                        silent="deep").loadAll(silent="deep")
    assert parent_api is not None, "immutable CUC parent did not load"
    slots = parent_api.F.otype.maxSlot
    nodes = parent_api.F.otype.maxNode

    module_path = materialize_requested_feature_module(
        module_id="cuc-burns", plugin_id="cuc-burns",
        materializer_id="cuc-burns-csv", source=csv,
        cache_dir=cache, install_root=install_root,
    )
    assert module_path.is_dir()
    assert (module_path / "burns_headword_1.tf").is_file()
    assert (module_path / "burns-feature-module-report.json").is_file()
    assert not set(WARP) & {path.name for path in module_path.iterdir()}
    assert all(path.is_file() and not path.is_symlink() for path in module_path.iterdir())
    receipt = json.loads((module_path / "agora-materialization.json").read_text())
    assert receipt["sandbox"] == "bubblewrap", receipt["sandbox"]
    assert receipt["parent"] == {
        "resource_id": "cuc",
        "version": "0.2.8",
        "source_revision": CUC_COMMIT,
        "relative_path": "tf/0.2.8",
        "trusted": True,
    }, receipt["parent"]

    composed = resolver.prepare_with_modules(
        "cuc", version="0.2.8", modules=("cuc-burns",)
    )
    assert composed.modules and composed.modules[0].resource_id == "cuc-burns"
    assert composed.modules[0].source_revision.startswith("local-")
    assert _hash_warp(prepared_parent.path) == before, "CUC parent warp changed"

    composed_api = Fabric(locations=[str(composed.path)], modules=[""],
                          silent="deep").loadAll(silent="deep")
    assert composed_api is not None, "managed CUC + Burns TF overlay did not load"
    assert composed_api.F.otype.maxSlot == slots, "Burns changed the CUC slot universe"
    assert composed_api.F.otype.maxNode == nodes, "Burns invented/replaced corpus nodes"
    carriers = sum(
        composed_api.F.burns_headword_1.v(word) is not None
        for word in parent_api.F.otype.s("word")
    )
    assert carriers > 0, "real Burns annotations are not queryable on existing CUC word nodes"
    print(json.dumps({
        "status": "ok", "parent_revision": CUC_COMMIT, "tf_version": "0.2.8",
        "slots": slots, "nodes": nodes, "burns_carriers": carriers,
        "sandbox": receipt["sandbox"], "module_snapshot": composed.modules[0].source_revision,
        "parent_warp_unchanged": True,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
