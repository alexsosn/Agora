"""Issue #135 RED3a: resolver-owned, immutable parent binding before execution.

These contracts deliberately use a fake resolver with a realistic snapshot tree;
they must fail until a bounded orchestrator implementation exists.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import agora_materialize as host

try:
    from scripts import agora_compose_feature_module as compose
except ImportError:
    compose = None


REVISION = "a" * 40


def fixture(root: Path, *, allowed=("0.2.8",), revision=REVISION):
    snapshot_root = root / "snapshots"
    parent_path = snapshot_root / "cuc" / revision / "corpora" / "tf" / "0.2.8"
    parent_path.mkdir(parents=True)
    for name in ("otype.tf", "oslots.tf", "otext.tf"):
        (parent_path / name).write_text("fixture", encoding="utf-8")
    spec = {
        "id": "cuc-burns",
        "parent_input": {
            "resource": "cuc",
            "parent_versions": list(allowed),
            "required_paths": ["otype.tf", "oslots.tf", "otext.tf"],
        },
    }
    prepared = SimpleNamespace(
        resource_id="cuc", member_id=None, version="0.2.8",
        source_revision=revision, relative_path="tf/0.2.8", path=parent_path,
    )
    store = SimpleNamespace(snapshots_dir=snapshot_root, safe_cache_key=lambda _: "cuc")
    resolver = mock.Mock()
    resolver.store = store
    resolver.catalog.get.return_value = SimpleNamespace(id="cuc", kind="corpus")
    resolver.default_corpus_version.return_value = "0.2.8"
    resolver.prepare.return_value = prepared
    return spec, resolver, prepared


class ManagedParentResolutionRed3aTests(unittest.TestCase):
    def resolve(self, *args, **kwargs):
        self.assertIsNotNone(compose, "RED3a: managed parent orchestrator module missing")
        fn = getattr(compose, "resolve_managed_parent", None)
        self.assertTrue(callable(fn), "RED3a: resolve_managed_parent missing")
        return fn(*args, **kwargs)

    def test_prepares_exact_compatible_parent_and_propagates_resolved_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, resolver, prepared = fixture(Path(tmp))
            result = self.resolve(spec, resolver)
            self.assertIsInstance(result, host.ParentBinding)
            self.assertEqual(result.path, prepared.path.resolve())
            self.assertEqual(result.resource_id, "cuc")
            self.assertEqual(result.version, "0.2.8")
            self.assertEqual(result.source_revision, REVISION)
            self.assertTrue(result.trusted)
            resolver.catalog.get.assert_called_once_with("cuc")
            resolver.prepare.assert_called_once_with("cuc", version="0.2.8")

    def test_incompatible_request_rejected_before_preparation_or_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, resolver, _ = fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError, "compatible|version"):
                self.resolve(spec, resolver, requested_version="1935")
            resolver.prepare.assert_not_called()
            resolver.default_corpus_version.assert_not_called()

    def test_collection_parent_is_refused_before_prepare(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, resolver, _ = fixture(Path(tmp))
            resolver.catalog.get.return_value = SimpleNamespace(id="cuc", kind="collection")
            with self.assertRaisesRegex(ValueError, "corpus|collection"):
                self.resolve(spec, resolver)
            resolver.prepare.assert_not_called()

    def test_forged_unmanaged_directory_must_not_become_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec, resolver, prepared = fixture(root)
            outside = root / "user-supplied-parent"
            outside.mkdir()
            for name in spec["parent_input"]["required_paths"]:
                (outside / name).write_text("fake")
            prepared.path = outside
            with self.assertRaisesRegex(ValueError, "snapshot|managed"):
                self.resolve(spec, resolver)

    def test_identity_mismatch_after_prepare_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, resolver, prepared = fixture(Path(tmp))
            prepared.source_revision = "b" * 40
            with self.assertRaisesRegex(ValueError, "snapshot|revision"):
                self.resolve(spec, resolver)

    def test_missing_or_symlinked_required_tf_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, resolver, prepared = fixture(Path(tmp))
            (prepared.path / "otype.tf").unlink()
            with self.assertRaisesRegex(ValueError, "otype.tf"):
                self.resolve(spec, resolver)
            (prepared.path / "otype.tf").symlink_to(prepared.path / "oslots.tf")
            with self.assertRaisesRegex(ValueError, "otype.tf|symlink"):
                self.resolve(spec, resolver)

    def test_multiple_compatible_versions_require_matching_default_or_explicit_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, resolver, _ = fixture(Path(tmp), allowed=("0.2.8", "0.2.9"))
            resolver.default_corpus_version.return_value = "0.3.0"
            with self.assertRaisesRegex(ValueError, "compatible|version"):
                self.resolve(spec, resolver)
            resolver.prepare.assert_not_called()
            self.resolve(spec, resolver, requested_version="0.2.8")
            resolver.prepare.assert_called_once_with("cuc", version="0.2.8")

    def test_no_declared_parent_is_never_silently_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, resolver, _ = fixture(Path(tmp))
            del spec["parent_input"]
            with self.assertRaisesRegex(ValueError, "parent_input"):
                self.resolve(spec, resolver)
            resolver.prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
