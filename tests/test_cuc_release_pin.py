from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

from scripts.generate_context_fabric_catalog import check

ROOT = Path(__file__).resolve().parents[1]

# Immutable commit of upstream CUC release v0.2.8.
CUC_RELEASE_COMMIT = "0408967b1808c1f22c69e299d302b1e7b5e26354"
IMMUTABLE_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _resource(path: Path, resource_id: str = "cuc") -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(item for item in document["resources"] if item["id"] == resource_id)


class CucReleasePinTests(unittest.TestCase):
    def test_cuc_is_pinned_to_an_immutable_release_commit(self):
        upstream = _resource(ROOT / "registry" / "resources.yaml")["upstream"]
        self.assertEqual(upstream["repository"], "DT-UCPH/cuc")
        self.assertEqual(upstream["ref"], CUC_RELEASE_COMMIT)
        self.assertRegex(upstream["ref"], IMMUTABLE_COMMIT)

    def test_cuc_selects_one_concrete_text_fabric_dataset_version(self):
        upstream = _resource(ROOT / "registry" / "resources.yaml")["upstream"]
        self.assertEqual(upstream["tf_path"], "tf/0.2.8")

    def test_pin_is_explained_so_promotion_stays_a_deliberate_decision(self):
        acquisition = _resource(ROOT / "registry" / "resources.yaml")["acquisition"]
        notes = acquisition.get("notes", "")
        self.assertIn("v0.2.8", notes)
        self.assertIn("release", notes.lower())

    def test_runtime_catalog_carries_the_pin(self):
        self.assertEqual(check(ROOT), [])
        runtime = _resource(ROOT / "plugins" / "context-fabric" / "resources" / "catalog.yaml")
        self.assertEqual(runtime["upstream"]["ref"], CUC_RELEASE_COMMIT)
        self.assertEqual(runtime["upstream"]["tf_path"], "tf/0.2.8")


if __name__ == "__main__":
    unittest.main()
