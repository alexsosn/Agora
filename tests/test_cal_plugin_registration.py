"""Post-1.0 CAL-MCP marketplace contract: versioned source and native launches."""

from __future__ import annotations

import json
import unittest
import yaml

from scripts.generate_marketplaces import ROOT, check_outputs, render_outputs


def _yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "registry" / name).read_text(encoding="utf-8"))


class CalPluginRegistrationTests(unittest.TestCase):
    def test_post_one_scope_adds_cal_without_mutating_frozen_scope(self) -> None:
        old = _yaml("v0.1.yaml")
        new = _yaml("v1.1.yaml")
        self.assertEqual(old["required_plugins"], ["context-fabric", "perseus", "sefaria", "sedra"])
        self.assertEqual(new["release"], "v1.1")
        self.assertEqual(
            new["required_plugins"],
            ["context-fabric", "perseus", "sefaria", "sedra", "cal"],
        )
        self.assertEqual(new["required_resources"], old["required_resources"])

    def test_cal_registry_identity_and_low_risk_evidence(self) -> None:
        plugins = _yaml("plugins.yaml")["plugins"]
        plugin = next(item for item in plugins if item["id"] == "cal")
        providers = _yaml("providers.yaml")["providers"]
        provider = next(item for item in providers if item["id"] == "cal")
        self.assertEqual(plugin["upstream"]["repository"], "alexsosn/CAL-MCP")
        self.assertEqual(plugin["runtime"]["mode"], "local")
        self.assertEqual(plugin["data_mode"], "remote")
        self.assertEqual(plugin["licenses"]["software"], "MIT")
        self.assertEqual(plugin["licenses"]["data"], "upstream-dependent")
        self.assertEqual(provider["plugin"], "cal")
        self.assertEqual(provider["health"]["status"], "unknown")
        self.assertEqual(plugin["verification"]["status"], "community")
        for client in ("claude", "codex"):
            self.assertEqual(plugin["verification"]["clients"][client]["status"], "community")
            self.assertEqual(plugin["verification"]["clients"][client]["transport"], "stdio")
            launch = plugin["runtime"]["launch"][client]
            self.assertEqual(launch["command"], "uvx")
            self.assertEqual(launch["args"][-3:], ["--from", "cal-mcp==0.1.0", "cal-mcp"])

    def test_generated_client_artifacts_are_in_post_one_scope(self) -> None:
        outputs = render_outputs()
        for client in ("claude", "codex"):
            artifact = ROOT / f"plugins/cal/.{client}-plugin/mcp.json"
            self.assertIn(artifact, outputs)
            actual = json.loads(artifact.read_text(encoding="utf-8"))
            target = actual["cal"] if client == "claude" else actual["mcpServers"]["cal"]
            self.assertEqual(target["command"], "uvx")
            self.assertEqual(target["args"][-3:], ["--from", "cal-mcp==0.1.0", "cal-mcp"])
        self.assertEqual(check_outputs(), [])

    def test_upstream_one_call_smoke_contract_is_only_one_cal_lookup(self) -> None:
        guidance = (ROOT / "plugins" / "cal" / "README.md").read_text(encoding="utf-8")
        self.assertIn("cal-mcp==0.1.0", guidance)
        self.assertIn("cal_lexicon_lookup", guidance)
        self.assertIn('"query": "br"', guidance)
        self.assertIn('"lemma_key": "br N"', guidance)
        self.assertIn("one CAL", guidance)
        self.assertIn("upstream-dependent", guidance)

        workflow = (ROOT / ".github/workflows/cal-mcp-smoke.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('CAL_MCP_LIVE_SMOKE_MAX_ATTEMPTS: "25"', workflow)
        self.assertIn('"actual_cal_transport_attempts": 2', workflow)
        self.assertIn("mcp-live/cal-codex", workflow)


if __name__ == "__main__":
    unittest.main()
