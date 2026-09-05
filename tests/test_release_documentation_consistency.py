from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHARED_STATUS_DOCS = (
    "README.md",
    "wiki/README.md",
    "wiki/releases/v0.1-plan-active.md",
    "wiki/architecture/ref-implementation-details.md",
)
SHARED_BEGIN = "<!-- BEGIN AGORA V0.1 STATUS -->"
SHARED_END = "<!-- END AGORA V0.1 STATUS -->"
RESOURCE_BEGIN = "<!-- BEGIN AGORA V0.1 RESOURCE RUNTIME FACTS -->"
RESOURCE_END = "<!-- END AGORA V0.1 RESOURCE RUNTIME FACTS -->"

try:
    from scripts.validate_release_documentation import validate_release_documentation
except ModuleNotFoundError:
    validate_release_documentation = None


class ReleaseDocumentationConsistencyTests(unittest.TestCase):
    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for relative in (
            "registry/plugins.yaml",
            "registry/resources.yaml",
            *SHARED_STATUS_DOCS,
            "wiki/releases/v0.1-scope-frozen.md",
        ):
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        for skill in (ROOT / "plugins").glob("*/skills/*/SKILL.md"):
            relative = skill.relative_to(ROOT)
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(skill, target)
        return root

    def require_validator(self):
        self.assertTrue(
            callable(validate_release_documentation),
            "scripts.validate_release_documentation must expose validate_release_documentation(root)",
        )
        return validate_release_documentation

    def mutate_resource(self, root: Path, resource_id: str, mutate) -> None:
        path = root / "registry/resources.yaml"
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        resource = next(item for item in document["resources"] if item["id"] == resource_id)
        mutate(resource)
        path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def test_high_level_current_status_docs_have_bounded_visible_status_blocks(self):
        for relative in SHARED_STATUS_DOCS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(SHARED_BEGIN, text, relative)
            self.assertIn(SHARED_END, text, relative)
            self.assertLess(text.index(SHARED_BEGIN), text.index(SHARED_END), relative)

    def test_registry_status_mutation_changes_expected_documentation(self):
        validate = self.require_validator()
        root = self.make_root()
        path = root / "registry/plugins.yaml"
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        plugin = next(item for item in document["plugins"] if item["id"] == "context-fabric")
        plugin["verification"]["status"] = "verified"
        path.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        errors = validate(root)
        self.assertTrue(
            any("README.md" in error and "status" in error.lower() for error in errors),
            errors,
        )

    def test_skill_tree_mutation_changes_expected_documentation(self):
        validate = self.require_validator()
        root = self.make_root()
        skill = root / "plugins/context-fabric/skills/new-research/SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("---\nname: new-research\ndescription: test\n---\n", encoding="utf-8")

        errors = validate(root)
        self.assertTrue(
            any("README.md" in error and "skill" in error.lower() for error in errors),
            errors,
        )

    def test_scope_has_bounded_resource_runtime_facts_block(self):
        text = (ROOT / "wiki/releases/v0.1-scope-frozen.md").read_text(encoding="utf-8")
        self.assertIn(RESOURCE_BEGIN, text)
        self.assertIn(RESOURCE_END, text)
        self.assertLess(text.index(RESOURCE_BEGIN), text.index(RESOURCE_END))

    def test_tlhdig_tf_path_mutation_changes_expected_scope_documentation(self):
        validate = self.require_validator()
        root = self.make_root()
        self.mutate_resource(root, "TLHdig-TF", lambda resource: resource["upstream"].__setitem__("tf_path", "tf/9.9.9"))

        errors = validate(root)
        self.assertTrue(
            any("v0.1-scope-frozen.md" in error and "TLHdig" in error for error in errors),
            errors,
        )

    def test_tlhdig_configured_ref_mutation_changes_expected_scope_documentation(self):
        validate = self.require_validator()
        root = self.make_root()
        self.mutate_resource(root, "TLHdig-TF", lambda resource: resource["upstream"].__setitem__("ref", "a" * 40))

        errors = validate(root)
        self.assertTrue(
            any("v0.1-scope-frozen.md" in error and "TLHdig" in error for error in errors),
            errors,
        )

    def test_collection_discovery_mutation_changes_expected_scope_documentation(self):
        validate = self.require_validator()
        root = self.make_root()
        self.mutate_resource(root, "greek_literature", lambda resource: resource["collection"].__setitem__("discovery", "git-tree"))

        errors = validate(root)
        self.assertTrue(
            any("v0.1-scope-frozen.md" in error and "collection" in error.lower() for error in errors),
            errors,
        )

    def test_indexed_collections_reject_stale_normal_git_tree_discovery_prose(self):
        validate = self.require_validator()
        errors = validate(ROOT)
        self.assertTrue(
            any("Git tree" in error and "collection" in error.lower() for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
