#!/usr/bin/env python3
"""#267: pinned real Tischendorf 2.8 + 14 optional morphology TF features.

This is a real-data integration oracle, not a documentation/registry-only test.
No converter is installed or executed; source acquisition is Git-data only.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/context-fabric/src"))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service_source_modes import ContextFabricService
from cfabric_mcp import corpus_manager

PARENT = "tischendorf_tf"
MODULE = "tischendorf-morphology-additions"
PIN = "ca96bd44f38fd716d4a1faa6d451f3716f0dce46"
SOURCE_DIR = "FeatureAdditions"
FEATURES = frozenset((
    "case.tf", "freq_lex_og.tf", "gn.tf", "lex_abc.tf", "lex_og.tf",
    "mood.tf", "nountype.tf", "nu.tf", "originterrdiff.tf",
    "prntyp.tf", "ps.tf", "sp.tf", "voice.tf", "vt.tf",
))


def inspect_source(repo_path: Path, revision: str, store: GitStore) -> None:
    assert revision == PIN, f"unreviewed source revision: {revision}"
    selected = set(store.feature_files(repo_path, SOURCE_DIR, revision))
    assert selected == FEATURES, f"canonical upstream module changed: {selected ^ FEATURES}"
    assert not {"otype.tf", "oslots.tf", "otext.tf"} & selected
    module_path = store.materialize_feature_module(repo_path, SOURCE_DIR, revision)
    assert {p.name for p in module_path.glob("*.tf")} == FEATURES
    assert not (module_path / "test").exists(), "non-feature upstream artifact leaked"
    for filename in sorted(FEATURES):
        # Metadata is checked from the immutable source bytes. TF's public
        # loaded feature API below validates actual parsed node/value data;
        # the module alone intentionally has no otype/oslots warp features.
        source = (module_path / filename).read_text(encoding="utf-8")
        if not source.startswith("@node\\n") or "@valueType=" not in source:
            raise AssertionError(f"invalid native TF node feature header {filename}")
    print(json.dumps({"tf_feature_files": len(FEATURES), "sha": revision,
                      "parent_max_node": 152077}, sort_keys=True), flush=True)


def inspect_api(api, *, module: bool) -> dict:
    words = api.F.otype.s("word")
    assert len(words) == 137_711, f"parent slot identity changed: {len(words)}"
    assert len(api.F.otype.s("book")) == 27
    original = (api.F.morph.v(1), api.F.qere.v(1), tuple(api.T.sectionFromNode(1)))
    if module:
        # These values come from actual pinned FeatureAdditions source rows.
        assert api.F.case.v(1) == "nominative", api.F.case.v(1)
        assert api.F.lex_og.v(1) == "biblos", api.F.lex_og.v(1)
        assert api.F.freq_lex_og.v(1) == 10, api.F.freq_lex_og.v(1)
        for name in ("case", "gn", "mood", "sp", "ps", "nu", "voice", "vt",
                     "lex_abc", "lex_og", "freq_lex_og", "originterrdiff",
                     "prntyp", "nountype"):
            assert hasattr(api.F, name), f"requested module feature {name} not loaded"
            # Text-Fabric's loaded node-feature items are the authoritative
            # decoded values and bounds; no unsupported low-level parser.
            observed = 0
            for node, value in getattr(api.F, name).items():
                if type(node) is not int or not 1 <= node <= 152_077:
                    raise AssertionError(f"{name}: feature node outside pinned parent warp: {node!r}")
                if value is None:
                    raise AssertionError(f"{name}: null decoded value at node {node}")
                observed += 1
            if not observed:
                raise AssertionError(f"{name}: no actual parsed values in upstream feature")
    else:
        assert not hasattr(api.F, "case"), "parent-only load unexpectedly includes additions"
    return {"words": len(words), "first_original": original}


def main() -> None:
    catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
    resource = catalog.get(MODULE)
    assert resource.ref == PIN and resource.parent == PARENT
    assert resource.tf_path == SOURCE_DIR
    with tempfile.TemporaryDirectory(prefix="agora-tischendorf-267-") as directory:
        store = GitStore(Path(directory) / "cache", min_free_bytes=0)
        resolver = ContextFabricResolver(catalog, store)
        service = ContextFabricService(catalog, resolver, corpus_manager)
        module_repo, revision = resolver._repo(resource)
        inspect_source(module_repo, revision, store)
        parent_prepare = service.prepare(PARENT, source_mode="require-fresh")
        assert parent_prepare["source_revision"] == PIN
        assert parent_prepare["version"] == "2.8"
        parent_path = Path(parent_prepare["path"])
        parent_warp = {name: (parent_path / name).read_bytes()
                       for name in ("otype.tf", "oslots.tf")}
        first = service.load(PARENT, features=["morph", "qere"], source_mode="offline")
        try:
            assert first["source_revision"] == PIN
            alone = inspect_api(corpus_manager.get_api(first["logical_name"]), module=False)
        finally:
            service.unload(first["logical_name"])
        second = service.load(
            PARENT, modules=[MODULE], source_mode="offline",
            features=["morph", "qere", *sorted(name[:-3] for name in FEATURES)],
        )
        try:
            assert second["source_revision"] == PIN
            with_module = inspect_api(corpus_manager.get_api(second["logical_name"]), module=True)
            assert alone == with_module, "optional features changed parent text/sections"
            composed = Path(second["path"])
            for filename, expected in parent_warp.items():
                assert (composed / filename).read_bytes() == expected, filename
        finally:
            service.unload(second["logical_name"])
        print(json.dumps({
            "parent": PARENT, "module": MODULE, "source_revision": PIN,
            "features": 14, "offline": "passed", "parent_unchanged": True,
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
