from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog


EXPECTED_REVISIONS = {
    "bible": "f09ea5060761b372adf1ac1d70d7b96918f57757",
    "patristics": "75d0e305c4f88a9304a4cf524dc19b9a66b0ec9e",
    "greek_literature": "77d85bf71fc6f689f7faedc255666a2609ffe590",
    "translatin-manif": "ab4df0d84d3480cee0cdaa41973c77ec7a0f99ed",
}

DUPLICATE_STRUCTURE_ISSUE = "context-fabric/duplicate-structure-levels"
BAD_GREEK_PATHS = (
    "canonical-greekLit/tlg0001/tlg001/perseus-grc2/1/tf/1.0",
    "canonical-greekLit/tlg0006/tlg009/perseus-grc2/1/tf/1.0",
)
GOOD_GREEK_PATH = "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def member_issue_ids(member: dict) -> set[str]:
    verification = member.get("verification") or {}
    return {
        reference["issue_id"]
        for reference in verification.get("known_issues", [])
        if isinstance(reference, dict) and isinstance(reference.get("issue_id"), str)
    }


class CommittedCollectionIndexTests(unittest.TestCase):
    def test_v01_collections_use_complete_commit_bound_indexes(self):
        catalog = Catalog.from_registry(ROOT)
        for resource_id, expected_revision in EXPECTED_REVISIONS.items():
            resource = catalog.get(resource_id)
            self.assertEqual(resource.kind, "collection")
            self.assertEqual(resource.collection_discovery, "indexed")
            self.assertIsNotNone(resource.member_index_path)

            document = load_yaml(resource.member_index_path)
            self.assertEqual(document["collection_id"], resource_id)
            self.assertEqual(document["source_revision"], expected_revision)
            self.assertEqual(document["index_status"], "complete")
            self.assertGreater(len(document["members"]), 0)

    def test_complete_indexes_have_stable_unique_member_identity_and_load_paths(self):
        catalog = Catalog.from_registry(ROOT)
        for resource_id in EXPECTED_REVISIONS:
            resource = catalog.get(resource_id)
            document = load_yaml(resource.member_index_path)
            ids: set[str] = set()
            identities: set[str] = set()
            for member in document["members"]:
                self.assertTrue(member["id"])
                self.assertTrue(member["path"])
                self.assertTrue(member["tf_path"])
                self.assertTrue(member["languages"])
                self.assertIn("verification", member)
                self.assertNotIn(member["id"], ids)
                self.assertNotIn(member["path"], identities)
                ids.add(member["id"])
                identities.add(member["path"])

    def test_greek_resource_defines_duplicate_structure_levels_as_blocking_issue(self):
        resource = Catalog.from_registry(ROOT).get("greek_literature")
        issues = {
            issue["id"]: issue
            for issue in resource.verification_known_issues
            if isinstance(issue.get("id"), str)
        }
        self.assertIn(DUPLICATE_STRUCTURE_ISSUE, issues)
        issue = issues[DUPLICATE_STRUCTURE_ISSUE]
        self.assertEqual(issue["severity"], "blocking")
        self.assertEqual(issue["signature"], "duplicate-structure-levels")
        repositories = {
            upstream["repository"]
            for upstream in issue.get("upstream", [])
            if isinstance(upstream, dict) and isinstance(upstream.get("repository"), str)
        }
        self.assertEqual(
            repositories,
            {"Context-Fabric/context-fabric", "pthu/greek_literature"},
        )

    def test_greek_snapshot_flags_reproduced_bad_members_but_not_iliad(self):
        catalog = Catalog.from_registry(ROOT)
        document = load_yaml(catalog.get("greek_literature").member_index_path)
        by_tf_path = {member["tf_path"]: member for member in document["members"]}

        for path in BAD_GREEK_PATHS:
            self.assertIn(path, by_tf_path)
            self.assertIn(DUPLICATE_STRUCTURE_ISSUE, member_issue_ids(by_tf_path[path]))

        self.assertIn(GOOD_GREEK_PATH, by_tf_path)
        self.assertNotIn(DUPLICATE_STRUCTURE_ISSUE, member_issue_ids(by_tf_path[GOOD_GREEK_PATH]))

    def test_greek_index_contains_source_backed_homer_iliad_identity(self):
        catalog = Catalog.from_registry(ROOT)
        document = load_yaml(catalog.get("greek_literature").member_index_path)
        matches = [
            member
            for member in document["members"]
            if member.get("canonical_id") == "tlg0012.tlg001.perseus-grc2"
        ]
        self.assertEqual(len(matches), 1)
        iliad = matches[0]
        self.assertEqual(iliad.get("author"), "Homer")
        self.assertIn("Iliad", iliad.get("title", ""))
        self.assertEqual(
            iliad["path"],
            "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1",
        )
        self.assertEqual(
            iliad["tf_path"],
            GOOD_GREEK_PATH,
        )

    def test_installed_plugin_carries_exact_canonical_index_documents(self):
        catalog = Catalog.from_registry(ROOT)
        bundled_root = ROOT / "plugins" / "context-fabric" / "resources" / "collections"
        for resource_id in EXPECTED_REVISIONS:
            canonical = load_yaml(catalog.get(resource_id).member_index_path)
            bundled = load_yaml(bundled_root / f"{resource_id}.yaml")
            self.assertEqual(bundled, canonical)


if __name__ == "__main__":
    unittest.main()
