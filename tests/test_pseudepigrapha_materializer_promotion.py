from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "materializers.yaml"
INSTALL_WORKFLOW = ROOT / ".github" / "workflows" / "materializer-install.yml"
EXPECTED_REF = "317e960e05ca7f36f35a11fcf567285312951095"


def _entry() -> dict:
    document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return next(item for item in document["plugins"] if item["id"] == "pseudepigrapha-tf")


class PseudepigraphaMaterializerPromotionRedTests(unittest.TestCase):
    def test_stable_registry_points_at_verified_v020_release(self):
        plugin = _entry()

        self.assertEqual(plugin["version"], "0.2.0")
        self.assertEqual(plugin["ref"], EXPECTED_REF)
        self.assertEqual(len(plugin["ref"]), 40)
        self.assertEqual(plugin["repository"], "alexsosn/Pseudepigrapha-TF")
        self.assertEqual(
            plugin["release_tracking"],
            {
                "mode": "github-releases",
                "channel": "stable",
                "tag_prefix": "v",
            },
        )
        self.assertEqual(plugin["materializers"], ["ocp-text-fabric"])

    def test_install_smoke_compares_distribution_to_registry_version(self):
        workflow = INSTALL_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("distributions['pseudepigrapha-tf'] == '0.1.0'", workflow)
        self.assertIn("distributions['pseudepigrapha-tf'] == plugin['version']", workflow)


if __name__ == "__main__":
    unittest.main()
