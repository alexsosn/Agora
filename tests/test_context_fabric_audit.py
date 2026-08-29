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
    def __init__(self, roots: dict[str, list[str]], failures: set[str] | None = None):
        self.roots = roots
        self.failures = failures or set()
        self.repositories: dict[str, str] = {}

    def ensure_metadata(self, repository: str, *, cache_key: str | None = None) -> Path:
        key = cache_key or repository
        if key in self.failures:
            raise RuntimeError(f"cannot clone {key}")
        self.repositories[key] = repository
        return Path("/metadata") / key

    def dataset_roots(self, repo: Path) -> list[str]:
        return list(self.roots[repo.name])


def resource(resource_id: str, *, kind: str = "corpus") -> ResourceSpec:
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
    )


class SourceAuditTests(unittest.TestCase):
    def test_audit_selects_latest_dataset_for_ordinary_corpus(self):
        catalog = Catalog([resource("ordinary")])
        store = FakeStore({"ordinary": ["tf/0.9", "tf/1.0"]})

        report = audit_catalog(catalog, store)

        self.assertTrue(report["ok"])
        self.assertEqual(report["checked"], 1)
        self.assertEqual(report["failed"], 0)
        item = report["resources"][0]
        self.assertEqual(item["status"], "ok")
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

    def test_empty_dataset_root_set_is_a_failure(self):
        catalog = Catalog([resource("empty")])
        report = audit_catalog(catalog, FakeStore({"empty": []}))

        self.assertFalse(report["ok"])
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["resources"][0]["status"], "error")
        self.assertIn("no Text-Fabric dataset", report["resources"][0]["error"])

    def test_one_upstream_failure_does_not_abort_remaining_resources(self):
        catalog = Catalog([resource("bad"), resource("good")])
        store = FakeStore({"good": ["tf/1.0"]}, failures={"bad"})

        report = audit_catalog(catalog, store)

        self.assertEqual(report["checked"], 2)
        self.assertEqual(report["failed"], 1)
        self.assertEqual(
            [item["status"] for item in report["resources"]],
            ["error", "ok"],
        )


if __name__ == "__main__":
    unittest.main()
