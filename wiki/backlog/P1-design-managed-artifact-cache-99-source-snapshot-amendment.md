# Design amendment: immutable source snapshot for managed artifacts (#99)

## Status

This amendment is normative for #99 and overrides the earlier research/plan wording that treated a pre-run and post-run hash of the caller's live source tree as sufficient to close source mutation TOCTOU.

A fresh adversarial review found an ABA gap: a non-cooperating host process can change live source bytes while the converter reads them and restore the original bytes before the post-run hash. Pre/post equality can therefore coexist with converter output derived from transient bytes.

## Required source model

Every managed materialization build, reusable or one-shot, must execute from an Agora-owned frozen input snapshot. The converter must never read the caller's live source directory after the snapshot has been accepted.

For a directory source, the managed wrapper must establish one private snapshot with these properties:

- its payload bytes are immutable for the duration of the converter run;
- symlinks and path escapes are rejected under the same or stricter policy as the current materialization host;
- its canonical content tree digest is the source-tree identity recorded in the managed request/receipt;
- any resolved source revision passed to the materializer is captured as part of the accepted source identity and must remain consistent across snapshot acquisition;
- the sandbox receives the frozen snapshot as its read-only `/input`, not the caller's original path;
- absolute caller path and local basename remain non-identity/private and are absent from the managed public descriptor/receipt identity fields.

The one-shot path uses the same source snapshot seam even though it does not receive deterministic request-key lookup. That keeps provenance and execution semantics uniform and prevents a one-shot receipt from claiming bytes different from those actually consumed.

## Race-safe acquisition contract

A plain recursive copy is not sufficient by itself because the caller tree can change while it is copied. The implementation must use a fail-closed acquisition protocol equivalent to:

1. validate and compute live source identity A;
2. copy/materialize the source into a new private Agora staging snapshot while rejecting unsupported links/special paths;
3. compute the snapshot identity S from the completed frozen copy;
4. recompute live source identity B;
5. accept only when the content identity represented by A, S and B is equal and any semantically relevant resolved revision is unchanged;
6. after acceptance, execute only from S.

The exact implementation may avoid redundant full scans if it can prove equivalent byte stability, but it must preserve the same fail-closed property. Files disappearing, changing type, becoming symlinks, or changing content during acquisition must not yield a final managed artifact.

Once S is accepted, later mutation of the original source during converter execution does not invalidate the already-frozen execution input: the converter must continue to observe S. A later live-source recheck may be retained as diagnostic/conservative policy, but it is not the integrity primitive and must not replace the frozen snapshot contract.

## Reusable request identity

For reusable materializers, the request key binds the accepted frozen snapshot identity, not a hash of a path that remains live during execution.

At minimum the source component remains:

```text
source type
accepted snapshot tree SHA-256
resolved source revision when semantically observable/passed
```

Cache root, snapshot staging path, caller absolute path, caller basename and timestamps remain excluded.

The existing #103 execution identity/attestation and all other request-key inputs remain unchanged.

## Execution consistency

The source snapshot and materializer runtime are separate consistency domains:

- source snapshot acquisition completes before converter execution;
- #103 authorization still comes only from the integrity-verified installed runtime;
- a reusable miss still re-verifies actual runtime identity/attestation under the registered-runner lock before executing;
- the converter receives the accepted frozen source snapshot while that runtime consistency check is in force;
- no source snapshot operation may fetch/install/repair a materializer.

Publication still happens only after converter success, output validation, payload-manifest construction and receipt construction.

## Required RED additions before GREEN

Add focused tests proving at least:

1. a live source mutated and then restored while the converter is running cannot change what the converter observes; output must correspond only to the frozen accepted snapshot;
2. mutation during snapshot acquisition causes the acquisition/build to fail closed and exposes no final artifact;
3. a file-to-directory, directory-to-file, symlink, deletion or addition race during acquisition is rejected;
4. the request/receipt source tree digest equals the frozen snapshot actually mounted to the converter;
5. resolved source revision drift during acquisition is rejected when that revision is semantically passed to the materializer;
6. the frozen staging path and original caller path/basename do not appear in request identity or public descriptor fields;
7. identical reusable requests made from different filesystem locations can still share identity when their accepted snapshot bytes/revision and all other key inputs are equal;
8. one-shot builds also execute from a frozen source snapshot but remain distinct artifacts and never gain request-key reuse;
9. no accepted frozen source snapshot survives as a visible final cache object when converter/output/receipt publication later fails;
10. snapshot cleanup is bounded/private and does not introduce recursive constructor/startup cleanup.

These tests are additive to the existing RED4/RED5/RED6 source/runtime race contracts. Any older test that merely expects "mutate during converter => post-run hash failure" should be replaced by the stronger assertion that converter input itself is frozen.

## Lock/order implications

The source snapshot should be acquired before long publication/runtime operations wherever possible. Do not hold the reusable publish lock while performing an unbounded caller-tree copy unless the bounded design explicitly requires it; if the key depends on the accepted snapshot identity, acquire/freeze the snapshot first, then resolve current #103 authorization and derive/acquire the request-key lock.

After waiting for the request-key lock, revalidate the authority/key inputs that can change (registry/runtime policy). The accepted frozen source snapshot itself is immutable and need not be reconstructed solely because another caller held the publish lock.

No managed-artifact compile lock is held during source snapshot acquisition or converter execution.

## Definition of done amendment

#99's source TOCTOU requirement is satisfied only when the bytes used for source identity are the same frozen bytes made visible to the converter. Equality of two hashes of a still-live caller directory is insufficient evidence.