from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.collection_index import (
    build_collection_index,
    index_from_document,
    index_to_document,
    member_id_from_identity,
    member_identity_path,
    parse_tf_header,
)


REVISION = "a" * 40
DUPLICATE_STRUCTURE_ISSUE = "context-fabric/duplicate-structure-levels"


class CollectionIndexGenerationTests(unittest.TestCase):
    def test_deep_cts_like_root_has_version_independent_identity_and_id(self):
        root_v1 = "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0"
        root_v2 = "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/2.0"
        identity = "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1"
        self.assertEqual(member_identity_path(root_v1), identity)
        self.assertEqual(member_identity_path(root_v2), identity)
        self.assertEqual(
            member_id_from_identity(member_identity_path(root_v1)),
            member_id_from_identity(member_identity_path(root_v2)),
        )

    def test_translatin_root_strips_tf_version_but_keeps_manifestation_identity(self):
        self.assertEqual(member_identity_path("tf/M1043/0.1.2"), "tf/M1043")
        self.assertEqual(member_identity_path("tf/M1043/0.2.0"), "tf/M1043")

    def test_tf_header_parser_stops_before_feature_data(self):
        parsed = parse_tf_header(
            [
                "@node",
                "@author=Homer",
                "@title=Iliad (Greek). Machine readable text",
                "@filename=tlg0012.tlg001.perseus-grc2",
                "@edition=Oxford, 1920",
                "",
                "113397\tIliad",
                "this must not be parsed",
            ]
        )
        self.assertEqual(parsed["author"], "Homer")
        self.assertEqual(parsed["title"], "Iliad (Greek). Machine readable text")
        self.assertEqual(parsed["filename"], "tlg0012.tlg001.perseus-grc2")
        self.assertNotIn("113397", parsed)

    def test_generation_uses_source_metadata_not_two_component_path_guessing(self):
        roots = [
            "Archive/Volume/tf/1.0",
            "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
        ]

        def metadata_reader(tf_path: str):
            if tf_path.startswith("canonical-greekLit/"):
                return {
                    "author": "Homer",
                    "title": "Iliad (Greek). Machine readable text",
                    "filename": "tlg0012.tlg001.perseus-grc2",
                    "edition": "Oxford, 1920",
                }
            return {}

        index = build_collection_index(
            collection_id="greek_literature",
            source_revision=REVISION,
            roots=roots,
            languages=("greek",),
            metadata_reader=metadata_reader,
        )
        by_path = {member.path: member for member in index.members}
        neutral = by_path["Archive/Volume"]
        self.assertIsNone(neutral.author)
        self.assertIsNone(neutral.title)
        self.assertIsNone(neutral.canonical_id)

        iliad = by_path["canonical-greekLit/tlg0012/tlg001/perseus-grc2/1"]
        self.assertEqual(iliad.author, "Homer")
        self.assertEqual(iliad.title, "Iliad (Greek). Machine readable text")
        self.assertEqual(iliad.canonical_id, "tlg0012.tlg001.perseus-grc2")
        self.assertEqual(iliad.edition, "Oxford, 1920")

    def test_generation_selects_latest_tf_version_without_changing_member_id(self):
        roots = ["Homer/Iliad/tf/1.0", "Homer/Iliad/tf/2.0"]
        first = build_collection_index(
            collection_id="greek",
            source_revision=REVISION,
            roots=roots[:1],
            languages=("greek",),
            metadata_reader=lambda _path: {"author": "Homer", "_book": "Iliad"},
        )
        second = build_collection_index(
            collection_id="greek",
            source_revision=REVISION,
            roots=roots,
            languages=("greek",),
            metadata_reader=lambda _path: {"author": "Homer", "_book": "Iliad"},
        )
        self.assertEqual(first.members[0].id, second.members[0].id)
        self.assertEqual(second.members[0].tf_path, "Homer/Iliad/tf/2.0")
        self.assertEqual(second.members[0].title, "Iliad")

    def test_generated_index_is_revision_bound_complete_and_conservative(self):
        index = build_collection_index(
            collection_id="greek",
            source_revision=REVISION,
            roots=["Homer/Odyssey/tf/1.0", "Homer/Iliad/tf/1.0"],
            languages=("greek",),
            metadata_reader=lambda _path: {},
        )
        self.assertEqual(index.collection_id, "greek")
        self.assertEqual(index.source_revision, REVISION)
        self.assertEqual(index.index_status, "complete")
        self.assertEqual(
            [member.path for member in index.members],
            ["Homer/Iliad", "Homer/Odyssey"],
        )
        for member in index.members:
            self.assertEqual(member.verification_status, "community")
            self.assertEqual(member.verification_evidence, ())
            self.assertEqual(member.verification_known_issues, ())

    def test_duplicate_structure_types_are_classified_as_known_issue(self):
        index = build_collection_index(
            collection_id="greek_literature",
            source_revision=REVISION,
            roots=["Homer/Iliad/tf/1.0"],
            languages=("greek",),
            metadata_reader=lambda _path: {
                "author": "Homer",
                "structureTypes": "_book,book,card,card,_sentence,_phrase",
            },
        )
        self.assertEqual(
            index.members[0].verification_known_issues,
            (DUPLICATE_STRUCTURE_ISSUE,),
        )

    def test_unique_or_missing_structure_types_are_not_classified(self):
        unique = build_collection_index(
            collection_id="greek_literature",
            source_revision=REVISION,
            roots=["Homer/Iliad/tf/1.0"],
            languages=("greek",),
            metadata_reader=lambda _path: {
                "structureTypes": "_book,book,chapter,_sentence,_phrase",
            },
        )
        missing = build_collection_index(
            collection_id="greek_literature",
            source_revision=REVISION,
            roots=["Homer/Odyssey/tf/1.0"],
            languages=("greek",),
            metadata_reader=lambda _path: {},
        )
        self.assertEqual(unique.members[0].verification_known_issues, ())
        self.assertEqual(missing.members[0].verification_known_issues, ())

    def test_member_known_issue_round_trips_through_index_document(self):
        index = build_collection_index(
            collection_id="greek_literature",
            source_revision=REVISION,
            roots=["Homer/Iliad/tf/1.0"],
            languages=("greek",),
            metadata_reader=lambda _path: {"structureTypes": "book,card,card"},
        )
        restored = index_from_document(index_to_document(index))
        self.assertEqual(
            restored.members[0].verification_known_issues,
            (DUPLICATE_STRUCTURE_ISSUE,),
        )
        self.assertEqual(
            index_to_document(restored)["members"][0]["verification"]["known_issues"],
            [{"issue_id": DUPLICATE_STRUCTURE_ISSUE}],
        )

    def test_source_revision_must_be_full_immutable_commit(self):
        with self.assertRaisesRegex(ValueError, "immutable commit"):
            build_collection_index(
                collection_id="greek",
                source_revision="main",
                roots=["Homer/Iliad/tf/1.0"],
                languages=("greek",),
                metadata_reader=lambda _path: {},
            )


if __name__ == "__main__":
    unittest.main()
