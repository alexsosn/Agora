from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.collection_index import CollectionIndex, CollectionIndexMember
from scripts import generate_context_fabric_collection_indexes as generator


class ResourceMemberVerificationGenerationRed3Tests(unittest.TestCase):
    def test_collection_regeneration_preserves_canonical_trust_metadata_only(self):
        preserve = getattr(generator, "preserve_canonical_verification", None)
        self.assertTrue(
            callable(preserve),
            "collection regeneration must preserve canonical member status/evidence/notes",
        )
        generated = CollectionIndex(
            collection_id="greek_literature",
            source_revision="a" * 40,
            index_status="complete",
            members=(
                CollectionIndexMember(
                    id="iliad",
                    path="canonical-greekLit/tlg0012/tlg001/perseus-grc2/1",
                    tf_path="canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
                    languages=("greek",),
                    verification_status="community",
                    verification_known_issues=("context-fabric/source-derived",),
                ),
            ),
        )
        canonical = {
            "schema_version": 1,
            "collection_id": "greek_literature",
            "source_revision": "a" * 40,
            "index_status": "complete",
            "members": [
                {
                    "id": "iliad",
                    "path": "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1",
                    "tf_path": "canonical-greekLit/tlg0012/tlg001/perseus-grc2/1/tf/1.0",
                    "languages": ["greek"],
                    "verification": {
                        "status": "verified",
                        "evidence": [{"check_id": "member-load/greek-iliad"}],
                        "notes": ["Exact live representative load passed."],
                        "known_issues": [{"issue_id": "context-fabric/stale-manual"}],
                    },
                }
            ],
        }

        merged = preserve(generated, canonical)
        member = merged.members[0]
        self.assertEqual(member.verification_status, "verified")
        self.assertEqual(member.verification_evidence, ("member-load/greek-iliad",))
        self.assertEqual(member.verification_notes, ("Exact live representative load passed.",))
        self.assertEqual(
            member.verification_known_issues,
            ("context-fabric/source-derived",),
            "source-derived known issues must not be overwritten by canonical trust annotations",
        )


if __name__ == "__main__":
    unittest.main()
