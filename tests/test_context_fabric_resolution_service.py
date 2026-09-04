from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.resolution_service import ResolutionAwareContextFabricService
from agora_context_fabric.resolver import PreparedCorpus, PreparedFeatureModule


class ResolutionServiceTests(unittest.TestCase):
    def test_prepared_result_surfaces_cached_freshness_for_parent_and_modules(self):
        prepared = PreparedCorpus(
            resource_id="fixture",
            member_id=None,
            logical_name="fixture+addon",
            relative_path="tf/1.0",
            path=Path("/tmp/fixture"),
            version="1.0",
            source_revision="a" * 40,
            source_revision_verified=False,
            resolution="cached",
            modules=(
                PreparedFeatureModule(
                    resource_id="addon",
                    parent_resource_id="fixture",
                    module_path="example/addon/tf",
                    relative_path="tf/1.0",
                    path=Path("/tmp/addon"),
                    source_revision="b" * 40,
                    source_revision_verified=True,
                    resolution="cached",
                ),
            ),
        )

        result = ResolutionAwareContextFabricService._prepared_dict(
            prepared,
            cache_residency="evictable",
        )

        self.assertEqual(result["resolution"], "cached")
        self.assertFalse(result["source_revision_verified"])
        self.assertEqual(result["modules"][0]["resolution"], "cached")
        self.assertTrue(result["modules"][0]["source_revision_verified"])


if __name__ == "__main__":
    unittest.main()
