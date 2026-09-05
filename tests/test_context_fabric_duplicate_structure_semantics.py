from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.collection_index import duplicate_structure_levels


class DuplicateStructureSemanticsTests(unittest.TestCase):
    def test_per_item_whitespace_is_not_normalized_beyond_upstream_itemize(self):
        # Context-Fabric itemize(value, ",") does value.strip().split(",").
        # It therefore treats "book" and " book" as distinct tokens.
        self.assertFalse(
            duplicate_structure_levels({"structureTypes": "book, book"})
        )

    def test_empty_tokens_are_preserved_like_upstream_itemize(self):
        # Two empty comma-separated levels are duplicates to Context-Fabric.
        self.assertTrue(
            duplicate_structure_levels({"structureTypes": "book,,"})
        )


if __name__ == "__main__":
    unittest.main()
