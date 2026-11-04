"""#170 RED: first-success journeys must be real bounded plugin workflows."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import generate_plugin_docs

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "wiki/guides/README.md"
TUTORIALS = ROOT / "wiki/guides/first-success"
PLUGINS = ("context-fabric", "perseus", "sefaria", "sedra", "cal")
REQUIRED = {
    "context-fabric": (
        "describe_available_corpus", "prepare_corpus", "load_corpus",
        "lex", "sp", "word", "feature", "revision",
    ),
    "perseus": (
        "find_author_names", "get_work_resources", "get_scaife_library_metadata",
        "Iliad 1.1", "URN", "CTS", "Scaife",
    ),
    "sefaria": (
        "get_text", "get_links_between_texts", "Genesis 1:1",
        "Hebrew", "English", "duplicate",
    ),
    "sedra": (
        "lookup_word", "get_lexeme", "ܡܠܟܐ",
        "word-form", "lexeme", "ambig",
    ),
    "cal": ("cal_lexicon_lookup", "br N", "found", "provenance", "429"),
}


class FirstSuccessTutorialContracts(unittest.TestCase):
    def test_five_bounded_guides_have_findable_entrypoints_and_generators_agree(self):
        landing = GUIDE.read_text(encoding="utf-8")
        self.assertEqual({f"{p}.md" for p in PLUGINS},
                         {p.name for p in TUTORIALS.glob("*.md")})
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                link = f"first-success/{plugin}.md"
                self.assertIn(link, landing)
                detail = (ROOT / "wiki/guides/plugins" / f"{plugin}.md").read_text(encoding="utf-8")
                self.assertIn(f"../first-success/{plugin}.md", detail)
                doc = (TUTORIALS / f"{plugin}.md").read_text(encoding="utf-8")
                self.assertIn("## Start after installation", doc)
                self.assertIn("## Try this", doc)
                self.assertIn("## What success looks like", doc)
                self.assertIn("## Interpretation limits", doc)
                self.assertIn("## Next steps", doc)
                self.assertLess(len(doc), 4500, "Keep first-success guidance genuinely concise")
                self.assertIn("../plugins/" + plugin + ".md", doc)
                for term in REQUIRED[plugin]:
                    self.assertIn(term, doc)
        self.assertTrue(generate_plugin_docs.check())

    def test_bhsa_first_query_is_schema_first_and_reports_count_unit(self):
        body = (TUTORIALS / "context-fabric.md").read_text(encoding="utf-8")
        self.assertLess(body.index("prepare_corpus"), body.index("load_corpus"))
        self.assertLess(body.index("inspect"), body.index("query"))
        self.assertIn("counted unit", body)
        self.assertIn("source revision", body)
        self.assertIn("sp", body)
        self.assertIn("pdp", body)

    def test_perseus_does_not_advertise_legacy_navigation_as_required(self):
        body = (TUTORIALS / "perseus.md").read_text(encoding="utf-8")
        self.assertIn("discovered URN", body)
        self.assertIn("malformed", body.lower())
        self.assertIn("do not", body.lower())

    def test_sefaria_does_not_count_version_duplicate_search_rows(self):
        body = (TUTORIALS / "sefaria.md").read_text(encoding="utf-8")
        self.assertIn("version_language", body)
        self.assertIn("duplicate", body.lower())
        self.assertIn("not", body.lower())
        self.assertIn("version", body.lower())

    def test_sedra_keeps_multiple_analysis_paths(self):
        body = (TUTORIALS / "sedra.md").read_text(encoding="utf-8")
        self.assertIn("returned numeric", body)
        self.assertIn("multiple", body.lower())
        self.assertIn("do not", body.lower())


if __name__ == "__main__":
    unittest.main()
