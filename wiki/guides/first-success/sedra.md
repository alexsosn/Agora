# First success: Syriac word and lexeme lookup

## Start after installation

Open the installed **SEDRA** plugin. Agora runs a local adapter but looks up scholarly lexical data in the remote SEDRA IV service; provider availability can change.

## Try this

Ask the agent: “Look up the Syriac word **ܡܠܟܐ**. Preserve any competing analyses, follow one returned lexeme identifier, and distinguish word-form facts from lexeme facts.”

1. Use `lookup_word` with the actual Syriac Unicode spelling **ܡܠܟܐ**. Do not silently normalize, drop vowels or replace the spelling with Latin transliteration.
2. Inspect **multiple** candidates if returned: each word-form match is not necessarily a unique grammatical analysis. Preserve ambiguity instead of arbitrarily choosing the first candidate.
3. When a candidate supplies a **returned numeric** lexeme ID, use `get_lexeme` with that ID and report separately the word-form record and the lexeme record. If none was supplied, do **not** guess an ID.

## What success looks like

A returned word-form record (or an explicit no-match/provider-error report), followed when possible by a clearly identified lexeme record with the exact numeric ID and any unresolved alternative analyses. A gloss is a dictionary possibility, not automatically the correct meaning in a particular passage.

## Interpretation limits

SEDRA is a lexicon, not a contextual parser. A word-form candidate does not establish a unique passage-level reading; label each inference separately from returned source data. Network/API errors and no-match results are different conditions.

## Next steps

Consult [SEDRA's maintained guidance](../../../plugins/sedra/skills/sedra-research/SKILL.md#ambiguity-is-data), then compare a candidate lexeme with its actual passage context. For prerequisites and upstream links, use the [SEDRA plugin page](../plugins/sedra.md).
