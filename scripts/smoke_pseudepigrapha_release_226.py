#!/usr/bin/env python3
"""Published Pseudepigrapha-TF v1.1.0 -> named Agora resource -> offline reopen.

This uses only reviewed, immutable release bytes. No OCP clone or converter.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/context-fabric/src"))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service_source_modes import ContextFabricService
from cfabric_mcp import corpus_manager

RESOURCE = "pseudepigrapha"
ASSET_SHA = "88f23ac9106c6ea8b35f89b19d760cf5d4ee544a3f8d8262d6ed7e2092e447e9"
SECTION = ("1En__Ethiopic", "1", "2")
FEATURES = [
    "source_ref", "version_id", "version_kind", "ocp_book", "language",
    "reading_of", "witness", "is_primary", "reading_text",
    "translation_of", "translation_unit_of", "generated_language",
]


def check(api):
    verse = api.T.nodeFromSection(SECTION)
    if verse is None or api.F.otype.v(verse) != "verse":
        raise AssertionError(f"published corpus lost version-qualified section {SECTION!r}")
    if not api.F.source_ref.v(verse):
        raise AssertionError("OCP original source_ref lost at representative verse")
    # A CFM warm load must preserve Text-API navigation, not just loaded
    # source feature values. The compiler's CFM reader currently misses
    # C.sections even when the original cold load had it.
    if not hasattr(api.C, "sections"):
        raise AssertionError("compiled CFM load lost C.sections index")
    if tuple(api.T.sectionFromNode(verse)) != SECTION:
        raise AssertionError("cold/warm version-qualified section navigation differs")
    if not api.T.text(verse).strip():
        raise AssertionError("1 Enoch Ethiopic section has no text")
    books = tuple(api.F.otype.s("book"))
    sources = [b for b in books if api.F.version_kind.v(b) != "generated_translation"]
    generated = [b for b in books if api.F.version_kind.v(b) == "generated_translation"]
    if not sources or not generated:
        raise AssertionError("published corpus lacks source or distinct generated translation books")
    if not all(len(api.E.translation_of.f(b)) == 1 for b in generated):
        raise AssertionError("generated translation book is not linked to exactly one source version")
    if any(api.F.version_kind.v(b) == "generated_translation" for b in sources):
        raise AssertionError("generated output leaked into historical source-book class")
    readings = tuple(api.F.otype.s("reading"))
    if not readings:
        raise AssertionError("historical apparatus readings absent")
    if not any(api.E.reading_of.f(n) for n in readings):
        raise AssertionError("apparatus reading-to-unit edge absent")
    if not any(api.E.witness.f(n) for n in readings):
        raise AssertionError("apparatus witness citations absent")
    result = {
        "section": SECTION, "source_ref": api.F.source_ref.v(verse),
        "source_books": len(sources), "generated_translation_books": len(generated),
        "readings": len(readings),
    }
    print(json.dumps(result, sort_keys=True, ensure_ascii=False), flush=True)


def main():
    catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
    resource = catalog.get(RESOURCE)
    assert resource.release_archive["sha256"] == ASSET_SHA
    assert resource.ref == "39bd9fb895d1201e9cd9260170512fd8c399a3ac"
    with tempfile.TemporaryDirectory(prefix="agora-pseudepigrapha-release-") as tmp:
        store = GitStore(Path(tmp) / "cache", min_free_bytes=0)
        service = ContextFabricService(
            catalog, ContextFabricResolver(catalog, store), corpus_manager
        )
        listed = service.list_resources(query=RESOURCE)
        assert len(listed) == 1 and listed[0]["id"] == RESOURCE
        described = service.describe_resource(RESOURCE)
        assert described["default_version"] == "1.1"
        assert described["acquisition"]["archive"]["sha256"] == ASSET_SHA
        prepared = service.prepare(RESOURCE, source_mode="require-fresh")
        assert prepared["source_revision"] == ASSET_SHA
        path = Path(prepared["path"])
        assert len(tuple(path.glob("*.tf"))) == 96
        assert (path / ".agora-release.json").is_file()
        assert not list(store.repositories_dir.iterdir()), "unexpected Git builder/OCP checkout"
        first = service.load(RESOURCE, features=FEATURES, source_mode="offline")
        try:
            assert first["source_revision"] == ASSET_SHA
            check(corpus_manager.get_api(first["logical_name"]))
        finally:
            service.unload(first["logical_name"])
        # A new Context-Fabric service must reuse cache only and never request
        # a release download, clone OCP or start converter code.
        fresh = ContextFabricService(
            catalog, ContextFabricResolver(catalog, store), corpus_manager
        )
        with patch(
            "agora_context_fabric.release_download.download_pinned_release",
            side_effect=AssertionError("offline reload attempted network"),
        ):
            second = fresh.load(RESOURCE, features=FEATURES, source_mode="offline")
            try:
                assert second["path"] == first["path"]
                assert second["source_revision"] == ASSET_SHA
                check(corpus_manager.get_api(second["logical_name"]))
            finally:
                fresh.unload(second["logical_name"])
        print(json.dumps({
            "resource": RESOURCE, "sha256": ASSET_SHA,
            "offline_reload": "success",
            "cache": store.cache_status()["totals_by_kind"],
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
