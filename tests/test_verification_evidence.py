from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import ROOT, validate_registry


class VerificationEvidenceTests(unittest.TestCase):
    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(ROOT / "registry", root / "registry")
        workflows = root / ".github" / "workflows"
        workflows.parent.mkdir(parents=True)
        shutil.copytree(ROOT / ".github/workflows", workflows)
        (root / "tests").mkdir()
        shutil.copy2(ROOT / "tests/test_generation.py", root / "tests/test_generation.py")
        return root

    def load_yaml(self, root: Path, relative_path: str):
        return yaml.safe_load((root / relative_path).read_text(encoding="utf-8"))

    def write_yaml(self, root: Path, relative_path: str, doc) -> None:
        (root / relative_path).write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def mutate_check(self, root: Path, check_id: str, mutate) -> None:
        doc = self.load_yaml(root, "registry/verification-checks.yaml")
        check = next(item for item in doc["checks"] if item["id"] == check_id)
        mutate(check)
        self.write_yaml(root, "registry/verification-checks.yaml", doc)

    def test_canonical_check_catalog_exists_and_registry_is_valid(self):
        self.assertTrue((ROOT / "registry/verification-checks.yaml").is_file())
        self.assertEqual(validate_registry(), [])

    def test_plugin_client_evidence_uses_stable_check_ids_not_free_form_tests(self):
        plugins = self.load_yaml(ROOT, "registry/plugins.yaml")["plugins"]
        for plugin in plugins:
            for client_id, evidence in plugin["verification"]["clients"].items():
                self.assertNotIn("tests", evidence, f"{plugin['id']}:{client_id}")
                self.assertTrue(evidence.get("checks"), f"{plugin['id']}:{client_id}")
                for check in evidence["checks"]:
                    self.assertRegex(check["check_id"], r"^[a-z0-9-]+/[a-z0-9-]+$")
                    self.assertTrue(check.get("inputs"), check)

    def test_nonexistent_check_id_is_rejected(self):
        root = self.make_root()
        plugins = self.load_yaml(root, "registry/plugins.yaml")
        plugins["plugins"][0]["verification"]["clients"]["codex"]["checks"][0][
            "check_id"
        ] = "mcp-live/does-not-exist"
        self.write_yaml(root, "registry/plugins.yaml", plugins)

        errors = validate_registry(root)
        self.assertTrue(any("references missing verification check" in error for error in errors), errors)

    def test_check_contract_must_match_plugin_client_and_transport(self):
        root = self.make_root()
        plugins = self.load_yaml(root, "registry/plugins.yaml")
        # Reuse a real check from another client/plugin; referential integrity alone
        # must not be enough to justify this evidence record.
        plugins["plugins"][0]["verification"]["clients"]["codex"]["checks"][0][
            "check_id"
        ] = "mcp-live/perseus-codex"
        self.write_yaml(root, "registry/plugins.yaml", plugins)

        errors = validate_registry(root)
        self.assertTrue(any("does not match evidence contract" in error for error in errors), errors)

    def test_verified_client_requires_verified_level_executable_evidence(self):
        root = self.make_root()
        plugins = self.load_yaml(root, "registry/plugins.yaml")
        candidate = plugins["plugins"][0]
        codex = candidate["verification"]["clients"]["codex"]
        codex["checks"] = copy.deepcopy(candidate["verification"]["clients"]["claude"]["checks"])
        self.write_yaml(root, "registry/plugins.yaml", plugins)

        errors = validate_registry(root)
        self.assertTrue(
            any("status 'verified' exceeds strongest executable evidence" in error for error in errors),
            errors,
        )

    def test_legacy_free_form_test_record_is_rejected_by_schema(self):
        root = self.make_root()
        plugins = self.load_yaml(root, "registry/plugins.yaml")
        evidence = plugins["plugins"][0]["verification"]["clients"]["claude"]
        evidence["tests"] = [{"name": "free form claim", "kind": "deterministic"}]
        evidence.pop("checks", None)
        self.write_yaml(root, "registry/plugins.yaml", plugins)

        errors = validate_registry(root)
        self.assertTrue(any("plugins.yaml" in error and "checks" in error for error in errors), errors)

    def test_nonexistent_unittest_target_is_rejected(self):
        root = self.make_root()
        self.mutate_check(
            root,
            "manifest/context-fabric-claude",
            lambda check: check["executor"].update(
                {"target": "tests.test_generation.MarketplaceGenerationTests.test_does_not_exist"}
            ),
        )

        errors = validate_registry(root)
        self.assertTrue(any("unittest target" in error and "not executable" in error for error in errors), errors)

    def test_nonexistent_actions_job_is_rejected(self):
        root = self.make_root()
        self.mutate_check(
            root,
            "mcp-live/context-fabric-codex",
            lambda check: check["executor"].update({"job": "does-not-exist"}),
        )

        errors = validate_registry(root)
        self.assertTrue(any("missing workflow job 'does-not-exist'" in error for error in errors), errors)

    def test_actions_matrix_selector_must_be_executable(self):
        root = self.make_root()
        self.mutate_check(
            root,
            "mcp-live/context-fabric-codex",
            lambda check: check["executor"].update({"matrix": {"plugin": "does-not-exist"}}),
        )

        errors = validate_registry(root)
        self.assertTrue(any("matrix selector" in error and "does-not-exist" in error for error in errors), errors)

    def test_live_workflow_reruns_when_canonical_verification_claims_change(self):
        workflow = (ROOT / ".github/workflows/external-mcp-smoke.yml").read_text(encoding="utf-8")
        for path in (
            "registry/plugins.yaml",
            "registry/verification-checks.yaml",
            "registry/schema/plugins.schema.json",
            "registry/schema/verification-checks.schema.json",
        ):
            self.assertIn(f'"{path}"', workflow, path)


if __name__ == "__main__":
    unittest.main()
