# Design amendment: bind managed artifacts to a private source snapshot (#99)

## Status

Normative amendment to `P1-design-managed-artifact-cache-99.md` after independent adversarial review. Where the earlier plan says that pre/post hashing of the caller-owned source closes the source TOCTOU, this document overrides it.

## Review finding

Two equal hashes observed before and after execution do not prove that the converter consumed those bytes.

A host process can:

1. leave source bytes in state A for the pre-run hash;
2. change one or more files to state B while the converter reads them;
3. restore state A before the post-run hash.

The two observations both identify A, but the converter may have produced output from B. A reusable request key and durable receipt would then make a false statement about the source bytes that produced the artifact.

The sandbox's read-only source mount does not solve this because it prevents writes by the sandboxed child, not writes by another host process to the underlying source.

## Corrected source trust boundary

Managed materialization must execute from a **private contained source snapshot whose bytes are the bytes used to derive `SourceIdentity`**. Caller-owned mutable paths are acquisition inputs, not execution identity after snapshot capture.

For v1, correctness takes priority over avoiding the snapshot-copy cost. Optimization may be added later only if it preserves the same exact-byte guarantee.

### Snapshot capture

For every managed build, reusable or one-shot:

1. validate the caller source against the materializer input contract, including the existing symlink policy;
2. observe a pre-capture identity of the caller source;
3. copy the accepted source into a private staging snapshot using contained, symlink-safe filesystem operations;
4. derive the canonical `SourceIdentity` from the **private snapshot**, not from the caller path;
5. observe the caller source again immediately after capture;
6. require the caller pre-capture identity, snapshot identity, and caller post-capture identity to agree on all content-bearing components; otherwise discard the snapshot and fail closed (or restart capture under an explicitly bounded retry policy defined later);
7. execute the converter with the existing sandbox pointed at the private snapshot;
8. never re-point the execution to the original mutable source after identity is established.

The pre/snapshot/post equality check detects changes captured during the copy. After successful capture, later mutations of the original source cannot affect converter reads because execution uses the private snapshot.

For a single-file input the same rule applies: copy the accepted file into a private source-snapshot location and hash the copied bytes. For directory inputs, the snapshot preserves only source structure/data needed by the declared input contract; it must not follow symlinks or escape the caller root.

### Resolved revision

If source provenance exposes a resolved Git commit that is semantically passed to the materializer, record it as an additional identity component only when the capture logic verifies it consistently with the caller source observation. The content tree digest remains authoritative for the bytes actually presented to the converter.

A Git commit string alone must never substitute for the private byte snapshot when the converter consumes a caller working tree that can differ from that commit.

## Reusable lookup ordering

The corrected reusable flow is:

1. capture and validate the private source snapshot;
2. derive `SourceIdentity` from that snapshot;
3. resolve current #103 cacheability authorization;
4. derive/acquire the reusable request-key lock;
5. after waiting, re-resolve authorization; the private source snapshot remains unchanged and therefore does not need to be re-read from the caller path;
6. validate/reuse an existing winner, or execute the converter against the same private snapshot under the expected runtime/attestation consistency checks;
7. publish the managed object transactionally;
8. release the publication lock;
9. delete the temporary private source snapshot after the request completes.

A cache hit may therefore pay source-capture cost in v1. Do not replace this with an unsafe hash-only fast path without a separately reviewed stable-source proof.

## One-shot ordering

Unknown/non-reusable managed execution uses the same snapshot capture. It receives no deterministic request-key lookup, but its receipt still truthfully identifies the exact snapshot bytes consumed by the converter.

## Privacy and lifecycle

- source snapshot paths are internal implementation details and never enter the reusable key, receipt public descriptor, logs, or artifact ID;
- snapshot staging is private (`0700` directory semantics on POSIX where applicable);
- source snapshots are request-temporary, not durable artifacts and not cache objects;
- a failed capture or execution leaves no published artifact;
- abandoned snapshot staging after process death is handled only by explicit/bounded housekeeping, not recursive constructor/startup cleanup;
- no workflow uploads a captured source snapshot.

## Required RED changes

Before production implementation, #99 tests must freeze at least:

1. the converter reads from the managed private snapshot, not the original caller path;
2. mutating the original source after successful capture but while the converter runs cannot change converter output or `SourceIdentity`;
3. a mutation that affects bytes while snapshot capture is in progress makes pre/snapshot/post identities disagree and publication fails closed;
4. restoring the original source before execution completes cannot manufacture a false matching receipt because execution no longer reads the original path;
5. source snapshot path spelling, cache root and caller basename never enter request identity or public descriptors;
6. symlink insertion/replacement during capture cannot escape the source root or make the snapshot follow an unapproved target;
7. reusable losers/winners operate on the exact captured source identity used to derive the key;
8. one-shot builds use the same exact-byte source binding even though they never receive request-key reuse;
9. capture failure, source instability or snapshot validation failure leaves no final managed object;
10. the existing registered runner and sandbox receive a source argument resolving to the private snapshot without weakening normal explicit-source validation.

## Impact on earlier slices

- **Slice 1:** `SourceIdentity` remains privacy-bounded but is explicitly snapshot-derived.
- **Slice 2:** source snapshots are staging inputs, not object payload and not receipt files.
- **Slice 4:** replace the earlier "rehash before/after converter execution" source-TOCTOU contract with the capture contract above. Runtime/authorization TOCTOU requirements remain unchanged.
- **Slice 5:** one-shot orchestration must snapshot before execution.
- **Slice 6:** reusable lookup/build must snapshot before request-key authority is exercised.
- **Slice 7:** source snapshots are not exposed through artifact lifecycle APIs.

## Definition of done amendment

#99 may claim source-bound managed artifact provenance only when the converter is proven to have consumed the exact private snapshot bytes represented by `SourceIdentity`. Equality of two observations of a mutable caller path is not sufficient evidence.
