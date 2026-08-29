from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
SEDRA_SRC = ROOT / "plugins" / "sedra" / "src"
if str(SEDRA_SRC) not in sys.path:
    sys.path.insert(0, str(SEDRA_SRC))

from agora_sedra.client import SedraAPIError, SedraClient
from agora_sedra.mcp_tools import register_tools


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class SedraClientTests(unittest.TestCase):
    def test_word_lookup_percent_encodes_syriac_and_requests_json(self):
        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, timeout, dict(request.header_items())))
            return FakeResponse([{"id": 30862, "syriac": "ܐܒܪܐ"}])

        client = SedraClient(opener=opener)
        result = client.lookup_word("ܐܒܪܐ")
        self.assertEqual(result[0]["id"], 30862)
        url, timeout, headers = calls[0]
        self.assertEqual(
            url,
            "https://sedra.bethmardutho.org/api/word/%DC%90%DC%92%DC%AA%DC%90.json",
        )
        self.assertEqual(timeout, 20.0)
        self.assertEqual(headers["Accept"], "application/json")

    def test_word_lookup_accepts_sedra_word_id(self):
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            return FakeResponse({"id": 30862})

        result = SedraClient(opener=opener).lookup_word(30862)
        self.assertEqual(result["id"], 30862)
        self.assertEqual(
            calls,
            ["https://sedra.bethmardutho.org/api/word/30862.json"],
        )

    def test_lexeme_lookup_requires_positive_numeric_id(self):
        client = SedraClient(opener=lambda *_args, **_kwargs: FakeResponse({}))
        for invalid in (0, -1, "", "abc"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    client.get_lexeme(invalid)

    def test_http_errors_become_domain_errors(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

        with self.assertRaisesRegex(SedraAPIError, "HTTP 404"):
            SedraClient(opener=opener).get_lexeme(999999999)

    def test_invalid_json_is_reported(self):
        class InvalidResponse(FakeResponse):
            def read(self):
                return b"not-json"

        client = SedraClient(opener=lambda *_args, **_kwargs: InvalidResponse(None))
        with self.assertRaisesRegex(SedraAPIError, "invalid JSON"):
            client.lookup_word("ܐܒܪܐ")


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, function):
        self.tools[function.__name__] = function
        return function


class SedraToolTests(unittest.TestCase):
    def test_registers_exact_read_only_tool_set(self):
        mcp = FakeMCP()
        client = object()
        register_tools(mcp, client)
        self.assertEqual(set(mcp.tools), {"lookup_word", "get_lexeme"})

    def test_tools_delegate_without_reinterpreting_sedra_data(self):
        class Client:
            def __init__(self):
                self.calls = []

            def lookup_word(self, query):
                self.calls.append(("word", query))
                return [{"word": query}]

            def get_lexeme(self, lexeme_id):
                self.calls.append(("lexeme", lexeme_id))
                return {"id": lexeme_id}

        client = Client()
        mcp = FakeMCP()
        register_tools(mcp, client)
        self.assertEqual(mcp.tools["lookup_word"]("ܟܬܒ"), [{"word": "ܟܬܒ"}])
        self.assertEqual(mcp.tools["get_lexeme"](42), {"id": 42})
        self.assertEqual(client.calls, [("word", "ܟܬܒ"), ("lexeme", 42)])


if __name__ == "__main__":
    unittest.main()
