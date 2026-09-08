from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import validate_registry

ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "context-fabric/duplicate-structure-levels"
ARGONAUTICA_ID = "canonical-greeklit-tlg0001-tlg001-perseus-grc2-1-62c8ed02"
RUNTIME_SNAPSHOTS = (
    "plugins/context-fabric/uv.lock",
    "plugins/perseus/runtime-constraints.txt",
    "plugins/sefaria/runtime-constraints.txt",
    "plugins/sedra/uv.lock",
    "verification/mcp-smoke/uv.lock",
)


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, document) -> None:
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )


class ResourceMemberVerificationPromotionReviewRed2Tests(unittest.TestCase):
    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(ROOT / "registry", root / "registry")
        shutil.copytree(ROOT / ".github" / "workflows", root / ".github" / "workflows")
        (root / "tests").mkdir()
        shutil.copy2(ROOT / "tests" / "test_generation.py", root / "tests" / "test_generation.py")
        for relative in RUNTIME_SNAPSHOTS:
            source = ROOT / relative
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return root

    def test_member_issue_reference_cannot_target_resource_impact_definition(self):
        root = self.make_root()
        resources = _load_yaml(root / "registry/resources.yaml")
        greek = next(
            item for item in resources["resources"] if item["id"] == "greek_literature"
        )
        issue = next(
            item
            for item in greek["verification"]["known_issues"]
            if item["id"] == ISSUE_ID
        )
        issue["impact"] = "resource"
        _write_yaml(root / "registry/resources.yaml", resources)

        index = _load_yaml(root / "registry/collections/greek_literature.yaml")
        argonautica = next(item for item in index["members"] if item["id"] == ARGONAUTICA_ID)
        self.assertIn(
            ISSUE_ID,
            {ref["issue_id"] for ref in argonautica["verification"].get("known_issues", [])},
        )

        errors = validate_registry(root)
        self.assertTrue(
            any(
                f"member[{ARGONAUTICA_ID}].verification.known_issues" in error
                and "impact" in error.casefold()
                and "member" in error.casefold()
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
