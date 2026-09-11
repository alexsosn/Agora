from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContextFabricLongOperationDocumentationTests(unittest.TestCase):
    def test_skill_and_cache_guide_explain_bounded_staged_workflow(self):
        skill = (
            ROOT / "plugins/context-fabric/skills/context-fabric-research/SKILL.md"
        ).read_text(encoding="utf-8")
        cache_guide = (
            ROOT / "wiki/guides/context-fabric-cache.md"
        ).read_text(encoding="utf-8")
        combined = f"{skill}\n{cache_guide}"

        for token in (
            "describe_available_corpus",
            "prepare_corpus",
            "load_corpus",
            "acquiring/materializing",
            "loading/compiling",
            "AGORA_CORPUS_ACQUISITION_MAX_MINUTES",
            "corpus_cache_status",
            "active_loads",
        ):
            self.assertIn(token, combined)

        lower = combined.lower()
        self.assertIn("do not retry", lower)
        self.assertIn("15", combined)
        self.assertIn("60", combined)
        self.assertIn("historical", lower)


if __name__ == "__main__":
    unittest.main()
