from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import check_materializer_releases as updates


ROOT = Path(__file__).resolve().parents[1]
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
COMMIT_C = "c" * 40


def _plugin() -> dict:
    return {
        "id": "example-converter",
        "name": "Example converter",
        "description": "Example.",
        "repository": "example/converter",
        "ref": COMMIT_A,
        "version": "1.2.3",
        "manifest": "agora.materializer.json",
        "package": {
            "type": "python-project",
            "path": ".",
            "install_trust": "explicit-code-execution",
        },
        "materializers": ["first", "second"],
        "disciplines": ["digital-philology"],
        "licenses": {"software": "MIT", "data": "upstream-dependent"},
        "verification": {"status": "experimental"},
        "release_tracking": {
            "mode": "github-releases",
            "channel": "stable",
            "tag_prefix": "v",
        },
    }


def _materializer(materializer_id: str) -> dict:
    return {
        "id": materializer_id,
        "description": "Convert example XML.",
        "acquisition": [
            {
                "type": "git",
                "url": "https://github.com/example/data.git",
                "ref": COMMIT_C,
                "subpath": "data",
            }
        ],
        "input": {
            "type": "directory",
            "required_globs": ["*.xml"],
            "allow_symlinks": False,
        },
        "execution": {
            "type": "python-module",
            "module": "example_converter.cli",
            "args": ["{source}", "{output}"],
            "network": "deny",
        },
        "output": {
            "format": "text-fabric",
            "required_paths": ["otype.tf", "oslots.tf"],
        },
    }


def _manifest(
    *,
    name: str = "Example converter",
    repository: str | None = "example/converter",
    ids: list[str] | None = None,
) -> dict:
    ids = ids or ["first", "second"]
    plugin = {
        "id": "example-converter",
        "name": name,
        "version": "1.2.4",
    }
    if repository is not None:
        plugin["repository"] = repository
    return {
        "schema_version": 1,
        "plugin": plugin,
        "materializers": [_materializer(materializer_id) for materializer_id in ids],
    }


class FakeApi:
    def __init__(self, manifest: dict) -> None:
        self.manifest = manifest

    def list_releases(self, repository: str):
        return [
            {
                "id": 1,
                "tag_name": "v1.2.4",
                "draft": False,
                "prerelease": False,
                "html_url": "https://github.com/example/converter/releases/tag/v1.2.4",
            }
        ]

    def get_ref(self, repository: str, tag: str):
        return {"object": {"type": "commit", "sha": COMMIT_B}}

    def get_file(self, repository: str, path: str, ref: str):
        return json.dumps(self.manifest).encode("utf-8")


class CandidateBindingRegressionTests(unittest.TestCase):
    def test_candidate_name_drift_is_rejected_like_install_time_binding(self):
        with self.assertRaisesRegex(updates.ReleaseDiscoveryError, "name"):
            updates.discover_plugin_update(
                _plugin(),
                FakeApi(_manifest(name="Renamed converter")),
            )

    def test_candidate_missing_repository_is_rejected_like_install_time_binding(self):
        with self.assertRaisesRegex(updates.ReleaseDiscoveryError, "repository"):
            updates.discover_plugin_update(
                _plugin(),
                FakeApi(_manifest(repository=None)),
            )

    def test_candidate_materializer_order_drift_is_rejected_like_install_time_binding(self):
        with self.assertRaisesRegex(updates.ReleaseDiscoveryError, "materializer"):
            updates.discover_plugin_update(
                _plugin(),
                FakeApi(_manifest(ids=["second", "first"])),
            )


class WorkflowBaseRefRegressionTests(unittest.TestCase):
    def test_manual_dispatch_checkout_is_explicitly_based_on_main(self):
        text = (ROOT / ".github/workflows/materializer-release-updates.yml").read_text(
            encoding="utf-8"
        )
        checkout = text.index("uses: actions/checkout@v4")
        setup = text.index("- name: Set up Python", checkout)
        checkout_block = text[checkout:setup]
        self.assertIn("ref: main", checkout_block)


if __name__ == "__main__":
    unittest.main()
