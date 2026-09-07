from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_release_status.py"
PLAN = ROOT / "wiki" / "releases" / "v0.1-plan-active.md"
WIKI_INDEX = ROOT / "wiki" / "README.md"
IMPLEMENTATION_DETAILS = ROOT / "wiki" / "architecture" / "ref-implementation-details.md"
BEGIN = "<!-- BEGIN GENERATED V0.1 PLUGIN VERIFICATION -->"
END = "<!-- END GENERATED V0.1 PLUGIN VERIFICATION -->"


class ReleaseStatusDocumentationTests(unittest.TestCase):
    def _load_generator(self):
        self.assertTrue(GENERATOR.is_file(), "release-status generator is not implemented")
        spec = importlib.util.spec_from_file_location("agora_release_status_generator", GENERATOR)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "registry").mkdir(parents=True)
        for name in ("v0.1.yaml", "plugins.yaml", "verification-checks.yaml"):
            shutil.copy2(ROOT / "registry" / name, root / "registry" / name)
        plan = root / "wiki" / "releases" / "v0.1-plan-active.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(
            "before\n"
            f"{BEGIN}\nold generated content\n{END}\n"
            "after\n",
            encoding="utf-8",
        )
        return root

    @staticmethod
    def _read_yaml(root: Path, relative: str):
        return yaml.safe_load((root / relative).read_text(encoding="utf-8"))

    @staticmethod
    def _write_yaml(root: Path, relative: str, document) -> None:
        (root / relative).write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def test_generator_script_exists_and_check_accepts_committed_plan(self):
        self.assertTrue(GENERATOR.is_file(), "release-status generator is not implemented")
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_render_is_derived_from_v01_scope_and_exact_registry_statuses(self):
        generator = self._load_generator()
        block = generator.render_verification_block(ROOT)
        scope = self._read_yaml(ROOT, "registry/v0.1.yaml")["required_plugins"]
        plugins = {
            item["id"]: item
            for item in self._read_yaml(ROOT, "registry/plugins.yaml")["plugins"]
        }
        for plugin_id in scope:
            self.assertIn(plugin_id, block)
            self.assertIn(plugins[plugin_id]["verification"]["status"], block)
            for client_id, client in plugins[plugin_id]["verification"]["clients"].items():
                self.assertIn(client_id, block)
                self.assertIn(client["status"], block)

    def test_verified_client_does_not_promote_aggregate_plugin_status(self):
        generator = self._load_generator()
        root = self._make_root()
        plugins = self._read_yaml(root, "registry/plugins.yaml")
        first = plugins["plugins"][0]
        first["verification"]["status"] = "community"
        first["verification"]["clients"]["codex"]["status"] = "verified"
        self._write_yaml(root, "registry/plugins.yaml", plugins)

        block = generator.render_verification_block(root)
        self.assertRegex(block, rf"{first['id']}.*community")
        self.assertNotRegex(block, rf"{first['id']}[^\n]*aggregate[^\n]*verified")

    def test_live_verified_label_requires_canonical_live_verified_check(self):
        generator = self._load_generator()
        root = self._make_root()
        checks = self._read_yaml(root, "registry/verification-checks.yaml")
        target = next(item for item in checks["checks"] if item["id"] == "mcp-live/context-fabric-codex")
        target["kind"] = "deterministic"
        target["evidence_level"] = "community"
        self._write_yaml(root, "registry/verification-checks.yaml", checks)

        block = generator.render_verification_block(root)
        context_fabric_line = next(
            line for line in block.splitlines() if "context-fabric" in line and "codex" in line
        )
        self.assertNotIn("live-verified", context_fabric_line.casefold())
        self.assertNotIn("live verified", context_fabric_line.casefold())

    def test_missing_or_mismatched_referenced_check_fails_closed(self):
        generator = self._load_generator()
        root = self._make_root()
        checks = self._read_yaml(root, "registry/verification-checks.yaml")
        target = next(item for item in checks["checks"] if item["id"] == "mcp-live/context-fabric-codex")
        target["client"] = "claude"
        self._write_yaml(root, "registry/verification-checks.yaml", checks)

        with self.assertRaisesRegex(ValueError, "check|client|mismatch|context-fabric"):
            generator.render_verification_block(root)

    def test_missing_v01_plugin_verification_metadata_fails_closed(self):
        generator = self._load_generator()
        root = self._make_root()
        plugins = self._read_yaml(root, "registry/plugins.yaml")
        plugins["plugins"][0].pop("verification")
        self._write_yaml(root, "registry/plugins.yaml", plugins)

        with self.assertRaisesRegex(ValueError, "verification|context-fabric"):
            generator.render_verification_block(root)

    def test_generation_changes_only_the_bounded_block(self):
        generator = self._load_generator()
        root = self._make_root()
        path = root / "wiki" / "releases" / "v0.1-plan-active.md"
        before = path.read_text(encoding="utf-8")
        expected_prefix, rest = before.split(BEGIN, 1)
        _old, expected_suffix = rest.split(END, 1)

        generator.write(root)
        after = path.read_text(encoding="utf-8")
        actual_prefix, rest = after.split(BEGIN, 1)
        _new, actual_suffix = rest.split(END, 1)
        self.assertEqual(actual_prefix, expected_prefix)
        self.assertEqual(actual_suffix, expected_suffix)

    def test_phase_4_does_not_claim_unscoped_verified_status(self):
        plan = PLAN.read_text(encoding="utf-8")
        self.assertNotIn("**Status: implemented and Verified.**", plan)

    def test_phase_5_is_not_still_next_after_required_skills_exist(self):
        plan = PLAN.read_text(encoding="utf-8")
        self.assertNotIn("**Status: next major implementation phase.**", plan)
        self.assertNotRegex(plan, r"Phase 5 scholarly skills\s+NEXT")

    def test_plan_does_not_claim_all_aggregate_plugin_statuses_are_verified(self):
        plan = PLAN.read_text(encoding="utf-8")
        self.assertNotIn("The current v0.1 plugin statuses in `registry/plugins.yaml` are therefore `verified`.", plan)

    def test_wiki_index_does_not_present_superseded_review_list_as_current_p0(self):
        index = WIKI_INDEX.read_text(encoding="utf-8")
        self.assertNotIn("## Current P0 engineering findings", index)
        self.assertIn("reviews/2026-08-29-review-pr1-pr4.md", index)

    def test_implementation_details_does_not_point_to_completed_work_as_next_priority(self):
        details = IMPLEMENTATION_DETAILS.read_text(encoding="utf-8")
        self.assertNotIn(
            "Context-Fabric snapshot integrity and representative corpus-load evidence among the highest-priority engineering items",
            details,
        )


if __name__ == "__main__":
    unittest.main()
