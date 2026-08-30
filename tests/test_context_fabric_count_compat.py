from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.compat import install_exact_count_compat


class FakeSearchApi:
    def __init__(
        self,
        results=None,
        *,
        search_results=None,
        error: Exception | None = None,
    ):
        self._results = results
        self._search_results = results if search_results is None else search_results
        self._error = error
        self.exe = SimpleNamespace(
            good=True,
            badSyntax=[],
            badSemantics=[],
            results=self._iter_results,
        )
        self.study_calls: list[str] = []
        self.search_calls: list[str] = []

    def _iter_results(self):
        if self._error is not None:
            raise self._error
        return iter(self._results or [])

    def study(self, template: str) -> None:
        self.study_calls.append(template)

    def search(self, template: str):
        self.search_calls.append(template)
        if self._error is not None:
            raise self._error
        return self._search_results


class ExactCountCompatTests(unittest.TestCase):
    def make_tools(self, search_api: FakeSearchApi):
        delegated_calls: list[tuple[tuple, dict]] = []

        def upstream_search(*args, **kwargs):
            delegated_calls.append((args, kwargs))
            return {
                "total_count": 10_000,
                "template": args[0] if args else kwargs["template"],
                "results": [],
            }

        tools = SimpleNamespace(
            search=upstream_search,
            corpus_manager=SimpleNamespace(
                current="cuc",
                get_api=lambda _corpus=None: SimpleNamespace(S=search_api),
            ),
            logger=logging.getLogger("test.cfabric_mcp.tools"),
        )
        return tools, delegated_calls

    def test_count_returns_cuc_word_total_above_cache_cap_without_replanning(self):
        search_api = FakeSearchApi([(node,) for node in range(27_770)])
        tools, delegated_calls = self.make_tools(search_api)
        install_exact_count_compat(tools)

        result = tools.search("word", return_type="count")

        self.assertEqual(result, {"total_count": 27_770, "template": "word"})
        self.assertEqual(search_api.study_calls, ["word"])
        self.assertEqual(search_api.search_calls, [])
        self.assertEqual(delegated_calls, [])

    def test_count_uses_uncapped_studied_results_instead_of_public_search_results(self):
        full_results = [(node,) for node in range(25)]
        search_api = FakeSearchApi(full_results, search_results=full_results[:20])
        tools, _delegated_calls = self.make_tools(search_api)
        install_exact_count_compat(tools)

        result = tools.search("word\nword", return_type="count")

        self.assertEqual(result["total_count"], 25)
        self.assertEqual(search_api.search_calls, [])

    def test_non_count_searches_keep_upstream_cache_and_pagination_path(self):
        search_api = FakeSearchApi([(node,) for node in range(27_770)])
        tools, delegated_calls = self.make_tools(search_api)
        install_exact_count_compat(tools)

        result = tools.search("word", return_type="results", limit=25)

        self.assertEqual(result["total_count"], 10_000)
        self.assertEqual(
            delegated_calls,
            [(("word",), {"return_type": "results", "limit": 25})],
        )
        self.assertEqual(search_api.search_calls, [])

    def test_count_execution_failure_is_reported_instead_of_as_an_exact_total(self):
        search_api = FakeSearchApi(error=RuntimeError("boom"))
        tools, _delegated_calls = self.make_tools(search_api)
        install_exact_count_compat(tools)

        result = tools.search("word", return_type="count")

        self.assertNotIn("total_count", result)
        self.assertEqual(result["template"], "word")
        self.assertFalse(result["exact"])
        self.assertIn("boom", result["error"])

    def test_installation_is_idempotent(self):
        search_api = FakeSearchApi([(1,), (2,)])
        tools, delegated_calls = self.make_tools(search_api)
        install_exact_count_compat(tools)
        first_wrapper = tools.search
        install_exact_count_compat(tools)

        self.assertIs(tools.search, first_wrapper)
        self.assertEqual(tools.search("word", return_type="count")["total_count"], 2)
        self.assertEqual(delegated_calls, [])


if __name__ == "__main__":
    unittest.main()
