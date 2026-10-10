# Agora #214 — full registered Coptic TT → Text-Fabric → Context-Fabric

## Research before implementation (2026-10-10)

The production `scripts/agora_materialize_registered.py` calls
`host.materialize(..., source=None)` when CLI `--source` is omitted,
forcing the immutable Git acquisition strategy in the installed Coptic
manifest. Explicit installation requires `--approve-code-execution` and
provides the verified v3 environment and execution-identity receipts.
The host executes `copticscriptorium_tf.agora` in required network-denied
Bubblewrap and atomically publishes `output/tf` together with
`agora-materialization.json` (host-owned provenance) and
`conversion-summary.json` (converter's operational report).

Pinned upstream `CopticScriptorium/corpora@3ac067f1709a0012daf39ea8da2fac79980176a5`:
565 exact TT Git blobs, 220,289,125 raw bytes verified via Agora #210 real
Git checkout. Direct Coptic full-converter test previously observed 2,628 source
records, 2,394,354 word slots and ~130 native `.tf` features; verify those
counts on real final artifact, never infer them from number of Git objects.
Coptic #68 verified one real Thomas TT source with 6,521 slots in the actual
host; Agora #213 registered-install synthetic fixture and full Context-Fabric
MCP lifecycle passed on immutable Coptic release `60fec735...`.

Failure modes to investigate: partial Git remote fetch/checkout timeout
(~15.5 minutes already observed), cumulative disk usage (especially installed
wheel, Git checkout, staged TF, TF cache copy), high parser/graph/writer peak
RSS, full-load memory, license metadata omissions, and host cleanup on failure.
Record timings and capacity rather than claiming guaranteed performance.

## RED → plan → implement → exact-head CI → skeptical independent review

1. RED-first `tests/test_issue214_coptic_full_registered.py` requires
   dedicated real-source workflow and a tested Python verifier, absence of
   any `--source` override, positive `source.type=git` and exact immutable
   source commit and patterns, required sandbox, full expected counts, native
   TF load, and actual Context-Fabric MCP lifecycle.
2. Create dedicated `coptic-registered-full-source.yml` with 75-minute
   job cap, explicitly approved installation, isolated temp install/output,
   real full remote acquisition (not test-only sparse pattern replacement),
   Bubblewrap required, `/usr/bin/time -v` metrics, final disk/resource
   diagnostics even on failure.
3. Add `tests/live_issue214_full_coptic.py` as standalone acceptance driver
   to check host receipt and native TF before launching Context-Fabric
   install/prepare/load/search/unload/remove. Validate no structural
   JSON/XML blob features; maintain per-record license/provenance features.
4. Dedicated full run **may fail** on runner quota or process memory;
   do not weaken counts, silently subset the input, or change the network
   boundary. Record exact failure and create a bounded resource/streaming
   follow-up. Do not merge code or mark acceptance passed until exact-head
   GitHub workflow green and independent adversarial review.
5. Only after the complete composed registered path is proven, reconcile
   parent Agora #205 and Coptic #17.

## Scope

No committed/circulated generated corpus. No license aggregation or
scholarly corpus certification. This verifies reproducible technical
conversion of pinned upstream inputs into native TF and interactive
Context-Fabric retrieval.
