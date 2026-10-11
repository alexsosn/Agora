"""#251 RED — parse real pinned release ZIP layout without installing corpus."""
from __future__ import annotations

import io
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.probe_tf_release_asset import inspect_zip, PINNED_RELEASE_ASSETS


def zip_fixture(entries: dict[str, bytes], *, symlink: bool = False) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for name, payload in entries.items():
            if symlink:
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, payload)
            else:
                archive.writestr(name, payload)
    return data.getvalue()


class PinnedReleaseLayoutTests(unittest.TestCase):
    def inspect(self, blob: bytes, **kwargs):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "asset.zip"
            path.write_bytes(blob)
            return inspect_zip(path, **kwargs)

    def test_traces_real_tf_warp_from_member_names_only(self):
        report = self.inspect(zip_fixture({
            "tf/1.0/otype.tf": b"@node",
            "tf/1.0/oslots.tf": b"@edge",
            "tf/1.0/lex.tf": b"@node",
            "app/config.yaml": b"test",
        }))
        self.assertEqual(["tf/1.0"], report["tf_roots"])
        self.assertEqual(4, report["members"])
        self.assertEqual(1, report["warp_roots"])
        self.assertEqual(len(b"@node@edge@nodetest"), report["declared_bytes"])

    def test_multi_root_is_reported_not_silently_selected(self):
        report = self.inspect(zip_fixture({
            "a/otype.tf": b"a", "a/oslots.tf": b"b",
            "b/otype.tf": b"c", "b/oslots.tf": b"d",
        }))
        self.assertEqual(["a", "b"], report["tf_roots"])
        self.assertEqual(2, report["warp_roots"])

    def test_missing_warp_and_split_pairs_cannot_pass_probe(self):
        for members in (
            {"tf/1.0/otype.tf": b"x"},
            {"a/otype.tf": b"a", "b/oslots.tf": b"b"},
            {"app/config.yaml": b"y"},
        ):
            with self.subTest(members=members), self.assertRaisesRegex(ValueError, "warp"):
                self.inspect(zip_fixture(members))

    def test_unsafe_and_duplicate_paths_fail_before_extraction(self):
        for name in ("../otype.tf", "/tf/otype.tf", "C:/tf/otype.tf",
                     "tf/../otype.tf", "tf\\..\\otype.tf"):
            with self.subTest(name=name), self.assertRaises((ValueError, RuntimeError)):
                self.inspect(zip_fixture({
                    name: b"malicious", "tf/otype.tf": b"x", "tf/oslots.tf": b"y"
                }))
        with self.assertRaisesRegex(ValueError, "noncanonical"):
            self.inspect(zip_fixture({
                "tf/otype.tf": b"x", "tf/oslots.tf": b"y",
                "tf//otype.tf": b"z",
            }))
        # ZIP central directories may legally repeat a member name; unlike
        # a Python dict fixture, constructing the ZIP manually preserves it.
        duplicate = io.BytesIO()
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr("tf/otype.tf", b"first")
            archive.writestr("tf/oslots.tf", b"slots")
            archive.writestr("tf/otype.tf", b"second")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.inspect(duplicate.getvalue())

    def test_symlink_and_declared_budgets_fail(self):
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.inspect(zip_fixture({
                "tf/otype.tf": b"o",
                "tf/oslots.tf": b"s",
                "tf/link.tf": b"../secret",
            }, symlink=True))
        with self.assertRaisesRegex(ValueError, "member"):
            self.inspect(zip_fixture({
                "tf/otype.tf": b"o", "tf/oslots.tf": b"s", "tf/a.tf": b"a",
            }), max_members=2)
        with self.assertRaisesRegex(ValueError, "expanded"):
            self.inspect(zip_fixture({
                "tf/otype.tf": b"o", "tf/oslots.tf": b"s",
            }), max_expanded_bytes=1)

    def test_tagged_release_asset_identities_are_immutable(self):
        self.assertEqual(
            {
                "complete.zip": ("1ea4488202d1e9fbc008abaabff14f220328118fc52bed3a06a2d331b145bb7d", 9643332),
                "tf-1.0.zip": ("d2dfad7e643699617a9493b9f5d724868f8027dd5f2e88bd558451e3e7819b7a", 9632449),
            },
            {name: (v["sha256"], v["size"]) for name, v in PINNED_RELEASE_ASSETS.items()},
        )


if __name__ == "__main__":
    unittest.main()
