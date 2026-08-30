## Summary

<!-- What does this PR change? -->

## Scope ownership

For plugin-related changes, answer these before requesting review:

- [ ] I identified the **Agora-owned responsibility** this change serves (discovery, metadata, installation, launch, transport/configuration, Agora-owned resource resolution, verification, or permitted skills).
- [ ] I checked whether the underlying bug or missing capability still exists when the third-party plugin is run directly without Agora.
- [ ] If the problem is upstream-owned, I linked/reported it upstream and kept the Agora change to metadata, version constraints, documentation, or thin integration glue.
- [ ] Any adapter added here preserves upstream domain semantics and uses public upstream interfaces where practical.
- [ ] This PR does not monkey-patch third-party behavior, repair upstream domain results, or add a missing upstream scholarly capability without an explicit architecture decision.

## Skills

If this PR adds or changes a skill:

- [ ] It is a generic marketplace skill, a repository-maintenance skill, or facilitation of capabilities the upstream plugin already exposes.
- [ ] It does not emulate a missing upstream tool or silently correct an incorrect upstream result.
- [ ] A substantive third-party/domain skill has been contributed upstream instead when practical.

## Tests

- [ ] Tests cover Agora-owned contracts rather than reproducing a third-party semantic test suite.
- [ ] Generated marketplace artifacts are fresh where applicable (`python scripts/generate_marketplaces.py --check`).

See `wiki/architecture/ref-plugin-boundary.md` for the normative ownership policy.
