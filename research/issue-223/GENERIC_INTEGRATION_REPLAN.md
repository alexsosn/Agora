# ORACC-TF #223 — adopt the generic release-backed corpus resolver

## Independent source/review finding (11 October 2026)

The first ORACC draft (#258) duplicated the new generic `github-release-archive`
resolver from #260 with an incompatible `acquisition.release` descriptor and
a separate download/cache-receipt manager. Merging both as-is is unsafe and
non-maintainable. This branch is based on exact reviewed #260 head
`3f49fddd9dfe04814c0d502f6bbd4e45da95d18c` and intentionally
**does not** include the custom `release_resource.py` implementation or
patch the generic resolver/cache. The generic `acquisition.archive` contract
is the sole accepted mechanism. Do not merge #223 before the generic PR #260.

## Exact real published asset identity

- ORACC-TF [v1.0.0](https://github.com/alexsosn/ORACC-TF/releases/tag/v1.0.0)
  published 2026-10-11, source tag commit
  `60db4b724a687c0f425e78eae924fce89454e106`.
- `assyrian-royal-inscriptions-1.0.0.zip` **41,285,702 bytes**, SHA-256
  `788f580604e30054fab34c4c3ea60ec3eb4f399412f1da90f778469d03507468`.
- Release identity **1.0.0** and native TF **schema/data version 0.4.0**
  are different and never silently equated.
- Standalone root includes `manifest.json`, `tf/0.4.0/`, `app/`, `docs/`.
  The shared generic acquirer copies only native verified TF features, not
  the upstream app, converter code or manual. The exact compressed SHA pins
  the bundled root manifest indirectly; the generic acquirer does not expose
  or independently attest all manifest fields.
- Source rights are component-specific. RIAO/RINAP corpusjson may assert CC0
  even where edition/project materials claim CC BY-SA 3.0; official TEI
  translation rights must be tracked separately. MIT applies to converter
  software, not all source text. Documentation links are pinned to v1.0.0.

## Research → plan → RED → implementation → review gates

1. Preserve v1 37-resource baseline, register one new corpus with typed
   `archive.release_tag/asset_name/sha256/compressed_bytes/version`.
   No guessed Git `tf_path`, no clone of multi-GB builder.
2. RED tests assert canonical/bundled catalog agreement; schema rejects
   missing SHA, unsafe ZIP paths and obsolete duplicate `release` descriptor;
   offline cold miss never invokes Git/network; metadata exposes pinned source.
3. Implementation makes no custom downloader or cache manager. Generic #260
   `download_pinned_release` → `staged_verified_tf_zip` →
   `ReleaseSnapshots` owns atomic publication, integrity receipts, leases
   and offline source policy.
4. Exact-head CI must download the **public pinned ZIP**, query actual native
   Text-Fabric for qualified document `riao/ria1:Q001801`, line
   `Q001801.1`, source word `E₂`, sign `𒂍`, translation-line edge;
   unload and reopen under `source_mode="offline"` from fresh resolver.
   Keep synthetic malicious/corrupt ZIP regressions of #260 green.
5. Run Foundation, generated catalogs/guides, load and local import smoke;
   independent adversarial review of both producer ZIP and changed Agora
   source. Merge/rebase generic core #260 first, then retarget/rebase this
   ORACC-specific PR and close old draft #258 without merging two loaders.

Non-goals: all ORACC subprojects, running the original TF web app from
the Agora MCP plugin, licensing the whole source dataset as MIT/CC0,
scholarly verification of every alignment or incomplete original TEI stub.
