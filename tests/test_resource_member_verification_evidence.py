from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from scripts.validate_registry import validate_registry

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_SCHEMA = ROOT / "registry/schema/resources.schema.json"
CHECK_SCHEMA = ROOT / "registry/schema/verification-checks.schema.json"


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, document) -> None:
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )


def _schema_errors(schema_path: Path, document) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return [error.message for error in Draft202012Validator(schema).iter_errors(document)]


def _direct_check(
    check_id: str,
    *,
    resource_id: str,
    member_id: str | None = None,
    claims: tuple[str, ...] = ("materialization", "load", "representative-content"),
):
    subject = {"type": "resource", "resource_id": resource_id}
    if member_id is not None:
        subject = {
            "type": "collection-member",
            "resource_id": resource_id,
            "member_id": member_id,
        }
    return {
        "id": check_id,
        "kind": "live",
        "plugin": "context-fabric",
        "provider": "context-fabric",
        "evidence_level": "community",
        "subject": subject,
        "claims": list(claims),
        "executor": {
            "type": "unittest",
            "target": (
                "tests.test_generation.MarketplaceGenerationTests."
                "test_context_fabric_claude_mcp_uses_plugin_root"
            ),
        },
    }


class ResourceMemberVerificationEvidenceRed1Tests(unittest.TestCase):
    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(ROOT / "registry", root / "registry")
        shutil.copytree(ROOT / ".github" / "workflows", root / ".github" / "workflows")
        (root / "tests").mkdir()
        shutil.copy2(ROOT / "tests" / "test_generation.py", root / "tests" / "test_generation.py")
        return root

    def test_resource_schema_accepts_evidence_references(self):
        resources = _load_yaml(ROOT / "registry/resources.yaml")
        bhsa = next(item for item in resources["resources"] if item["id"] == "bhsa")
        bhsa = dict(bhsa)
        bhsa["verification"] = {
            **bhsa["verification"],
            "evidence": [{"check_id": "resource-load/bhsa"}],
        }
        document = {"schema_version": 1, "resources": [bhsa]}
        self.assertEqual(_schema_errors(RESOURCE_SCHEMA, document), [])

    def test_direct_resource_check_schema_needs_no_client_or_transport(self):
        document = {
            "schema_version": 1,
            "checks": [_direct_check("resource-load/bhsa", resource_id="bhsa")],
        }
        self.assertEqual(_schema_errors(CHECK_SCHEMA, document), [])

    def test_direct_resource_subject_accepts_mixed_case_canonical_ids(self):
        document = {
            "schema_version": 1,
            "checks": [
                _direct_check(
                    "resource-load/tlhdig-fixture",
                    resource_id="TLHdig-TF",
                )
            ],
        }
        self.assertEqual(_schema_errors(CHECK_SCHEMA, document), [])

    def test_client_check_cannot_satisfy_resource_evidence(self):
        root = self.make_root()
        resources = _load_yaml(root / "registry/resources.yaml")
        bhsa = next(item for item in resources["resources"] if item["id"] == "bhsa")
        bhsa["verification"]["evidence"] = [
            {"check_id": "mcp-live/context-fabric-codex"}
        ]
        _write_yaml(root / "registry/resources.yaml", resources)

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource bhsa.verification.evidence" in error
                and "resource" in error.casefold()
                and "check" in error.casefold()
                for error in errors
            ),
            errors,
        )

    def test_resource_evidence_check_must_target_exact_resource(self):
        root = self.make_root()
        checks = _load_yaml(root / "registry/verification-checks.yaml")
        checks["checks"].append(
            _direct_check("resource-load/bhsa-wrong-target", resource_id="cuc")
        )
        _write_yaml(root / "registry/verification-checks.yaml", checks)

        resources = _load_yaml(root / "registry/resources.yaml")
        bhsa = next(item for item in resources["resources"] if item["id"] == "bhsa")
        bhsa["verification"]["evidence"] = [
            {"check_id": "resource-load/bhsa-wrong-target"}
        ]
        _write_yaml(root / "registry/resources.yaml", resources)

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource bhsa.verification.evidence" in error
                and "subject" in error.casefold()
                and "cuc" in error
                for error in errors
            ),
            errors,
        )

    def test_member_evidence_check_must_target_exact_member(self):
        root = self.make_root()
        index = _load_yaml(root / "registry/collections/greek_literature.yaml")
        iliad = next(
            member
            for member in index["members"]
            if member["id"] == "canonical-greeklit-tlg0012-tlg001-perseus-grc2-1-67402e1a"
        )
        argonautica_id = "canonical-greeklit-tlg0001-tlg001-perseus-grc2-1-62c8ed02"
        iliad["verification"]["evidence"] = [
            {"check_id": "member-load/iliad-wrong-target"}
        ]
        _write_yaml(root / "registry/collections/greek_literature.yaml", index)

        checks = _load_yaml(root / "registry/verification-checks.yaml")
        checks["checks"].append(
            _direct_check(
                "member-load/iliad-wrong-target",
                resource_id="greek_literature",
                member_id=argonautica_id,
            )
        )
        _write_yaml(root / "registry/verification-checks.yaml", checks)

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "member[canonical-greeklit-tlg0012-tlg001-perseus-grc2-1-67402e1a]"
                in error
                and "subject" in error.casefold()
                and argonautica_id in error
                for error in errors
            ),
            errors,
        )

    def test_resource_check_definition_rejects_missing_subject_resource(self):
        root = self.make_root()
        checks = _load_yaml(root / "registry/verification-checks.yaml")
        checks["checks"].append(
            _direct_check("resource-load/missing-fixture", resource_id="DoesNotExist")
        )
        _write_yaml(root / "registry/verification-checks.yaml", checks)

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource-load/missing-fixture" in error
                and "DoesNotExist" in error
                and "missing" in error.casefold()
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
