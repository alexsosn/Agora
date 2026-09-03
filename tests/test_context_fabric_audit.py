from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from scripts.audit_context_fabric_sources import audit_catalog


class FakeStore:
    def __init__(
        self,
        roots: dict[str, list[str]],
        failures: set[str] | None = None,
        feature_files: dict[tuple[str, str], list[str]] | None = None,
        summaries: dict[tuple[str, str], dict] | None = None,
    ):
        self.roots = roots
        self.failures = failures or set()
        self.feature_file_map = feature_files or {}
        self.summary_map = summaries or {}
        self.repositories: dict[str, str] = {}
        self.refs: dict[str, str | None] = {}

    def ensure_metadata(
        self,
        repository: str,
        *,
        cache_key: str | None = None,
        ref: str | None = None,
    ) -> Path:
        key = cache_key or repository
        if key in self.failures:
            raise RuntimeError(f"cannot clone {key}")
        self.repositories[key] = repository
        self.refs[key] = ref
        return Path("/metadata") / key

    def dataset_roots(self, repo: Path, revision=None) -> list[str]:
        return list(self.roots[repo.name])

    def feature_files(self, repo: Path, relative_path: str, revision=None) -> list[str]:
        return list(self.feature_file_map.get((repo.name, relative_path), []))

    def tf_feature_summary(self, repo: Path, relative_path: str, revision=None) -> dict:
        return dict(self.summary_map[(repo.name, relative_path)])

    def dataset_warp_fingerprint(self, repo: Path, relative_path: str, revision=None) -> str:
        return f"sha256:{repo.name}-{relative_path}"

    def selected_revision(self, repo: Path) -> str:
        return (repo.name.encode("utf-8").hex() + "0" * 40)[:40]


def resource(
    resource_id: str,
    *,
    kind: str = "corpus",
    ref: str | None = None,
    tf_path: str | None = None,
    parent: str | None = None,
    parent_versions: tuple[str, ...] = (),
    module_path: str | None = None,
) -> ResourceSpec:
    return ResourceSpec(
        id=resource_id,
        name=resource_id,
        plugin="context-fabric",
        provider="context-fabric",
        kind=kind,
        repository=f"example/{resource_id}",
        languages=("greek",),
        disciplines=("classics",),
        member_index="unused" if kind == "collection" else None,
        ref=ref,
        tf_path=tf_path,
        parent=parent,
        parent_versions=parent_versions,
        module_path=module_path,
        module_status="optional" if kind == "feature-module" else None,
    )


class SourceAuditTests(unittest.TestCase):
    def test_audit_selects_latest_dataset_for_ordinary_corpus(self):
        catalog = Catalog([resource("ordinary")])
        store = FakeStore({"ordinary": ["tf/0.9", "tf/1.0"]})

        report = audit_catalog(catalog, store)

        self.assertTrue(report["ok"])
        self.assertEqual(report["checked"], 1)
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["failed"], 0)
        item = report["resources"][0]
        self.assertEqual(item["status"], "ok")
        self.assertRegex(item["source_revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(item["selected_root"], "tf/1.0")
        self.assertEqual(item["dataset_root_count"], 2)

    def test_collection_audit_preserves_many_member_roots(self):
        catalog = Catalog([resource("greek", kind="collection")])
        store = FakeStore(
            {
                "greek": [
                    "Homer/Iliad/tf/1.0",
                    "Plato/Phaedo/tf/1.0",
                    "Plato/Phaedo/tf/2.0",
                ]
            }
        )

        report = audit_catalog(catalog, store)

        item = report["resources"][0]
        self.assertEqual(item["status"], "ok")
        self.assertEqual(item["kind"], "collection")
        self.assertEqual(item["dataset_root_count"], 3)
        self.assertNotIn("selected_root", item)

    def test_pinned_ref_and_tf_path_are_audited_explicitly(self):
        catalog = Catalog(
            [resource("pinned", ref="abc123", tf_path="tf/0.1.0")]
        )
        store = FakeStore({"pinned": ["tf/0.1.0", "tf/0.2.0"]})

        report = audit_catalog(catalog, store)

        self.assertTrue(report["ok"])
        self.assertEqual(store.refs["pinned"], "abc123")
        item = report["resources"][0]
        self.assertEqual(item["ref"], "abc123")
        self.assertEqual(item["configured_tf_path"], "tf/0.1.0")
        self.assertEqual(item["selected_root"], "tf/0.1.0")

    def test_feature_module_audit_uses_core_identity_version_and_bounds(self):
        catalog = Catalog(
            [
                resource("bhsa"),
                resource(
                    "addon",
                    kind="feature-module",
                    tf_path="tf/2021",
                    parent="bhsa",
                    parent_versions=("2021",),
                    module_path="example/addon/tf",
                ),
            ]
        )
        store = FakeStore(
            {"bhsa": ["tf/c", "tf/2021"], "addon": []},
            feature_files={("addon", "tf/2021"): ["accent.tf", "tree.tf"]},
            summaries={
                ("bhsa", "tf/2021/otype.tf"): {
                    "kind": "node",
                    "metadata": {"dataset": "BHSA", "version": "2021"},
                    "max_node": 100,
                },
                ("addon", "tf/2021/accent.tf"): {
                    "kind": "node",
                    "metadata": {"coreData": "BHSA", "coreVersion": "2021"},
                    "max_node": 90,
                },
                ("addon", "tf/2021/tree.tf"): {
                    "kind": "node",
                    "metadata": {"coreData": "BHSA", "coreVersion": "2021"},
                    "max_node": 95,
                },
            },
        )

        report = audit_catalog(catalog, store)

        self.assertTrue(report["ok"], report)
        item = report["resources"][1]
        self.assertEqual(item["parent"], "bhsa")
        self.assertEqual(item["compatible_parent_versions"], ["2021"])
        self.assertEqual(item["verified_parent_versions"], ["2021"])
        self.assertEqual(item["parent_default_version"], "2021")
        self.assertTrue(item["compatible_with_default"])
        self.assertEqual(item["module"], "example/addon/tf")
        self.assertEqual(item["feature_file_count"], 2)
        self.assertEqual(item["core_data"], "BHSA")
        self.assertEqual(item["core_version_evidence"], ["2021"])
        self.assertEqual(item["max_referenced_node"], 95)
        self.assertEqual(item["sample_features"], ["accent.tf", "tree.tf"])
        self.assertNotIn("dataset_root_count", item)

    def test_feature_module_audit_rejects_core_identity_mismatch(self):
        catalog = Catalog(
            [
                resource("bhsa"),
                resource(
                    "addon",
                    kind="feature-module",
                    tf_path="tf/2021",
                    parent="bhsa",
                    parent_versions=("2021",),
                    module_path="example/addon/tf",
                ),
            ]
        )
        store = FakeStore(
            {"bhsa": ["tf/2021"], "addon": []},
            feature_files={("addon", "tf/2021"): ["foo.tf"]},
            summaries={
                ("bhsa", "tf/2021/otype.tf"): {
                    "kind": "node",
                    "metadata": {"dataset": "BHSA", "version": "2021"},
                    "max_node": 100,
                },
                ("addon", "tf/2021/foo.tf"): {
                    "kind": "node",
                    "metadata": {"coreData": "OTHER", "coreVersion": "2021"},
                    "max_node": 10,
                },
            },
        )
        report = audit_catalog(catalog, store)
        self.assertFalse(report["ok"])
        self.assertIn("does not match parent", report["resources"][1]["error"])

    def test_feature_module_audit_rejects_out_of_bounds_node(self):
        catalog = Catalog(
            [
                resource("bhsa"),
                resource(
                    "addon",
                    kind="feature-module",
                    tf_path="tf/2021",
                    parent="bhsa",
                    parent_versions=("2021",),
                    module_path="example/addon/tf",
                ),
            ]
        )
        store = FakeStore(
            {"bhsa": ["tf/2021"], "addon": []},
            feature_files={("addon", "tf/2021"): ["foo.tf"]},
            summaries={
                ("bhsa", "tf/2021/otype.tf"): {
                    "kind": "node",
                    "metadata": {"dataset": "BHSA", "version": "2021"},
                    "max_node": 100,
                },
                ("addon", "tf/2021/foo.tf"): {
                    "kind": "node",
                    "metadata": {"coreData": "BHSA", "coreVersion": "2021"},
                    "max_node": 101,
                },
            },
        )
        report = audit_catalog(catalog, store)
        self.assertFalse(report["ok"])
        self.assertIn("beyond parent", report["resources"][1]["error"])

    def test_empty_dataset_root_set_is_a_failure(self):
        catalog = Catalog([resource("empty")])
        report = audit_catalog(catalog, FakeStore({"empty": []}))

        self.assertFalse(report["ok"])
        self.assertEqual(report["passed"], 0)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["resources"][0]["status"], "error")
        self.assertIn("no Text-Fabric dataset", report["resources"][0]["error"])

    def test_one_upstream_failure_does_not_abort_remaining_resources(self):
        catalog = Catalog([resource("bad"), resource("good")])
        store = FakeStore({"good": ["tf/1.0"]}, failures={"bad"})

        report = audit_catalog(catalog, store)

        self.assertEqual(report["checked"], 2)
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(
            [item["status"] for item in report["resources"]],
            ["error", "ok"],
        )


if __name__ == "__main__":
    unittest.main()
