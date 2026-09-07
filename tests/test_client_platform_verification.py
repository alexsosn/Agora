from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

import scripts.smoke_mcp_plugin as smoke
import scripts.validate_verification_checks as verification

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/external-mcp-smoke.yml"
CHECKS = ROOT / "registry/verification-checks.yaml"
PLUGINS = ROOT / "registry/plugins.yaml"
CHECK_SCHEMA = ROOT / "registry/schema/verification-checks.schema.json"
COMPATIBILITY = ROOT / "wiki/guides/compatibility.md"

PLATFORM_CELLS = {
    ("context-fabric", "ubuntu-latest", "linux", "x86_64"),
    ("context-fabric", "macos-15-intel", "macos", "x86_64"),
    ("context-fabric", "windows-latest", "windows", "x86_64"),
    ("sedra", "ubuntu-latest", "linux", "x86_64"),
    ("sedra", "macos-15-intel", "macos", "x86_64"),
    ("sedra", "windows-latest", "windows", "x86_64"),
}

PLATFORM_CHECKS = {
    "platform-startup/context-fabric-linux-x86-64": (
        "context-fabric",
        "ubuntu-latest",
        "linux",
        "x86_64",
    ),
    "platform-startup/context-fabric-macos-x86-64": (
        "context-fabric",
        "macos-15-intel",
        "macos",
        "x86_64",
    ),
    "platform-startup/context-fabric-windows-x86-64": (
        "context-fabric",
        "windows-latest",
        "windows",
        "x86_64",
    ),
    "platform-startup/sedra-linux-x86-64": (
        "sedra",
        "ubuntu-latest",
        "linux",
        "x86_64",
    ),
    "platform-startup/sedra-macos-x86-64": (
        "sedra",
        "macos-15-intel",
        "macos",
        "x86_64",
    ),
    "platform-startup/sedra-windows-x86-64": (
        "sedra",
        "windows-latest",
        "windows",
        "x86_64",
    ),
}

CLAUDE_CHECKS = {
    "context-fabric": ("mcp-live/context-fabric-claude", "stdio"),
    "perseus": ("mcp-live/perseus-claude", "stdio"),
    "sefaria": ("mcp-live/sefaria-claude", "sse"),
    "sedra": ("mcp-live/sedra-claude", "stdio"),
}


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_workflow() -> str:
    return """name: fixture
jobs:
  platform:
    strategy:
      matrix:
        include:
          - plugin: context-fabric
            runner: ubuntu-latest
            platform_os: linux
            platform_arch: x86_64
          - plugin: context-fabric
            runner: windows-latest
            platform_os: windows
            platform_arch: x86_64
    runs-on: ${{ matrix.runner }}
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: startup-${{ matrix.plugin }}-${{ matrix.platform_os }}-${{ matrix.platform_arch }}
"""


class PlatformVerificationSchemaTests(unittest.TestCase):
    def _schema_errors(self, platform):
        check = {
            "id": "fixture/check",
            "kind": "live",
            "plugin": "context-fabric",
            "client": "codex",
            "transport": "stdio",
            "evidence_level": "community",
            "executor": {
                "type": "github-actions",
                "workflow": ".github/workflows/fixture.yml",
                "job": "platform",
                "matrix": {"plugin": "context-fabric"},
                "artifact": "fixture",
            },
        }
        if platform is not None:
            check["platform"] = platform
        doc = {"schema_version": 1, "checks": [check]}
        return list(Draft202012Validator(_load_json(CHECK_SCHEMA)).iter_errors(doc))

    def test_platform_schema_accepts_complete_controlled_identity(self):
        errors = self._schema_errors({"os": "windows", "arch": "x86_64"})
        self.assertEqual(errors, [])

    def test_platform_schema_rejects_partial_or_unknown_identity(self):
        for platform in (
            {"os": "linux"},
            {"arch": "x86_64"},
            {"os": "plan9", "arch": "x86_64"},
            {"os": "linux", "arch": "sparc"},
        ):
            with self.subTest(platform=platform):
                self.assertTrue(self._schema_errors(platform))

    def test_actions_selector_supports_one_exact_matrix_include_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = root / ".github/workflows/fixture.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(_fixture_workflow(), encoding="utf-8")
            executor = {
                "type": "github-actions",
                "workflow": ".github/workflows/fixture.yml",
                "job": "platform",
                "matrix": {
                    "plugin": "context-fabric",
                    "runner": "windows-latest",
                    "platform_os": "windows",
                    "platform_arch": "x86_64",
                },
                "artifact": "startup-context-fabric-windows-x86_64",
            }
            self.assertEqual(
                verification._validate_actions_executor(root, "fixture/check", executor),
                [],
            )

    def test_partial_include_selector_fails_closed_as_non_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = root / ".github/workflows/fixture.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(_fixture_workflow(), encoding="utf-8")
            executor = {
                "type": "github-actions",
                "workflow": ".github/workflows/fixture.yml",
                "job": "platform",
                "matrix": {"plugin": "context-fabric"},
                "artifact": "startup-context-fabric-linux-x86_64",
            }
            errors = verification._validate_actions_executor(root, "fixture/check", executor)
            self.assertTrue(
                any("exactly one" in error or "multiple" in error for error in errors),
                errors,
            )

    def test_declared_platform_must_match_selected_include_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry/schema").mkdir(parents=True)
            (root / ".github/workflows").mkdir(parents=True)
            (root / "registry/schema/verification-checks.schema.json").write_text(
                CHECK_SCHEMA.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / ".github/workflows/fixture.yml").write_text(
                _fixture_workflow(),
                encoding="utf-8",
            )
            checks = {
                "schema_version": 1,
                "checks": [
                    {
                        "id": "fixture/check",
                        "kind": "live",
                        "plugin": "context-fabric",
                        "client": "codex",
                        "transport": "stdio",
                        "evidence_level": "community",
                        "platform": {"os": "windows", "arch": "x86_64"},
                        "executor": {
                            "type": "github-actions",
                            "workflow": ".github/workflows/fixture.yml",
                            "job": "platform",
                            "matrix": {
                                "plugin": "context-fabric",
                                "runner": "ubuntu-latest",
                                "platform_os": "linux",
                                "platform_arch": "x86_64",
                            },
                            "artifact": "startup-context-fabric-linux-x86_64",
                        },
                    }
                ],
            }
            (root / "registry/verification-checks.yaml").write_text(
                yaml.safe_dump(checks, sort_keys=False),
                encoding="utf-8",
            )
            plugins = {
                "plugins": [
                    {
                        "id": "context-fabric",
                        "verification": {
                            "clients": {
                                "codex": {
                                    "status": "community",
                                    "transport": "stdio",
                                    "checks": [{"check_id": "fixture/check"}],
                                }
                            }
                        },
                    }
                ]
            }
            errors = verification.validate_verification_checks(root, plugins)
            self.assertTrue(
                any("platform" in error and "windows" in error and "linux" in error for error in errors),
                errors,
            )


class ClientTransportHarnessTests(unittest.TestCase):
    def test_claude_stdio_configs_resolve_exact_plugin_root_without_shell(self):
        loader = getattr(smoke, "load_plugin_connection")
        root = ROOT.resolve()

        context_fabric = loader("context-fabric", client="claude")
        self.assertEqual(context_fabric.client, "claude")
        self.assertEqual(context_fabric.transport, "stdio")
        self.assertEqual(context_fabric.command, "uv")
        self.assertIn(str(root / "plugins/context-fabric"), context_fabric.args)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", "\n".join(context_fabric.args))

        perseus = loader("perseus", client="claude")
        self.assertEqual(perseus.transport, "stdio")
        self.assertIn(
            str(root / "plugins/perseus/runtime-constraints.txt"),
            perseus.args,
        )

        sedra = loader("sedra", client="claude")
        self.assertEqual(sedra.transport, "stdio")
        self.assertIn(str(root / "plugins/sedra"), sedra.args)

    def test_sefaria_claude_uses_generated_direct_sse_not_codex_proxy(self):
        loader = getattr(smoke, "load_plugin_connection")
        connection = loader("sefaria", client="claude")
        self.assertEqual(connection.client, "claude")
        self.assertEqual(connection.transport, "sse")
        self.assertEqual(connection.url, "https://mcp.sefaria.org/sse")
        self.assertIsNone(connection.command)
        self.assertNotIn("mcp-proxy", repr(connection))

    def test_default_codex_loader_behavior_remains_compatible(self):
        loader = getattr(smoke, "load_plugin_connection")
        connection = loader("perseus")
        legacy = smoke.load_plugin_launch("perseus")
        self.assertEqual(connection.client, "codex")
        self.assertEqual(connection.transport, "stdio")
        self.assertEqual(connection.command, legacy.command)
        self.assertEqual(connection.args, legacy.args)
        self.assertEqual(connection.cwd, legacy.cwd)

    def test_unsupported_generated_transport_fails_without_cross_client_fallback(self):
        loader = getattr(smoke, "load_plugin_connection")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "plugins/context-fabric/.claude-plugin/mcp.json"
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps(
                    {
                        "context-fabric": {
                            "type": "websocket",
                            "url": "wss://example.invalid/mcp",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "transport|websocket|unsupported"):
                loader("context-fabric", client="claude", root=root)

    def test_trace_names_requested_client_transport_and_generic_harness(self):
        loader = getattr(smoke, "load_plugin_connection")
        connection = loader("context-fabric", client="claude")
        trace = smoke.build_trace_metadata(
            "context-fabric",
            connection=connection,
            client="claude",
            check_id="mcp-live/context-fabric-claude",
            env={},
            checked_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(trace["client"], "claude")
        self.assertEqual(trace["client_requested"], "claude")
        self.assertEqual(trace["client_execution"], "generic-harness")
        self.assertEqual(trace["transport"], "stdio")
        self.assertEqual(trace["generated_transport"], "stdio")


class PlatformWorkflowContractTests(unittest.TestCase):
    def test_local_runtime_platform_matrix_has_exactly_six_bounded_cells(self):
        document = _load_yaml(WORKFLOW)
        job = document["jobs"]["local-runtime-platform"]
        include = job["strategy"]["matrix"]["include"]
        actual = {
            (
                cell["plugin"],
                cell["runner"],
                cell["platform_os"],
                cell["platform_arch"],
            )
            for cell in include
        }
        self.assertEqual(actual, PLATFORM_CELLS)
        self.assertEqual(len(include), 6)
        self.assertEqual(job["runs-on"], "${{ matrix.runner }}")
        self.assertLessEqual(job["timeout-minutes"], 10)

    def test_platform_job_runtime_asserts_declared_os_and_arch_before_launch(self):
        document = _load_yaml(WORKFLOW)
        steps = document["jobs"]["local-runtime-platform"]["steps"]
        assertion = next(
            step
            for step in steps
            if "platform.system()" in str(step.get("run", ""))
            and "platform.machine()" in str(step.get("run", ""))
        )
        self.assertEqual(assertion["env"]["EXPECTED_OS"], "${{ matrix.platform_os }}")
        self.assertEqual(assertion["env"]["EXPECTED_ARCH"], "${{ matrix.platform_arch }}")

        smoke_step = next(
            step
            for step in steps
            if "scripts/smoke_mcp_plugin.py" in str(step.get("run", ""))
        )
        run = smoke_step["run"]
        self.assertIn('"${{ matrix.plugin }}"', run)
        self.assertIn("--client codex", run)
        self.assertIn("--startup-only", run)
        self.assertNotIn("agora-context-fabric-mcp", run)
        self.assertNotIn("agora-sedra-mcp", run)

    def test_platform_artifacts_are_unique_and_always_uploaded(self):
        document = _load_yaml(WORKFLOW)
        steps = document["jobs"]["local-runtime-platform"]["steps"]
        uploads = [
            step
            for step in steps
            if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        ]
        self.assertEqual(len(uploads), 1)
        upload = uploads[0]
        self.assertEqual(upload.get("if"), "always()")
        name = upload["with"]["name"]
        self.assertIn("${{ matrix.plugin }}", name)
        self.assertIn("${{ matrix.platform_os }}", name)
        self.assertIn("${{ matrix.platform_arch }}", name)

    def test_platform_dependency_and_generated_launch_changes_retrigger_workflow(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for path in (
            "plugins/context-fabric/.codex-plugin/mcp.json",
            "plugins/context-fabric/pyproject.toml",
            "plugins/context-fabric/uv.lock",
            "plugins/sedra/.codex-plugin/mcp.json",
            "plugins/sedra/pyproject.toml",
            "plugins/sedra/uv.lock",
            "verification/mcp-smoke/pyproject.toml",
            "verification/mcp-smoke/uv.lock",
            "scripts/smoke_mcp_plugin.py",
        ):
            with self.subTest(path=path):
                self.assertIn(f'- "{path}"', workflow)


class ClaudeLiveWorkflowContractTests(unittest.TestCase):
    def test_all_v01_generated_claude_paths_have_live_matrix(self):
        document = _load_yaml(WORKFLOW)
        job = document["jobs"]["claude-live-mcp"]
        self.assertEqual(
            set(job["strategy"]["matrix"]["plugin"]),
            {"context-fabric", "perseus", "sefaria", "sedra"},
        )
        self.assertEqual(job["runs-on"], "ubuntu-24.04")
        self.assertLessEqual(job["timeout-minutes"], 10)
        run = "\n".join(
            str(step.get("run", ""))
            for step in job["steps"]
            if isinstance(step, dict)
        )
        self.assertIn("scripts/smoke_mcp_plugin.py", run)
        self.assertIn("--client claude", run)
        self.assertNotIn("--startup-only", run)

    def test_claude_artifacts_are_unique_and_generated_configs_retrigger(self):
        document = _load_yaml(WORKFLOW)
        job = document["jobs"]["claude-live-mcp"]
        upload = next(
            step
            for step in job["steps"]
            if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        )
        self.assertEqual(upload.get("if"), "always()")
        self.assertIn("${{ matrix.plugin }}", upload["with"]["name"])
        self.assertIn("claude", upload["with"]["name"])

        workflow = WORKFLOW.read_text(encoding="utf-8")
        for plugin in ("context-fabric", "perseus", "sefaria", "sedra"):
            with self.subTest(plugin=plugin):
                self.assertIn(f'"plugins/{plugin}/.claude-plugin/mcp.json"', workflow)


class CanonicalEvidenceGraphTests(unittest.TestCase):
    def test_platform_startup_checks_are_live_community_and_exactly_bound(self):
        checks = {item["id"]: item for item in _load_yaml(CHECKS)["checks"]}
        for check_id, (plugin, runner, os_name, arch) in PLATFORM_CHECKS.items():
            with self.subTest(check_id=check_id):
                check = checks[check_id]
                self.assertEqual(check["kind"], "live")
                self.assertEqual(check["evidence_level"], "community")
                self.assertEqual(check["plugin"], plugin)
                self.assertEqual(check["client"], "codex")
                self.assertEqual(check["transport"], "stdio")
                self.assertEqual(check["platform"], {"os": os_name, "arch": arch})
                executor = check["executor"]
                self.assertEqual(executor["job"], "local-runtime-platform")
                self.assertEqual(
                    executor["matrix"],
                    {
                        "plugin": plugin,
                        "runner": runner,
                        "platform_os": os_name,
                        "platform_arch": arch,
                    },
                )

    def test_claude_live_checks_match_exact_generated_transports(self):
        checks = {item["id"]: item for item in _load_yaml(CHECKS)["checks"]}
        plugins = {item["id"]: item for item in _load_yaml(PLUGINS)["plugins"]}
        for plugin_id, (check_id, transport) in CLAUDE_CHECKS.items():
            with self.subTest(plugin=plugin_id):
                check = checks[check_id]
                self.assertEqual(check["kind"], "live")
                self.assertIn(check["evidence_level"], {"community", "verified"})
                self.assertEqual(check["plugin"], plugin_id)
                self.assertEqual(check["client"], "claude")
                self.assertEqual(check["transport"], transport)
                self.assertEqual(check["executor"]["job"], "claude-live-mcp")
                self.assertEqual(check["executor"]["matrix"], {"plugin": plugin_id})

                client = plugins[plugin_id]["verification"]["clients"]["claude"]
                referenced = {item["check_id"] for item in client["checks"]}
                self.assertIn(check_id, referenced)
                if client["status"] == "verified":
                    self.assertEqual(check["evidence_level"], "verified")

    def test_local_runtime_codex_evidence_references_all_platform_checks(self):
        plugins = {item["id"]: item for item in _load_yaml(PLUGINS)["plugins"]}
        for plugin_id in ("context-fabric", "sedra"):
            referenced = {
                item["check_id"]
                for item in plugins[plugin_id]["verification"]["clients"]["codex"]["checks"]
            }
            expected = {
                check_id
                for check_id in PLATFORM_CHECKS
                if check_id.startswith(f"platform-startup/{plugin_id}-")
            }
            self.assertTrue(expected)
            self.assertTrue(expected.issubset(referenced), (plugin_id, referenced, expected))


class CompatibilityDocumentationTests(unittest.TestCase):
    def test_compatibility_guide_exists_and_is_linked(self):
        self.assertTrue(COMPATIBILITY.is_file())
        self.assertIn(
            "wiki/guides/compatibility.md",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "compatibility.md",
            (ROOT / "wiki/guides/installation.md").read_text(encoding="utf-8"),
        )

    def test_guide_discloses_evidence_boundaries_and_platform_scope(self):
        guide = COMPATIBILITY.read_text(encoding="utf-8")
        folded = guide.casefold()
        for phrase in (
            "generic mcp harness",
            "representative operation",
            "startup",
            "deterministic",
            "claude code",
            "codex",
            "intel",
            "x86_64",
            "direct sse",
            "stdio-via-sse-proxy",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, folded)
        self.assertRegex(folded, r"does not .*claude code|does not .*codex|not .*client executable")

    def test_every_check_id_named_in_guide_resolves_canonically(self):
        guide = COMPATIBILITY.read_text(encoding="utf-8")
        canonical = {item["id"] for item in _load_yaml(CHECKS)["checks"]}
        named = set(
            re.findall(
                r"`((?:mcp-live|manifest|platform-startup)/[a-z0-9-]+)`",
                guide,
            )
        )
        self.assertTrue(named)
        self.assertEqual(named - canonical, set())


if __name__ == "__main__":
    unittest.main()
