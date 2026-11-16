from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import scripts.smoke_context_fabric_resources as smoke


class _Feature:
    def __init__(self, values):
        self.values = values

    def v(self, node):
        return self.values.get(node)


class _Otype:
    def __init__(self, *, card_count=94):
        self.counts = {"word": 38904, "book": 4, "card": card_count}

    def s(self, otype):
        # The source otype.tf pins the node ranges, not just approximate sizes.
        if otype == "word":
            return range(1, 38905)
        if otype == "book":
            return range(47102, 47106)
        if otype == "card":
            return range(47106, 47106 + self.counts["card"])
        raise ValueError(otype)


class _Up:
    def __init__(self, nested=False):
        self.nested = nested

    def u(self, node, otype=None):
        if otype != "card":
            raise AssertionError("canary must query card containment explicitly")
        return [47106] if self.nested else []


def _api(*, first="ἀρχόμενος", second="σέο", nested=False, card_count=94):
    return SimpleNamespace(
        F=SimpleNamespace(main=_Feature({1: first, 2: second}),
                          otype=_Otype(card_count=card_count)),
        L=_Up(nested=nested),
    )


class _Fabric:
    api = None

    def __init__(self, *, locations, silent):
        self.locations = locations
        self.silent = silent

    def loadAll(self, *, silent):
        return self.api


class GreekDuplicateStructureCanaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dataset = Path(self.temp.name)
        (self.dataset / "otext.tf").write_text(
            "@config\n"
            "@sectionTypes=book,card,card\n"
            "@sectionFeatures=book,card,card\n"
            "@structureTypes=_book,book,card,card,_sentence,_phrase\n"
            "@structureFeatures=_book,book,card,card,_sentence,_phrase\n",
            encoding="utf-8",
        )

    def probe(self, api):
        class Fabric(_Fabric):
            pass

        Fabric.api = api
        return smoke.probe_duplicate_structure_canary(
            "greek-known-bad", self.dataset, fabric_factory=Fabric
        )

    def test_loaded_words_and_orphan_cards_remain_blocking(self):
        observed = self.probe(_api())
        self.assertEqual(observed["status"], "duplicate-structure-observed")
        self.assertEqual(observed["word_count"], 38904)
        self.assertEqual(observed["book_count"], 4)
        self.assertEqual(observed["card_count"], 94)
        self.assertEqual(observed["uncontained_card_nodes"], 94)
        self.assertEqual(
            [(item["feature"], item["node"], item["actual"])
             for item in observed["semantic_checks"]],
            [("main", 1, "ἀρχόμενος"), ("main", 2, "σέο")],
        )

    def test_canonical_node_order_is_not_assumed_numeric(self):
        # F.otype.s returns canonical order, not guaranteed numeric order.
        # Both orientations identify the same pinned source node range.
        api = _api()
        raw_otype = api.F.otype
        class ReversedOtype:
            def s(self, otype):
                return tuple(reversed(raw_otype.s(otype)))
        api.F.otype = ReversedOtype()
        observed = self.probe(api)
        self.assertEqual(observed["card_count"], 94)

    def test_changed_word_or_node_count_is_not_accepted(self):
        with self.assertRaisesRegex(RuntimeError, "expected.*wrong"):
            self.probe(_api(first="wrong"))
        with self.assertRaisesRegex(RuntimeError, "card.*expected 94"):
            self.probe(_api(card_count=93))

    def test_no_orphan_card_is_not_an_expected_duplicate_structure_canary(self):
        with self.assertRaisesRegex(RuntimeError, "uncontained card.*expected 94"):
            self.probe(_api(nested=True))

    def test_source_metadata_drift_fails_closed_before_loading(self):
        (self.dataset / "otext.tf").write_text(
            "@config\n@sectionTypes=book,card\n"
            "@structureTypes=_book,book,card,_sentence,_phrase\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RuntimeError, "source metadata"):
            self.probe(_api())

    def test_missing_api_and_upstream_exception_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "no API"):
            self.probe(None)

        class CrashingFabric(_Fabric):
            def loadAll(self, *, silent):
                raise ValueError("not enough values to unpack")

        with self.assertRaisesRegex(ValueError, "not enough values to unpack"):
            smoke.probe_duplicate_structure_canary(
                "greek-known-bad", self.dataset, fabric_factory=CrashingFabric
            )


if __name__ == "__main__":
    unittest.main()
