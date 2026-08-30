from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "context-fabric"
PLUGIN_SRC = PLUGIN_ROOT / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from cfabric.core.config import SEARCH_FAIL_FACTOR
from cfabric.search.searchexe import SearchExe
from cfabric_mcp import tools as upstream_tools

from agora_context_fabric.compat import install_exact_count_compat
from agora_context_fabric.server import build_runtime


class StudiedSearchApi:
    """Search facade whose public search path reproduces SearchExe.fetch()."""

    def __init__(self, exe: SearchExe):
        self._prepared_exe = exe
        self.exe = None
        self.study_calls: list[str] = []
        self.search_calls: list[str] = []

    def study(self, template: str) -> None:
        self.study_calls.append(template)
        self.exe = self._prepared_exe

    def search(self, template: str):
        self.search_calls.append(template)
        return self._prepared_exe.fetch()


def make_real_search_exe(*, total_results: int, max_node: int) -> SearchExe:
    """Build the minimal state needed to exercise the real SearchExe.fetch()."""
    exe = object.__new__(SearchExe)
    exe.api = SimpleNamespace(
        F=SimpleNamespace(otype=SimpleNamespace(maxNode=max_node)),
    )
    exe.good = True
    exe.shallow = 0
    exe.results = lambda: ((node,) for node in range(total_results))
    return exe


class UpstreamCompatibilityTests(unittest.TestCase):
    def test_runtime_dependency_versions_are_the_reviewed_compatibility_boundary(self):
        self.assertEqual(version("cfabric-mcp"), "0.1.7")
        self.assertEqual(version("context-fabric"), "0.5.0")
        self.assertEqual(SEARCH_FAIL_FACTOR, 4)

    def test_exact_count_bypasses_real_searchexe_fetch_fail_cutoff(self):
        max_node = 5
        fail_limit = SEARCH_FAIL_FACTOR * max_node
        total_results = fail_limit + 7
        exe = make_real_search_exe(total_results=total_results, max_node=max_node)

        # Demonstrate the third-party behavior that caused the review finding.
        self.assertEqual(len(list(exe.fetch())), fail_limit)

        search_api = StudiedSearchApi(exe)
        delegated_calls: list[tuple[tuple, dict]] = []

        def upstream_search(*args, **kwargs):
            delegated_calls.append((args, kwargs))
            return {"total_count": fail_limit, "template": args[0]}

        tools = SimpleNamespace(
            search=upstream_search,
            corpus_manager=SimpleNamespace(
                current="fixture",
                get_api=lambda _corpus=None: SimpleNamespace(S=search_api),
            ),
            logger=logging.getLogger("test.cfabric_mcp.tools"),
        )
        install_exact_count_compat(tools)

        result = tools.search("word\nword", return_type="count")

        self.assertEqual(result, {"total_count": total_results, "template": "word\nword"})
        self.assertEqual(search_api.study_calls, ["word\nword"])
        self.assertEqual(search_api.search_calls, [])
        self.assertEqual(delegated_calls, [])

    def test_build_runtime_installs_shim_on_real_cfabric_mcp_tools_module(self):
        original_search = upstream_tools.search
        try:
            with tempfile.TemporaryDirectory() as tmp, patch(
                "agora_context_fabric.server.register_tools"
            ) as register_tools:
                build_runtime(Path(tmp), plugin_root=PLUGIN_ROOT)

            self.assertTrue(
                getattr(upstream_tools.search, "_agora_exact_count_compat", False)
            )
            register_tools.assert_called_once()
        finally:
            upstream_tools.search = original_search


if __name__ == "__main__":
    unittest.main()
