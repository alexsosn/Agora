from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import ROOT, validate_registry


class ProviderHealthStateTests(unittest.TestCase):
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

    def set_health(self, root: Path, status: str, *, with_evidence: bool) -> None:
        doc = self.load_yaml(root, "registry/providers.yaml")
        provider = next(item for item in doc["providers"] if item["id"] == "context-fabric")
        provider["health"]["status"] = status
        if with_evidence:
            provider["health"]["evidence"] = [{"check_id": "mcp-live/context-fabric-codex"}]
        else:
            provider["health"].pop("evidence", None)
        self.write_yaml(root, "registry/providers.yaml", doc)

    def test_degraded_requires_provider_scoped_live_evidence(self):
        root = self.make_root()
        self.set_health(root, "degraded", with_evidence=False)
        errors = validate_registry(root)
        self.assertTrue(
            any("provider context-fabric.health" in error and "degraded requires at least one live evidence check" in error for error in errors),
            errors,
        )

    def test_unavailable_requires_provider_scoped_live_evidence(self):
        root = self.make_root()
        self.set_health(root, "unavailable", with_evidence=False)
        errors = validate_registry(root)
        self.assertTrue(
            any("provider context-fabric.health" in error and "unavailable requires at least one live evidence check" in error for error in errors),
            errors,
        )

    def test_unknown_allows_no_operational_evidence(self):
        root = self.make_root()
        self.set_health(root, "unknown", with_evidence=False)
        self.assertEqual(validate_registry(root), [])

    def test_registry_docs_define_all_provider_health_states(self):
        text = (ROOT / "registry/README.md").read_text(encoding="utf-8")
        for status in ("unknown", "observed-operational", "degraded", "unavailable"):
            self.assertIn(f"`{status}`", text)
        self.assertIn("recorded operational observation", text)
        self.assertIn("not automatic real-time monitoring", text)


if __name__ == "__main__":
    unittest.main()
