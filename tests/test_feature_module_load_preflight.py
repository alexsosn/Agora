from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.load_safety import compile_budget_bytes, compile_timeout_seconds
from agora_context_fabric.resolver import PreparedCorpus, PreparedFeatureModule
from agora_context_fabric.service import ContextFabricService


class _Store:
    min_free_bytes = 6 * 1024**3


class _Resolver:
    def __init__(self, prepared: PreparedCorpus):
        self.prepared = prepared
        self.store = _Store()

    def prepare_with_modules(self, resource_id: str, **_kwargs) -> PreparedCorpus:
        assert resource_id == self.prepared.resource_id
        return self.prepared


class FeatureModuleLoadPreflightTests(unittest.TestCase):
    @staticmethod
    def _service(root: Path, *, warm: bool = False) -> tuple[ContextFabricService, Path]:
        overlay = root / "cache" / "overlays" / "bhsa" / ("a" * 40) / "combo"
        overlay.mkdir(parents=True)
        (overlay / "otype.tf").write_text("@node\n\n1\tword\n", encoding="utf-8")
        (overlay / "oslots.tf").write_text("@edge\n\n1\t1\n", encoding="utf-8")
        (overlay / "actor.tf").write_text("@node\n\n1\tactor\n", encoding="utf-8")
        if warm:
            marker = overlay / ".cfm" / "test-v1" / "meta.json"
            marker.parent.mkdir(parents=True)
            marker.write_text("{}", encoding="utf-8")

        module = PreparedFeatureModule(
            resource_id="bhsa-actor",
            parent_resource_id="bhsa",
            module_path="example/actor/tf",
            relative_path="tf/c",
            path=root / "module",
            source_revision="b" * 40,
        )
        prepared = PreparedCorpus(
            resource_id="bhsa",
            member_id=None,
            logical_name="bhsa@c+bhsa-actor",
            relative_path="tf/c",
            path=overlay,
            version="c",
            source_revision="a" * 40,
            modules=(module,),
        )
        parent_cost = {
            "scope": "resource",
            "source_size_mb": 165,
            "compiled_size_mb": 866,
            "total_cache_mb": 1100,
            "first_load_seconds": 630,
            "measurement": {
                "checked_at": "2026-09-04",
                "agora_revision": "bf5fb918d513fcf859bc925a10922e841b777b98",
                "environment": "historical fixture",
                "evidence": "https://github.com/alexsosn/Agora/issues/38",
            },
        }
        catalog = Catalog(
            [
                ResourceSpec(
                    id="bhsa",
                    name="BHSA fixture",
                    plugin="context-fabric",
                    provider="context-fabric",
                    kind="corpus",
                    repository="example/bhsa",
                    languages=("hebrew",),
                    disciplines=("biblical-studies",),
                    load_cost=parent_cost,
                )
            ]
        )
        service = ContextFabricService(
            catalog,
            _Resolver(prepared),
            object(),
            cold_compiler=object(),
            cfm_version="test-v1",
        )
        return service, overlay

    def test_prepare_discloses_cold_overlay_before_full_compile(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, overlay = self._service(Path(tmp))
            result = service.prepare("bhsa", version="c", modules=["bhsa-actor"])

            preflight = result["load_preflight"]
            source_bytes = sum(path.stat().st_size for path in overlay.glob("*.tf"))
            self.assertEqual(preflight["cache_kind"], "overlay")
            self.assertEqual(preflight["module_order"], ["bhsa-actor"])
            self.assertEqual(preflight["module_order_semantics"], "ordered-last-wins")
            self.assertFalse(preflight["exact_combination_warm"])
            self.assertTrue(preflight["full_compile_required"])
            self.assertEqual(preflight["source_bytes"], source_bytes)
            self.assertEqual(
                preflight["compile_budget_bytes"],
                compile_budget_bytes(source_bytes),
            )
            self.assertEqual(
                preflight["compile_timeout_seconds"],
                compile_timeout_seconds(),
            )
            self.assertEqual(preflight["min_free_bytes"], 6 * 1024**3)
            self.assertEqual(preflight["cost_expectation"], "parent-scale-possible")
            self.assertEqual(preflight["parent_historical_load_cost"]["compiled_size_mb"], 866)
            self.assertEqual(preflight["parent_historical_load_cost"]["first_load_seconds"], 630)

    def test_prepare_reports_exact_overlay_warmth(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _overlay = self._service(Path(tmp), warm=True)
            preflight = service.prepare(
                "bhsa", version="c", modules=["bhsa-actor"]
            )["load_preflight"]
            self.assertTrue(preflight["exact_combination_warm"])
            self.assertFalse(preflight["full_compile_required"])

    def test_user_workflow_requires_preflight_for_new_module_combinations(self):
        skill = (
            ROOT / "plugins/context-fabric/skills/context-fabric-research/SKILL.md"
        ).read_text(encoding="utf-8")
        mcp_tools = (
            ROOT / "plugins/context-fabric/src/agora_context_fabric/mcp_tools.py"
        ).read_text(encoding="utf-8")
        cache_guide = (ROOT / "wiki/guides/context-fabric-cache.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((skill, mcp_tools, cache_guide)).lower()
        self.assertIn("load_preflight", combined)
        self.assertIn("parent-scale", combined)
        self.assertIn("ordered-last-wins", combined)
        self.assertIn("1.14", combined)
        self.assertIn("7.5", combined)


if __name__ == "__main__":
    unittest.main()
