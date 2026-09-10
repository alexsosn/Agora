from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver


REVISION = "a" * 40
OTHER_REVISION = "b" * 40


def _catalog(*, kind: str = "corpus", tf_path: str | None = None) -> Catalog:
    kwargs = {
        "id": "fixture",
        "name": "Cached parent fixture",
        "plugin": "context-fabric",
        "provider": "context-fabric",
        "kind": kind,
        "repository": "example/fixture",
        "languages": ("test",),
        "disciplines": ("test",),
    }
    if tf_path is not None:
        kwargs["tf_path"] = tf_path
    if kind == "feature-module":
        kwargs.update(
            parent="parent",
            parent_versions=("1.0",),
            module_path="modules/fixture",
        )
    return Catalog([ResourceSpec(**kwargs)])


def _resolver(root: Path, *, kind: str = "corpus", tf_path: str | None = None):
    store = GitStore(root / "cache", min_free_bytes=0)
    return ContextFabricResolver(_catalog(kind=kind, tf_path=tf_path), store), store


def _snapshot(
    store: GitStore,
    *,
    resource_id: str = "fixture",
    revision: str = REVISION,
    namespace: str = "corpora",
    relative_path: str = "tf/1.0",
) -> Path:
    destination = (
        store.snapshots_dir
        / resource_id
        / revision
        / namespace
        / Path(relative_path)
    )
    destination.mkdir(parents=True)
    if namespace == "corpora":
        (destination / "otype.tf").write_text("@node\n\nword\n", encoding="utf-8")
    else:
        (destination / "addon.tf").write_text("@node\n\nfeature\n", encoding="utf-8")
    store.touch_cache_object(destination)
    return destination.resolve()


def _overlay(store: GitStore, *, resource_id: str = "fixture", revision: str = REVISION) -> Path:
    destination = store.overlays_dir / resource_id / revision / "deadbeef"
    destination.mkdir(parents=True)
    (destination / "otype.tf").write_text("@node\n\nword\n", encoding="utf-8")
    store.touch_cache_object(destination)
    return destination.resolve()


class ExactCachedCorpusLookupRedTests(unittest.TestCase):
    def test_exact_indexed_corpus_snapshot_resolves_without_repository_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver, store = _resolver(root)
            expected = _snapshot(store)

            with (
                patch.object(store, "ensure_metadata", side_effect=AssertionError("metadata acquisition attempted")),
                patch.object(store, "_export_snapshot", side_effect=AssertionError("snapshot export attempted")),
                patch.object(store, "_select", side_effect=AssertionError("Git selection attempted")),
                patch.object(resolver, "_repo", side_effect=AssertionError("repository resolver attempted")),
                patch.object(resolver, "prepare", side_effect=AssertionError("ordinary prepare attempted")),
            ):
                cached = resolver.resolve_cached_corpus(
                    "fixture", version="1.0", source_revision=REVISION
                )

            self.assertEqual(cached.resource_id, "fixture")
            self.assertEqual(cached.version, "1.0")
            self.assertEqual(cached.source_revision, REVISION)
            self.assertEqual(cached.relative_path, "tf/1.0")
            self.assertEqual(cached.path, expected)

    def test_non_corpus_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            resolver, _store = _resolver(Path(tmp), kind="feature-module")
            with self.assertRaisesRegex(ValueError, "not a corpus"):
                resolver.resolve_cached_corpus(
                    "fixture", version="1.0", source_revision=REVISION
                )

    def test_invalid_identity_is_rejected_before_cache_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            resolver, store = _resolver(Path(tmp))
            with patch.object(store, "cache_entries", side_effect=AssertionError("cache inspected")):
                with self.assertRaisesRegex(ValueError, "version"):
                    resolver.resolve_cached_corpus(
                        "fixture", version="", source_revision=REVISION
                    )
                with self.assertRaisesRegex(ValueError, "immutable"):
                    resolver.resolve_cached_corpus(
                        "fixture", version="1.0", source_revision="main"
                    )

    def test_wrong_or_missing_exact_identity_never_falls_back_or_acquires(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver, store = _resolver(root)
            _snapshot(store)

            for version, revision in (("2.0", REVISION), ("1.0", OTHER_REVISION)):
                with self.subTest(version=version, revision=revision):
                    with (
                        patch.object(store, "ensure_metadata", side_effect=AssertionError("metadata acquisition attempted")),
                        patch.object(store, "_export_snapshot", side_effect=AssertionError("snapshot export attempted")),
                        patch.object(store, "_select", side_effect=AssertionError("Git selection attempted")),
                        patch.object(resolver, "_repo", side_effect=AssertionError("repository resolver attempted")),
                        patch.object(resolver, "prepare", side_effect=AssertionError("ordinary prepare attempted")),
                    ):
                        with self.assertRaisesRegex(ValueError, "cached|cache"):
                            resolver.resolve_cached_corpus(
                                "fixture", version=version, source_revision=revision
                            )

    def test_feature_module_and_overlay_cannot_masquerade_as_parent_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver, store = _resolver(root)
            _snapshot(store, namespace="feature-modules")
            _overlay(store)

            with self.assertRaisesRegex(ValueError, "cached|cache"):
                resolver.resolve_cached_corpus(
                    "fixture", version="1.0", source_revision=REVISION
                )

    def test_pinned_tf_path_must_match_exact_cached_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver, store = _resolver(root, tf_path="tf/1.0")
            _snapshot(store, relative_path="other/tf/1.0")

            with self.assertRaisesRegex(ValueError, "cached|cache"):
                resolver.resolve_cached_corpus(
                    "fixture", version="1.0", source_revision=REVISION
                )

    def test_multiple_same_version_candidates_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver, store = _resolver(root)
            _snapshot(store, relative_path="tf/1.0")
            _snapshot(store, relative_path="nested/tf/1.0")

            with self.assertRaisesRegex(ValueError, "ambiguous|multiple"):
                resolver.resolve_cached_corpus(
                    "fixture", version="1.0", source_revision=REVISION
                )

    def test_deleted_or_tampered_identity_sidecar_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver, store = _resolver(root)
            path = _snapshot(store)
            meta_path = store._meta_path(path)

            original = meta_path.read_text(encoding="utf-8")
            meta_path.unlink()
            with self.assertRaisesRegex(ValueError, "cached|cache"):
                resolver.resolve_cached_corpus(
                    "fixture", version="1.0", source_revision=REVISION
                )

            meta_path.write_text(original, encoding="utf-8")
            data = json.loads(original)
            data["revision"] = OTHER_REVISION
            meta_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cached|cache"):
                resolver.resolve_cached_corpus(
                    "fixture", version="1.0", source_revision=REVISION
                )


if __name__ == "__main__":
    unittest.main()
