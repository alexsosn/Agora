#!/usr/bin/env python3
"""Exact published ORACC-TF v1.0.0 -> Agora Context-Fabric consumer smoke."""
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

RESOURCE = "assyrian-royal-inscriptions"
SOURCE_KEY = "riao/ria1:Q001801"
ASSET_SHA = "788f580604e30054fab34c4c3ea60ec3eb4f399412f1da90f778469d03507468"
FEATURES = ["document_key", "line", "form", "cf", "gw", "utf8",
            "translation_text", "translation_line", "synthetic"]


def check(api):
    doc = next(
        n for n in api.F.otype.s("document")
        if api.F.document_key.v(n) == SOURCE_KEY
    )
    lines = [n for n in api.L.d(doc, otype="line") if api.F.line.v(n) == "Q001801.1"]
    if len(lines) != 1:
        raise AssertionError(f"expected one real {SOURCE_KEY} line, got {len(lines)}")
    words = api.L.d(lines[0], otype="word")
    if not words or not any(api.F.form.v(n) for n in words):
        raise AssertionError("released corpus has no transliterated words for Q001801.1")
    signs = api.L.d(lines[0], otype="sign")
    if not any(api.F.utf8.v(n) for n in signs):
        raise AssertionError("released corpus has no cuneiform signs for Q001801.1")
    translations = api.E.translation_line.t(lines[0])
    if not translations or not any(api.F.translation_text.v(n) for n in translations):
        raise AssertionError("released corpus has no upstream-aligned TEI text for Q001801.1")
    print(json.dumps({
        "document_key": SOURCE_KEY, "line": "Q001801.1",
        "words": len(words), "signs": len(signs),
        "aligned_tei_units": len(translations),
    }, sort_keys=True))


def main():
    catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
    resource = catalog.get(RESOURCE)
    assert resource.release["sha256"] == ASSET_SHA
    with tempfile.TemporaryDirectory(prefix="agora-oracc-release-") as d:
        store = GitStore(Path(d) / "cache", min_free_bytes=0)
        service = ContextFabricService(
            catalog, ContextFabricResolver(catalog, store), corpus_manager
        )
        listed = service.list_resources(query=RESOURCE)
        assert len(listed) == 1 and listed[0]["id"] == RESOURCE
        assert service.resolver.corpus_versions(RESOURCE) == ("1.0.0",)
        prepared = service.prepare(RESOURCE, source_mode="require-fresh")
        assert prepared["source_revision"] == ASSET_SHA
        assert (Path(prepared["path"]) / ".agora-release.json").is_file()
        assert not list(store.repositories_dir.iterdir()), "must not clone ORACC builder"
        loaded = service.load(RESOURCE, features=FEATURES, source_mode="offline")
        try:
            assert loaded["source_revision"] == ASSET_SHA
            check(corpus_manager.get_api(loaded["logical_name"]))
        finally:
            service.unload(loaded["logical_name"])
        # Fresh resolver instance, same managed disk cache and no network.
        fresh = ContextFabricService(
            catalog, ContextFabricResolver(catalog, store), corpus_manager
        )
        loaded2 = fresh.load(RESOURCE, features=FEATURES, source_mode="offline")
        try:
            assert loaded2["path"] == loaded["path"]
            assert loaded2["source_revision"] == ASSET_SHA
            check(corpus_manager.get_api(loaded2["logical_name"]))
        finally:
            fresh.unload(loaded2["logical_name"])
        assert not list(store.repositories_dir.iterdir())
        print(json.dumps({
            "resource": RESOURCE, "asset_sha256": ASSET_SHA,
            "snapshot": loaded2["path"], "offline_reload": "success",
            "cache_status": store.cache_status()["totals_by_kind"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
