from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MEASURED_RESOURCE_IDS = {"bhsa", "cuc", "TLHdig-TF", "greek_literature"}


class LoadCostReviewRegressionTests(unittest.TestCase):
    def test_seeded_measurements_disclaim_current_machine_portability(self) -> None:
        document = yaml.safe_load((ROOT / "registry/resources.yaml").read_text(encoding="utf-8"))
        resources = {item["id"]: item for item in document["resources"]}

        for resource_id in sorted(MEASURED_RESOURCE_IDS):
            with self.subTest(resource_id=resource_id):
                notes = resources[resource_id]["load_cost"].get("notes", "").lower()
                self.assertIn("historical", notes)
                self.assertIn("current-machine", notes)
                self.assertIn("may differ", notes)


if __name__ == "__main__":
    unittest.main()
