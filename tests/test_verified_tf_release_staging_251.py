"""#251 RED: verify native Text-Fabric ZIP feature staging without cache publication."""
from __future__ import annotations

import hashlib
import io
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.release_archive import staged_verified_tf_zip

FEATURES = {
    "otype.tf": b"@node\n1\tword\n",
    "oslots.tf": b"@edge\n1\t1\n",
    "otext.tf": b"@config\n@fmt=text\n",
    "lex.tf": b"@node\n1\tMLK\n",
}


def zip_bytes(entries, *, link=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in entries:
            if name == link:
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(info, content)
            else:
                z.writestr(name, content)
    return output.getvalue()


class VerifiedTFReleaseStaging251Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)

    def stage(self, entries, **kwargs):
        binary = zip_bytes(entries)
        path = self.parent / "input.zip"
        path.write_bytes(binary)
        return staged_verified_tf_zip(
            path, expected_sha256=hashlib.sha256(binary).hexdigest(),
            staging_parent=self.parent, **kwargs,
        )

    def test_native_flat_root_stages_only_tf_features_and_cleans(self):
        with self.stage(list(FEATURES.items())) as staged:
            self.assertEqual(set(FEATURES), {p.name for p in staged.iterdir()})
            self.assertEqual((staged / "otype.tf").read_bytes(), FEATURES["otype.tf"])
            self.assertFalse(any(p.is_symlink() for p in staged.iterdir()))
            staged_path = staged
        self.assertFalse(staged_path.exists())
        self.assertEqual(["input.zip"], sorted(p.name for p in self.parent.iterdir()))

    def test_stock_nested_root_can_be_discovered_not_guessed(self):
        entries = [("alexsosn/Pseudepigrapha-TF/tf/1.0/" + k, v) for k, v in FEATURES.items()]
        entries += [("alexsosn/Pseudepigrapha-TF/app/config.yaml", b"not a TF feature")]
        with self.stage(entries) as staged:
            self.assertEqual(set(FEATURES), {p.name for p in staged.iterdir()})

    def test_sha256_mismatch_fails_before_stage_creation(self):
        binary = zip_bytes(list(FEATURES.items()))
        path = self.parent / "input.zip"
        path.write_bytes(binary)
        with self.assertRaisesRegex(ValueError, "sha256"):
            with staged_verified_tf_zip(
                path, expected_sha256="0" * 64, staging_parent=self.parent,
            ):
                self.fail("must not yield unverified files")
        self.assertEqual(["input.zip"], sorted(p.name for p in self.parent.iterdir()))

    def test_refuses_missing_or_multiple_warp_roots(self):
        for entries in (
            [("otype.tf", FEATURES["otype.tf"])],
            [("a/otype.tf", FEATURES["otype.tf"]), ("b/oslots.tf", FEATURES["oslots.tf"])],
            [(f"a/{k}", v) for k, v in FEATURES.items()]
            + [(f"b/{k}", v) for k, v in FEATURES.items()],
        ):
            with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, "warp"):
                with self.stage(entries):
                    self.fail("inconsistent root should fail")

    def test_refuses_traversal_symlink_and_duplicate_feature_names(self):
        threats = (
            ([("../escape.tf", b"evil")] + list(FEATURES.items()), None),
            ([("C:/malware.tf", b"evil")] + list(FEATURES.items()), None),
            ([("tf\\..\\evil.tf", b"evil")] + list(FEATURES.items()), None),
            (list(FEATURES.items()) + [("evil.tf", b"../target")], "evil.tf"),
            (list(FEATURES.items()) + [("otype.tf", FEATURES["otype.tf"])], None),
            (list(FEATURES.items()) + [("OTYPE.tf", FEATURES["otype.tf"])], None),
        )
        for entries, link in threats:
            with self.subTest(entries=entries):
                data = zip_bytes(entries, link=link)
                archive = self.parent / "input.zip"
                archive.write_bytes(data)
                with self.assertRaises(ValueError):
                    with staged_verified_tf_zip(
                        archive, expected_sha256=hashlib.sha256(data).hexdigest(),
                        staging_parent=self.parent,
                    ):
                        self.fail("unsafe archive staged")

    def test_declared_and_real_size_and_member_limits(self):
        entries = list(FEATURES.items())
        for limits in (
            {"max_members": 3},
            {"max_uncompressed_bytes": 10},
            {"max_archive_bytes": 10},
        ):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                with self.stage(entries, **limits):
                    self.fail("budget-breaching archive staged")

    def test_pinned_real_asset_staging_workflow_is_not_a_corpus_loader(self):
        workflow = (
            ROOT / ".github/workflows/pseudepigrapha-release-staging.yml"
        ).read_text(encoding="utf-8")
        for required in (
            "PINNED_RELEASE_ASSETS.items()",
            "for name, pinned in sorted(PINNED_RELEASE_ASSETS.items())",
            "staged_verified_tf_zip",
            "test_verified_tf_release_staging_251",
            "no corpus cache publication",
            "persist-credentials: false",
        ):
            self.assertIn(required, workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("latest", workflow.lower())

    def test_invalid_utf8_or_bad_tf_header_rejected_and_cleaned(self):
        for payload in (b"@node\n1\t\xff\n", b"plain file\n"):
            with self.subTest(payload=payload):
                entries = list(FEATURES.items())
                entries[-1] = ("lex.tf", payload)
                with self.assertRaises(ValueError):
                    with self.stage(entries):
                        self.fail("malformed TF was staged")
                self.assertEqual(["input.zip"], sorted(p.name for p in self.parent.iterdir()))


if __name__ == "__main__":
    unittest.main()
