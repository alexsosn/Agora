"""#202 RED: normalize MCP SDK synthetic structured list/scalar wrappers."""
from __future__ import annotations

import json
from types import SimpleNamespace
import unittest


def payload(*, structured=None, text=None, is_error=False):
    blocks = [] if text is None else [SimpleNamespace(text=text)]
    return SimpleNamespace(
        isError=is_error,
        structuredContent=structured,
        content=blocks,
    )


class McpStructuredResultDecoderRedTests(unittest.TestCase):
    def decode(self, result):
        from scripts import context_fabric_mcp_result as decoder
        return decoder.decode_mcp_result(result, tool_name="list_available_corpora")

    def test_repaired_direct_local_import_smoke_is_executed_in_ci(self):
        from pathlib import Path

        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/context-fabric-local-import-smoke.yml"
        )
        self.assertTrue(workflow.is_file(), "RED: missing real stdio local-import CI")
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("python scripts/smoke_context_fabric_local_import.py", text)
        self.assertIn("pip install -e plugins/context-fabric", text)
        self.assertIn("contents: read", text)

    def test_wrapped_list_is_unwrapped_to_iterable_of_dicts(self):
        items = [{"id": "cuc"}, {"id": "bhsa"}]
        self.assertEqual(self.decode(payload(structured={"result": items})), items)

    def test_wrapped_scalar_and_nested_dict_unwrap(self):
        self.assertEqual(self.decode(payload(structured={"result": 12})), 12)
        self.assertEqual(self.decode(payload(structured={"result": {"count": 2}})), {"count": 2})

    def test_ordinary_dict_is_not_corrupted(self):
        doc = {"id": "cuc", "version": "0.2.8"}
        self.assertEqual(self.decode(payload(structured=doc)), doc)
        annotated = {"result": [{"id": "x"}], "context": {"verified": True}}
        self.assertEqual(self.decode(payload(structured=annotated)), annotated)

    def test_legacy_text_json_is_supported(self):
        self.assertEqual(
            self.decode(payload(text=json.dumps([{"id": "cuc"}]))),
            [{"id": "cuc"}],
        )

    def test_malformed_and_missing_text_fail_closed(self):
        with self.assertRaises((ValueError, RuntimeError)):
            self.decode(payload(text="{"))
        with self.assertRaises((ValueError, RuntimeError)):
            self.decode(payload())

    def test_tool_errors_are_not_hidden_by_structured_content(self):
        with self.assertRaisesRegex(RuntimeError, "list_available_corpora"):
            self.decode(payload(
                structured={"result": [{"id": "cuc"}]},
                text="permission denied",
                is_error=True,
            ))


if __name__ == "__main__":
    unittest.main()
