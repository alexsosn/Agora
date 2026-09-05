from __future__ import annotations

import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class RuntimeDependencyEnvironmentContractTests(unittest.TestCase):
    @staticmethod
    def _plugin_registry() -> dict:
        return yaml.safe_load((ROOT / "registry/plugins.yaml").read_text(encoding="utf-8"))

    @staticmethod
    def _server(plugin_id: str, client: str) -> dict:
        path = ROOT / f"plugins/{plugin_id}/.{client}-plugin/mcp.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        if client == "codex":
            return document["mcpServers"][plugin_id]
        return document[plugin_id]

    def test_agora_owned_local_runtime_launches_fail_closed_on_lock_drift(self):
        for plugin_id in ("context-fabric", "sedra"):
            for client in ("claude", "codex"):
                with self.subTest(plugin=plugin_id, client=client):
                    server = self._server(plugin_id, client)
                    self.assertEqual(server["command"], "uv")
                    self.assertIn("run", server["args"])
                    self.assertIn("--locked", server["args"])

    def test_uvx_launches_use_shipped_transitive_constraint_snapshots(self):
        expected = {
            ("perseus", "claude"): "${CLAUDE_PLUGIN_ROOT}/runtime-constraints.txt",
            ("perseus", "codex"): "runtime-constraints.txt",
            ("sefaria", "codex"): "runtime-constraints.txt",
        }
        for (plugin_id, client), constraint_path in expected.items():
            with self.subTest(plugin=plugin_id, client=client):
                server = self._server(plugin_id, client)
                self.assertEqual(server["command"], "uvx")
                self.assertIn("--constraint", server["args"])
                position = server["args"].index("--constraint")
                self.assertEqual(server["args"][position + 1], constraint_path)

    def test_sefaria_mcp_sdk_v1_compatibility_guard_remains_explicit(self):
        server = self._server("sefaria", "codex")
        self.assertIn("mcp>=1.17,<2", server["args"])

        registry = self._plugin_registry()
        sefaria = next(item for item in registry["plugins"] if item["id"] == "sefaria")
        resolution = sefaria["verification"]["clients"]["codex"]["checks"][0]["inputs"][
            "resolution"
        ]
        self.assertIn("mcp>=1.17,<2", resolution)

    def test_verification_inputs_identify_dependency_snapshot_and_live_harness(self):
        expected_environment = {
            ("context-fabric", "claude"): ("uv-lock", "plugins/context-fabric/uv.lock"),
            ("context-fabric", "codex"): ("uv-lock", "plugins/context-fabric/uv.lock"),
            ("perseus", "claude"): (
                "uv-constraints",
                "plugins/perseus/runtime-constraints.txt",
            ),
            ("perseus", "codex"): (
                "uv-constraints",
                "plugins/perseus/runtime-constraints.txt",
            ),
            ("sefaria", "claude"): ("hosted", None),
            ("sefaria", "codex"): (
                "uv-constraints",
                "plugins/sefaria/runtime-constraints.txt",
            ),
            ("sedra", "claude"): ("uv-lock", "plugins/sedra/uv.lock"),
            ("sedra", "codex"): ("uv-lock", "plugins/sedra/uv.lock"),
        }
        registry = self._plugin_registry()
        plugins = {item["id"]: item for item in registry["plugins"]}
        digest_re = __import__("re").compile(r"^[0-9a-f]{64}$")

        for (plugin_id, client), (kind, path) in expected_environment.items():
            with self.subTest(plugin=plugin_id, client=client):
                checks = plugins[plugin_id]["verification"]["clients"][client]["checks"]
                self.assertGreaterEqual(len(checks), 1)
                for reference in checks:
                    environment = reference["inputs"]["environment"]
                    self.assertEqual(environment["kind"], kind)
                    if kind == "hosted":
                        self.assertNotIn("path", environment)
                        self.assertNotIn("sha256", environment)
                    else:
                        self.assertEqual(environment["path"], path)
                        self.assertRegex(environment["sha256"], digest_re)
                        target = ROOT / path
                        self.assertTrue(target.is_file(), target)
                        actual = hashlib.sha256(target.read_bytes()).hexdigest()
                        self.assertEqual(environment["sha256"], actual)

                    if client == "codex" and reference["check_id"].startswith("mcp-live/"):
                        harness = reference["inputs"]["harness_environment"]
                        self.assertEqual(harness["kind"], "uv-lock")
                        self.assertEqual(
                            harness["path"],
                            "verification/mcp-smoke/uv.lock",
                        )
                        self.assertRegex(harness["sha256"], digest_re)

    def test_offline_validator_rejects_stale_dependency_digest(self):
        validator = importlib.import_module("scripts.validate_runtime_environments")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry").mkdir()
            lock_path = root / "plugins/demo/uv.lock"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("version = 1\n", encoding="utf-8")

            document = {
                "schema_version": 1,
                "plugins": [
                    {
                        "id": "demo",
                        "runtime": {
                            "mode": "local",
                            "launch": {
                                "claude": {"command": "uv", "args": ["run", "--locked"]},
                                "codex": {"command": "uv", "args": ["run", "--locked"]},
                            },
                        },
                        "verification": {
                            "clients": {
                                "claude": {
                                    "checks": [
                                        {
                                            "check_id": "manifest/demo-claude",
                                            "inputs": {
                                                "environment": {
                                                    "kind": "uv-lock",
                                                    "path": "plugins/demo/uv.lock",
                                                    "sha256": "0" * 64,
                                                }
                                            },
                                        }
                                    ]
                                },
                                "codex": {"checks": []},
                            }
                        },
                    }
                ],
            }
            (root / "registry/plugins.yaml").write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )

            errors = validator.validate_runtime_environments(root)
            self.assertTrue(
                any("sha256" in error and "plugins/demo/uv.lock" in error for error in errors),
                errors,
            )


if __name__ == "__main__":
    unittest.main()
