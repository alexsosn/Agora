"""Registry invariant: a declared `parent-base` ref must equal the parent's pin.

`ContextFabricResolver._check_parent_base` compares a feature module's declared
`parent-base` ref against the revision of the prepared parent by exact (case
insensitive) equality. Nothing previously tied that declared ref to the parent
corpus's own `upstream.ref`, so promoting one without the other left every
generation and validation gate green while `load_corpus(parent, modules=[...])`
failed for every user at run time.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import ROOT, validate_registry

MISMATCH = "must equal parent"
UNPINNED = "to declare an immutable upstream.ref"


class ParentBasePinAlignmentTests(unittest.TestCase):
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
        for relative_path in (
            "plugins/context-fabric/uv.lock",
            "plugins/sedra/uv.lock",
            "plugins/perseus/runtime-constraints.txt",
            "plugins/sefaria/runtime-constraints.txt",
            "verification/mcp-smoke/uv.lock",
        ):
            source = ROOT / relative_path
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return root

    def _load(self, root: Path, relative_path: str):
        return yaml.safe_load((root / relative_path).read_text(encoding="utf-8"))

    def _write(self, root: Path, relative_path: str, document) -> None:
        (root / relative_path).write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _set_parent_pin(self, root: Path, ref: str, resource_id: str = "cuc") -> None:
        document = self._load(root, "registry/resources.yaml")
        resource = next(item for item in document["resources"] if item["id"] == resource_id)
        resource["upstream"]["ref"] = ref
        self._write(root, "registry/resources.yaml", document)

    def _drop_parent_pin(self, root: Path, resource_id: str = "cuc") -> None:
        document = self._load(root, "registry/resources.yaml")
        resource = next(item for item in document["resources"] if item["id"] == resource_id)
        resource["upstream"].pop("ref", None)
        self._write(root, "registry/resources.yaml", document)

    def _set_parent_base(self, root: Path, ref: str, module_id: str = "cuc-burns") -> None:
        document = self._load(root, "registry/feature-modules.yaml")
        module = next(item for item in document["resources"] if item["id"] == module_id)
        for dependency in module["upstream"]["dependencies"]:
            if dependency.get("role") == "parent-base":
                dependency["ref"] = ref
        self._write(root, "registry/feature-modules.yaml", document)

    def _errors(self, root: Path, needle: str) -> list[str]:
        return [error for error in validate_registry(root) if needle in error]

    # --- the regressions this invariant exists to prevent -------------------

    def test_promoting_the_parent_pin_alone_is_rejected(self):
        """A `cuc` promotion that forgets `cuc-burns` must fail validation."""
        root = self.make_root()
        self._set_parent_pin(root, "a" * 40)
        errors = self._errors(root, MISMATCH)
        self.assertTrue(errors, validate_registry(root))
        self.assertTrue(any("cuc-burns" in error for error in errors), errors)

    def test_moving_the_module_parent_base_alone_is_rejected(self):
        """The reverse de-sync must fail too."""
        root = self.make_root()
        self._set_parent_base(root, "b" * 40)
        errors = self._errors(root, MISMATCH)
        self.assertTrue(errors, validate_registry(root))
        self.assertTrue(any("cuc-burns" in error for error in errors), errors)

    def test_parent_base_requires_the_parent_to_be_pinned(self):
        """An exact-equality runtime check against a floating parent is a time bomb."""
        root = self.make_root()
        self._drop_parent_pin(root)
        errors = self._errors(root, UNPINNED)
        self.assertTrue(errors, validate_registry(root))
        self.assertTrue(any("cuc-burns" in error for error in errors), errors)

    # --- guards against over-enforcement -----------------------------------

    def test_the_live_registry_satisfies_the_invariant(self):
        self.assertEqual(validate_registry(), [])

    def test_commit_id_case_is_not_a_mismatch(self):
        """The resolver casefolds before comparing; validation must agree."""
        root = self.make_root()
        document = self._load(root, "registry/feature-modules.yaml")
        module = next(item for item in document["resources"] if item["id"] == "cuc-burns")
        reference = next(
            dependency["ref"]
            for dependency in module["upstream"]["dependencies"]
            if dependency.get("role") == "parent-base"
        )
        self._set_parent_base(root, reference.upper())
        self.assertEqual(self._errors(root, MISMATCH), [])

    def test_modules_without_a_parent_base_dependency_stay_valid(self):
        """21 of 22 feature modules declare no parent-base and have unpinned parents."""
        root = self.make_root()
        self.assertEqual(self._errors(root, UNPINNED), [])
        self.assertEqual(self._errors(root, MISMATCH), [])


if __name__ == "__main__":
    unittest.main()
