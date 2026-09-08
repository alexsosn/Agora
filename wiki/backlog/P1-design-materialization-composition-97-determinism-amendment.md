# Design amendment: gate managed-artifact reuse on reviewed cacheability (#97 / #103)

## Required ordering change

The parent plan's Slice A must not implement request-identity reuse until #103 defines and lands reviewed materializer cacheability semantics.

Revised order:

1. #95 registered runner.
2. #103 cacheability contract and Burns/Pseudepigrapha dispositions.
3. #99 deterministic identity/receipt + validation/concurrency-safe cache, consuming #103 metadata.
4. #100 managed-artifact Context-Fabric load seam.
5. #101 end-to-end composition.

Current prerequisite status: #95 is merged on `main`; #103 remains the blocking research/design/TDD gate before reusable managed-artifact caching may begin.

## #99 RED additions

Before reuse behavior is implemented, tests must additionally freeze:

- unknown/legacy cacheability cannot produce a reusable cache hit;
- explicitly non-cacheable materializers may produce managed one-shot artifacts but are not served as request-identity hits;
- reusable entries bind the reviewed cacheability policy/attestation identity;
- cacheability metadata drift invalidates reuse;
- the cache key contains every identity input required by #103's determinism boundary;
- exact output tree hash verifies stored bytes but is not treated as evidence of rerun determinism.

## #100/#101 privacy additions

Public managed-artifact and composition responses must omit local source absolute paths and local source basenames by default. Tests should seed a conspicuously sensitive synthetic basename and assert it is absent from the public response while content/source type identity remains available.

## Review focus

Final independent review for #99 must explicitly challenge:

- hidden time/random/environment inputs;
- cacheability attestation drift;
- confusion between byte determinism and content determinism;
- accidental reuse of `unknown` materializers;
- leakage of local source naming through receipt-to-MCP projection.

No production implementation should encode a temporary `all registered materializers are deterministic` shortcut.
