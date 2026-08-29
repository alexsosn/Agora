from __future__ import annotations

from typing import Any

from .client import SedraClient


def register_tools(mcp: Any, client: SedraClient) -> None:
    @mcp.tool
    def lookup_word(query: str) -> Any:
        """Look up a Syriac word in SEDRA IV.

        `query` may be a SEDRA word ID or Syriac Unicode in consonantal,
        partially vocalized, or fully vocalized form. SEDRA reports the
        candidate word forms and their grammatical/lexical metadata.
        """
        return client.lookup_word(query)

    @mcp.tool
    def get_lexeme(lexeme_id: int) -> Any:
        """Retrieve a SEDRA IV lexeme by numeric ID.

        Returns the upstream lexeme record, including Syriac form, root,
        category, glosses, etymological information, and linked word forms
        where supplied by SEDRA.
        """
        return client.get_lexeme(lexeme_id)
