from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.server import build_parser
from agora_context_fabric.service import ContextFabricService
from scripts.generate_marketplaces import claude_mcp, codex_mcp


class _NoopResolver:
    pass


class _NoopLoader:
    pass


class ResourceIntegrationMetadataTests(unittest.TestCase):
    def test_tlhdig_integration_metadata_survives_catalog_projection(self):
        resource = Catalog.from_registry(ROOT).get("TLHdig-TF")
        self.assertEqual(resource.description, "Text-Fabric conversion of the Thesaurus Linguarum Hethaeorum digitalis Hittite corpus.")
        self.assertEqual(resource.period, "2nd millennium BCE")
        self.assertEqual(resource.verification_status, "community")
        self.assertEqual(resource.licenses["data"], "upstream-dependent")
        self.assertEqual(resource.licenses["redistribution"], "unknown")
        self.assertEqual(resource.integration_issues, ())
        self.assertEqual(resource.source_snapshot["source"], "alexsosn/TLHdig-TF")
        self.assertIsNone(resource.ref)
        self.assertEqual(resource.tf_path, "tf/0.1.0")

    def test_service_exposes_integration_and_source_configuration(self):
        service = ContextFabricService(Catalog.from_registry(ROOT), _NoopResolver(), _NoopLoader())
        item = service.describe_resource("TLHdig-TF")
        self.assertEqual(item["description"], "Text-Fabric conversion of the Thesaurus Linguarum Hethaeorum digitalis Hittite corpus.")
        self.assertEqual(item["period"], "2nd millennium BCE")
        self.assertEqual(item["verification"]["status"], "community")
        self.assertEqual(item["licenses"]["data"], "upstream-dependent")
        self.assertEqual(item["integration_issues"], [])
        self.assertEqual(item["source_snapshot"]["source"], "alexsosn/TLHdig-TF")
        self.assertIsNone(item["source"]["configured_ref"])
        self.assertEqual(item["source"]["tf_path"], "tf/0.1.0")


class GitRefreshAndProvenanceTests(unittest.TestCase):
    def _make_repository(self, root: Path) -> Path:
        source = root / "source"
        source.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
        subprocess.run(["git", "config", "user.name", "Agora Tests"], cwd=source, check=True)
        tf = source / "tf" / "1.0"
        tf.mkdir(parents=True)
        (tf / "otype.tf").write_text("@node\n", encoding="utf-8")
        (tf / "word.tf").write_text("first\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "first"], cwd=source, check=True)
        return source

    def _advance_repository(self, source: Path) -> str:
        (source / "tf/1.0/word.tf").write_text("second\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "second"], cwd=source, check=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()

    def test_unpinned_metadata_refreshes_to_current_default_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._make_repository(root)
            store = GitStore(root / "cache")
            repo = store.ensure_metadata(str(source), cache_key="fixture")
            first = store.selected_revision(repo)

            second = self._advance_repository(source)
            repo = store.ensure_metadata(str(source), cache_key="fixture")

            self.assertNotEqual(first, second)
            self.assertEqual(store.selected_revision(repo), second)
            materialized = store.materialize(repo, "tf/1.0")
            self.assertEqual((materialized / "word.tf").read_text(encoding="utf-8"), "second\n")

    def test_prepare_and_load_expose_resolved_source_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._make_repository(root)
            catalog = Catalog([
                ResourceSpec(
                    id="fixture",
                    name="Fixture",
                    plugin="context-fabric",
                    provider="context-fabric",
                    kind="corpus",
                    repository=str(source),
                    languages=("test",),
                    disciplines=("testing",),
                )
            ])
            store = GitStore(root / "cache")
            resolver = ContextFabricResolver(catalog, store)

            class Loader:
                def load(self, path, name=None, features=None):
                    return {"name": name, "path": path}

            service = ContextFabricService(catalog, resolver, Loader())
            prepared = service.prepare("fixture")
            loaded = service.load("fixture")
            self.assertRegex(prepared["source_revision"], r"^[0-9a-f]{40}$")
            self.assertEqual(loaded["source_revision"], prepared["source_revision"])


class CollectionMetadataTests(unittest.TestCase):
    def test_service_exposes_dynamic_collection_discovery_contract(self):
        service = ContextFabricService(Catalog.from_registry(ROOT), _NoopResolver(), _NoopLoader())
        item = service.describe_resource("greek_literature")
        self.assertEqual(
            item["collection"],
            {
                "discovery": "git-tree",
                "member_id_scheme": "stable-relative-id",
                "lazy_members": True,
                "member_index": "registry/collections/greek_literature.yaml",
            },
        )

    def test_arbitrary_repository_path_segments_are_not_mislabeled_author_and_title(self):
        resource = ResourceSpec(
            id="greek_literature",
            name="Greek Literature",
            plugin="context-fabric",
            provider="context-fabric",
            kind="collection",
            repository="unused/repository",
            languages=("greek",),
            disciplines=("classics",),
        )
        resolver = ContextFabricResolver(Catalog([resource]), object())
        members = resolver._collection_members_from_roots(
            resource,
            ["canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0"],
        )
        self.assertEqual(len(members), 1)
        self.assertIsNone(members[0].author)
        self.assertIsNone(members[0].title)
        self.assertEqual(
            members[0].identity_path,
            "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1",
        )


class TransportSafetyTests(unittest.TestCase):
    def test_network_transports_default_to_loopback(self):
        args = build_parser().parse_args(["--http", "9123"])
        self.assertEqual(args.host, "127.0.0.1")


class DeclarativeLaunchTests(unittest.TestCase):
    def test_every_release_plugin_declares_client_launch_metadata(self):
        with (ROOT / "registry/plugins.yaml").open("r", encoding="utf-8") as fh:
            plugins = yaml.safe_load(fh)["plugins"]
        for plugin in plugins:
            self.assertEqual(set(plugin["runtime"]["launch"]), {"claude", "codex"})

    def test_generator_transforms_launch_metadata_without_plugin_specific_branch(self):
        plugin = {
            "id": "example",
            "runtime": {
                "launch": {
                    "claude": {"command": "example-claude", "args": ["--stdio"]},
                    "codex": {"type": "stdio", "command": "example-codex", "args": []},
                }
            },
        }
        self.assertEqual(
            claude_mcp(plugin),
            {"example": {"command": "example-claude", "args": ["--stdio"]}},
        )
        self.assertEqual(
            codex_mcp(plugin),
            {"mcpServers": {"example": {"type": "stdio", "command": "example-codex", "args": []}}},
        )


class VerificationEvidenceTests(unittest.TestCase):
    def test_verification_is_client_and_transport_specific(self):
        with (ROOT / "registry/plugins.yaml").open("r", encoding="utf-8") as fh:
            plugins = yaml.safe_load(fh)["plugins"]
        for plugin in plugins:
            verification = plugin["verification"]
            self.assertIn("clients", verification)
            self.assertEqual(set(verification["clients"]), {"claude", "codex"})
            for client, evidence in verification["clients"].items():
                self.assertIn(evidence["status"], {"experimental", "community", "verified"})
                self.assertTrue(evidence["transport"])
                self.assertTrue(evidence["tests"])
                for test in evidence["tests"]:
                    self.assertTrue(test["name"])
                    self.assertTrue(test["kind"])
            # Until both client paths have equivalent live evidence, the aggregate
            # status must not claim stronger verification than the weakest client.
            client_statuses = {entry["status"] for entry in verification["clients"].values()}
            if "experimental" in client_statuses:
                expected = "experimental"
            elif "community" in client_statuses:
                expected = "community"
            else:
                expected = "verified"
            self.assertEqual(verification["status"], expected)


if __name__ == "__main__":
    unittest.main()
