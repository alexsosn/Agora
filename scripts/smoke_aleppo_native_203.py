#!/usr/bin/env python3
"""#203 exact pinned Aleppo native TF load, manuscript caveat and offline reopen.

Run only in the opt-in real-upstream integration workflow, not in unit suites.
No converter, reverse BHSA projection or BHSA corpus is installed here.
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

RESOURCE = "aleppo"
PIN = "db38ddc918fd5d6e47a118f24545bd925975a597"
FEATURES = ("g_word_utf8", "g_word_norm", "aleppo_extant", "bhsa", "bhsa_seg",
            "qere_utf8", "book", "chapter", "verse")


def assert_semantics(api) -> dict:
    words = tuple(api.F.otype.s("word"))
    verses = tuple(api.F.otype.s("verse"))
    if len(words) != 426_562 or len(verses) != 23_202:
        raise AssertionError(
            f"upstream node topology changed: words={len(words)}, verses={len(verses)}"
        )
    missing = sum(api.F.aleppo_extant.v(v) == 0 for v in verses)
    extant = sum(api.F.aleppo_extant.v(v) == 1 for v in verses)
    if (missing, extant) != (7_965, 15_237):
        raise AssertionError(f"manuscript-loss accounting changed: {(missing, extant)}")
    genesis = api.T.nodeFromSection(("Genesis", 1, 1))
    ruth = api.T.nodeFromSection(("Ruth", 1, 7))
    if genesis is None or ruth is None:
        raise AssertionError("published Aleppo book/chapter/verse navigation missing")
    if api.F.aleppo_extant.v(genesis) != 0:
        raise AssertionError("Genesis 1:1 must not be represented as surviving codex text")
    if api.F.aleppo_extant.v(ruth) != 1:
        raise AssertionError("Ruth 1:7 must be on an extant codex page")
    if not hasattr(api.C, "sections"):
        raise AssertionError("Context-Fabric lost the section index")
    if tuple(api.T.sectionFromNode(ruth)) != ("Ruth", 1, 7):
        raise AssertionError("Aleppo section navigation differs after compilation")
    ruth_words = api.L.d(ruth, otype="word")
    if not ruth_words or not any(api.F.g_word_utf8.v(w) for w in ruth_words):
        raise AssertionError("Ruth verse lost native Hebrew word text")
    mapped = sum(api.F.bhsa.v(w) is not None for w in words)
    if not 426_000 <= mapped <= 426_562:
        raise AssertionError(f"BHSA 2021 reference feature unexpectedly sparse: {mapped}")
    summary = {
        "words": len(words), "verses": len(verses), "missing_codex_verses": missing,
        "extant_codex_verses": extant, "bhsa_reference_words": mapped,
        "ruth_words": len(ruth_words),
    }
    print(json.dumps(summary, sort_keys=True), flush=True)
    return summary


def main() -> None:
    catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
    resource = catalog.get(RESOURCE)
    assert resource.ref == PIN and resource.tf_path == "tf/1.0"
    assert resource.acquisition_strategy == "repository"
    with tempfile.TemporaryDirectory(prefix="agora-aleppo-203-") as directory:
        store = GitStore(Path(directory) / "cache", min_free_bytes=0)
        service = ContextFabricService(catalog, ContextFabricResolver(catalog, store), corpus_manager)
        listed = service.list_resources(query=RESOURCE)
        assert len(listed) == 1 and listed[0]["id"] == RESOURCE
        prepared = service.prepare(RESOURCE, source_mode="require-fresh")
        assert prepared["source_revision"] == PIN and prepared["version"] == "1.0"
        path = Path(prepared["path"])
        assert all((path / name).is_file() for name in
                   ("otype.tf", "oslots.tf", "otext.tf", "bhsa.tf", "aleppo_extant.tf"))
        first = service.load(RESOURCE, features=list(FEATURES), source_mode="offline")
        try:
            assert first["source_revision"] == PIN
            cold = assert_semantics(corpus_manager.get_api(first["logical_name"]))
        finally:
            service.unload(first["logical_name"])
        fresh = ContextFabricService(catalog, ContextFabricResolver(catalog, store), corpus_manager)
        second = fresh.load(RESOURCE, features=list(FEATURES), source_mode="offline")
        try:
            assert second["source_revision"] == PIN
            assert second["path"] == first["path"]
            warm = assert_semantics(corpus_manager.get_api(second["logical_name"]))
            assert warm == cold
        finally:
            fresh.unload(second["logical_name"])
        print(json.dumps({
            "resource_id": RESOURCE, "source_revision": PIN,
            "native_path": "tf/1.0", "offline_reopen": "pass",
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
