#!/usr/bin/env python3
"""Real upstream consumer oracle for #314; not a registry-only smoke."""
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

MODULE = "bhsa-aleppo-alignment"
ALEPPO_PIN = "db38ddc918fd5d6e47a118f24545bd925975a597"
BHSA_PIN = "4db00e2157915495e1a4d3d57e41223df24775da"
MISSING_BHSA = set(range(125049, 125077)) | {164398, 164664}


def read_mapping(api, feature, domain_size, target_size):
    words = tuple(api.F.otype.s("word"))
    assert words == tuple(range(1, domain_size + 1)), "unexpected word IDs"
    mapping = {}
    missing = set()
    value_at = getattr(api.F, feature).v
    for word in words:
        target = value_at(word)
        if target is None:
            missing.add(word)
        else:
            assert type(target) is int and 1 <= target <= target_size, (word, target)
            mapping[word] = target
    return mapping, missing


def main():
    catalog = Catalog.from_plugin_root(ROOT / "plugins/context-fabric")
    module = catalog.get(MODULE)
    assert module.ref == ALEPPO_PIN
    with tempfile.TemporaryDirectory(prefix="agora-aleppo-314-") as directory:
        store = GitStore(Path(directory) / "cache", min_free_bytes=0)
        resolver = ContextFabricResolver(catalog, store)
        service = ContextFabricService(catalog, resolver, corpus_manager)
        repo, revision = resolver._repo(module)
        assert revision == ALEPPO_PIN
        assert set(store.feature_files(repo, module.tf_path, revision)) == {"aleppo.tf"}
        native = service.prepare("aleppo", source_mode="require-fresh")
        assert native["source_revision"] == ALEPPO_PIN and native["version"] == "1.0"
        parent = service.prepare("bhsa", version="2021", source_mode="require-fresh")
        assert parent["source_revision"] == BHSA_PIN and parent["version"] == "2021"
        parent_path = Path(parent["path"])
        assert not (parent_path / "aleppo.tf").exists()
        warp = {name: (parent_path / name).read_bytes()
                for name in ("otype.tf", "oslots.tf", "otext.tf")}

        loaded = service.load("aleppo", features=["bhsa", "aleppo_extant", "book", "chapter", "verse"],
                              source_mode="offline")
        try:
            assert loaded["source_revision"] == ALEPPO_PIN
            api = corpus_manager.get_api(loaded["logical_name"])
            forward, missing = read_mapping(api, "bhsa", 426562, 426590)
            assert missing == {164371} and len(forward) == 426561
            genesis = api.T.nodeFromSection(("Genesis", 1, 1))
            ruth = api.T.nodeFromSection(("Ruth", 1, 7))
            assert api.F.aleppo_extant.v(genesis) == 0
            assert api.F.aleppo_extant.v(ruth) == 1
            ruth_bhsa = {forward[w] for w in api.L.d(ruth, otype="word") if w in forward}
            assert ruth_bhsa
        finally:
            service.unload(loaded["logical_name"])

        base = service.load("bhsa", version="2021", features=["g_cons", "book", "chapter", "verse"],
                            source_mode="offline")
        try:
            assert base["source_revision"] == BHSA_PIN
            api = corpus_manager.get_api(base["logical_name"])
            assert not hasattr(api.F, "aleppo")
            assert len(api.F.otype.s("word")) == 426590
            assert api.F.g_cons.v(1) == "B"
            ruth = api.T.nodeFromSection(("Ruth", 1, 7))
            assert ruth_bhsa <= set(api.L.d(ruth, otype="word"))
        finally:
            service.unload(base["logical_name"])

        # Offline mode requires a materialized module snapshot, not just Git metadata.
        prepared = service.prepare("bhsa", version="2021", modules=[MODULE],
                                   source_mode="require-fresh")
        assert prepared["source_revision"] == BHSA_PIN
        assert prepared["modules"][0]["source_revision"] == ALEPPO_PIN
        assert Path(prepared["path"], "aleppo.tf").is_file()

        for iteration in range(2):
            if iteration:
                service = ContextFabricService(catalog, ContextFabricResolver(catalog, store),
                                               corpus_manager)
            combined = service.load(
                "bhsa", version="2021", modules=[MODULE],
                features=["aleppo", "g_cons", "book", "chapter", "verse"], source_mode="offline",
            )
            try:
                assert combined["source_revision"] == BHSA_PIN
                assert len(combined["modules"]) == 1
                assert combined["modules"][0]["source_revision"] == ALEPPO_PIN
                api = corpus_manager.get_api(combined["logical_name"])
                reverse, absent = read_mapping(api, "aleppo", 426590, 426562)
                assert len(reverse) == 426560 and absent == MISSING_BHSA
                assert all(forward.get(a) == b for b, a in reverse.items())
                assert {(a, b, reverse.get(b)) for a, b in forward.items()
                        if reverse.get(b) != a} == {(215228, 215256, 215227)}
                assert api.F.g_cons.v(1) == "B"
                assert tuple(api.T.sectionFromNode(1)) == ("Genesis", 1, 1)
                composed = Path(combined["path"])
                for filename, content in warp.items():
                    assert (composed / filename).read_bytes() == content, filename
                assert (composed / "aleppo.tf").is_file()
                assert not (parent_path / "aleppo.tf").exists()
            finally:
                service.unload(combined["logical_name"])
        print(json.dumps({"forward": len(forward), "reverse": len(reverse),
                          "missing_bhsa": len(absent), "offline_reload": "passed",
                          "parent_unchanged": True}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
