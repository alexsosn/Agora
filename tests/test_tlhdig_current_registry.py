from __future__ import annotations

from pathlib import Path
import unittest

import yaml

from scripts.generate_context_fabric_catalog import check

ROOT = Path(__file__).resolve().parents[1]


def _resource(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(item for item in document["resources"] if item["id"] == "TLHdig-TF")


class TLHdigCurrentRegistryTests(unittest.TestCase):
    def test_tlhdig_tracks_current_upstream_artifact_without_revision_pin(self):
        source = _resource(ROOT / "registry" / "resources.yaml")
        upstream = source["upstream"]
        self.assertNotIn("ref", upstream)
        self.assertEqual(upstream["repository"], "alexsosn/TLHdig-TF")
        self.assertEqual(upstream["tf_path"], "tf/0.4.0")
        self.assertNotIn("tf/0.1.0", source["acquisition"].get("notes", ""))

    def test_runtime_catalog_is_fresh_after_tlhdig_path_change(self):
        self.assertEqual(check(ROOT), [])
        runtime = _resource(ROOT / "plugins" / "context-fabric" / "resources" / "catalog.yaml")
        self.assertEqual(runtime["upstream"]["tf_path"], "tf/0.4.0")

    def test_legacy_load_cost_is_not_presented_as_current_040_measurement(self):
        source = _resource(ROOT / "registry" / "resources.yaml")
        load_cost = source.get("load_cost")
        if load_cost is None:
            return
        notes = load_cost.get("notes", "")
        self.assertIn("tf/0.1.0", notes)
        self.assertIn("tf/0.4.0", notes)
        self.assertIn("does not describe", notes.lower())


if __name__ == "__main__":
    unittest.main()
