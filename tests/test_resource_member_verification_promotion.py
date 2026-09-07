from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.validate_registry import validate_registry

ROOT = Path(__file__).resolve().parents[1]
ISSUE_ID = "context-fabric/duplicate-structure-levels"
ILIAD_ID = "canonical-greeklit-tlg0012-tlg001-perseus-grc2-1-67402e1a"
ARGONAUTICA_ID = "canonical-greeklit-tlg0001-tlg001-perseus-grc2-1-62c8ed02"
POSITIVE_CLAIMS = ("materialization", "load", "representative-content")
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


def _direct_check(
    check_id: str,
    *,
    resource_id: str,
    claims: tuple[str, ...],
    member_id: str | None = None,
    evidence_level: str = "verified",
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
        "evidence_level": evidence_level,
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


class ResourceMemberVerificationPromotionRed2Tests(unittest.TestCase):
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

    def resource(self, root: Path, resource_id: str):
        resources = _load_yaml(root / "registry/resources.yaml")
        return resources, next(
            item for item in resources["resources"] if item["id"] == resource_id
        )

    def member(self, root: Path, resource_id: str, member_id: str):
        index = _load_yaml(root / f"registry/collections/{resource_id}.yaml")
        return index, next(item for item in index["members"] if item["id"] == member_id)

    def add_check(self, root: Path, check) -> None:
        checks = _load_yaml(root / "registry/verification-checks.yaml")
        checks["checks"].append(check)
        _write_yaml(root / "registry/verification-checks.yaml", checks)

    def link_resource_check(self, resource: dict, check_id: str) -> None:
        resource["verification"]["evidence"] = [{"check_id": check_id}]

    def link_member_check(self, member: dict, check_id: str) -> None:
        member["verification"]["evidence"] = [{"check_id": check_id}]

    def set_greek_issue(self, resource: dict, *, severity: str, impact: str) -> None:
        issue = next(
            item
            for item in resource["verification"]["known_issues"]
            if item["id"] == ISSUE_ID
        )
        issue["severity"] = severity
        issue["impact"] = impact

    def test_known_issue_schema_requires_explicit_impact(self):
        schema = json.loads(
            (ROOT / "registry/schema/resources.schema.json").read_text(encoding="utf-8")
        )
        resource = schema["properties"]["resources"]["items"]
        issue = resource["properties"]["verification"]["properties"]["known_issues"]["items"]
        self.assertIn("impact", issue["required"])
        self.assertEqual(issue["properties"]["impact"]["enum"], ["resource", "member"])

    def test_verified_corpus_requires_all_positive_verified_live_claims(self):
        root = self.make_root()
        resources, bhsa = self.resource(root, "bhsa")
        check_id = "resource-load/bhsa-incomplete"
        bhsa["verification"]["status"] = "verified"
        self.link_resource_check(bhsa, check_id)
        _write_yaml(root / "registry/resources.yaml", resources)
        self.add_check(
            root,
            _direct_check(
                check_id,
                resource_id="bhsa",
                claims=("materialization", "load"),
            ),
        )

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource bhsa.verification" in error
                and "representative-content" in error
                for error in errors
            ),
            errors,
        )

    def test_community_resource_remains_valid_without_evidence(self):
        root = self.make_root()
        errors = validate_registry(root)
        self.assertEqual(errors, [])

    def test_verified_member_requires_all_positive_verified_live_claims(self):
        root = self.make_root()
        index, iliad = self.member(root, "greek_literature", ILIAD_ID)
        check_id = "member-load/iliad-incomplete"
        iliad["verification"]["status"] = "verified"
        self.link_member_check(iliad, check_id)
        _write_yaml(root / "registry/collections/greek_literature.yaml", index)
        self.add_check(
            root,
            _direct_check(
                check_id,
                resource_id="greek_literature",
                member_id=ILIAD_ID,
                claims=("materialization", "load"),
            ),
        )

        errors = validate_registry(root)
        self.assertTrue(
            any(
                f"member[{ILIAD_ID}].verification" in error
                and "representative-content" in error
                for error in errors
            ),
            errors,
        )

    def test_verified_collection_requires_its_own_discovery_evidence(self):
        root = self.make_root()
        resources, greek = self.resource(root, "greek_literature")
        greek["verification"]["status"] = "verified"
        _write_yaml(root / "registry/resources.yaml", resources)

        index, iliad = self.member(root, "greek_literature", ILIAD_ID)
        member_check = "member-load/iliad-full"
        iliad["verification"]["status"] = "verified"
        self.link_member_check(iliad, member_check)
        _write_yaml(root / "registry/collections/greek_literature.yaml", index)
        self.add_check(
            root,
            _direct_check(
                member_check,
                resource_id="greek_literature",
                member_id=ILIAD_ID,
                claims=POSITIVE_CLAIMS,
            ),
        )

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource greek_literature.verification" in error
                and "discovery" in error
                for error in errors
            ),
            errors,
        )

    def test_resource_wide_blocking_issue_rejects_verified_resource(self):
        root = self.make_root()
        resources, bhsa = self.resource(root, "bhsa")
        check_id = "resource-load/bhsa-full"
        bhsa["verification"]["status"] = "verified"
        self.link_resource_check(bhsa, check_id)
        bhsa["verification"]["known_issues"] = [
            {
                "id": "context-fabric/bhsa-fixture",
                "severity": "blocking",
                "impact": "resource",
                "signature": "fixture",
                "summary": "Fixture resource-wide blocker.",
            }
        ]
        _write_yaml(root / "registry/resources.yaml", resources)
        self.add_check(
            root,
            _direct_check(check_id, resource_id="bhsa", claims=POSITIVE_CLAIMS),
        )

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource bhsa.verification" in error
                and "blocking" in error.casefold()
                and "context-fabric/bhsa-fixture" in error
                for error in errors
            ),
            errors,
        )

    def test_member_impact_definition_is_rejected_on_non_collection(self):
        root = self.make_root()
        resources, bhsa = self.resource(root, "bhsa")
        bhsa["verification"]["known_issues"] = [
            {
                "id": "context-fabric/bhsa-member-fixture",
                "severity": "blocking",
                "impact": "member",
                "signature": "fixture",
                "summary": "Invalid member-scoped issue on corpus.",
            }
        ]
        _write_yaml(root / "registry/resources.yaml", resources)

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource bhsa.verification.known_issues" in error
                and "member" in error.casefold()
                and "collection" in error.casefold()
                for error in errors
            ),
            errors,
        )

    def test_member_scoped_blocker_does_not_block_collection_promotion(self):
        root = self.make_root()
        resources, greek = self.resource(root, "greek_literature")
        check_id = "resource-discovery/greek-literature"
        greek["verification"]["status"] = "verified"
        self.link_resource_check(greek, check_id)
        self.set_greek_issue(greek, severity="blocking", impact="member")
        _write_yaml(root / "registry/resources.yaml", resources)
        self.add_check(
            root,
            _direct_check(
                check_id,
                resource_id="greek_literature",
                claims=("discovery",),
            ),
        )

        errors = validate_registry(root)
        relevant = [
            error
            for error in errors
            if "resource greek_literature.verification" in error
            or "resources.yaml:resources" in error
        ]
        self.assertEqual(relevant, [], errors)

    def test_blocking_member_reference_rejects_verified_member(self):
        root = self.make_root()
        resources, greek = self.resource(root, "greek_literature")
        self.set_greek_issue(greek, severity="blocking", impact="member")
        _write_yaml(root / "registry/resources.yaml", resources)

        index, argonautica = self.member(root, "greek_literature", ARGONAUTICA_ID)
        check_id = "member-load/argonautica-full"
        argonautica["verification"]["status"] = "verified"
        self.link_member_check(argonautica, check_id)
        _write_yaml(root / "registry/collections/greek_literature.yaml", index)
        self.add_check(
            root,
            _direct_check(
                check_id,
                resource_id="greek_literature",
                member_id=ARGONAUTICA_ID,
                claims=POSITIVE_CLAIMS,
            ),
        )

        errors = validate_registry(root)
        self.assertTrue(
            any(
                f"member[{ARGONAUTICA_ID}].verification" in error
                and "blocking" in error.casefold()
                and ISSUE_ID in error
                for error in errors
            ),
            errors,
        )

    def test_advisory_member_issue_does_not_block_otherwise_verified_member(self):
        root = self.make_root()
        resources, greek = self.resource(root, "greek_literature")
        self.set_greek_issue(greek, severity="advisory", impact="member")
        _write_yaml(root / "registry/resources.yaml", resources)

        index, argonautica = self.member(root, "greek_literature", ARGONAUTICA_ID)
        check_id = "member-load/argonautica-advisory"
        argonautica["verification"]["status"] = "verified"
        self.link_member_check(argonautica, check_id)
        _write_yaml(root / "registry/collections/greek_literature.yaml", index)
        self.add_check(
            root,
            _direct_check(
                check_id,
                resource_id="greek_literature",
                member_id=ARGONAUTICA_ID,
                claims=POSITIVE_CLAIMS,
            ),
        )

        errors = validate_registry(root)
        relevant = [
            error
            for error in errors
            if f"member[{ARGONAUTICA_ID}].verification" in error
            or "resources.yaml:resources" in error
        ]
        self.assertEqual(relevant, [], errors)

    def test_known_issue_canary_cannot_substitute_positive_evidence(self):
        root = self.make_root()
        resources, bhsa = self.resource(root, "bhsa")
        check_id = "resource-canary/bhsa-fixture"
        bhsa["verification"]["status"] = "verified"
        self.link_resource_check(bhsa, check_id)
        _write_yaml(root / "registry/resources.yaml", resources)
        self.add_check(
            root,
            _direct_check(
                check_id,
                resource_id="bhsa",
                claims=("known-issue-canary",),
            ),
        )

        errors = validate_registry(root)
        self.assertTrue(
            any(
                "resource bhsa.verification" in error
                and "materialization" in error
                and "load" in error
                and "representative-content" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
