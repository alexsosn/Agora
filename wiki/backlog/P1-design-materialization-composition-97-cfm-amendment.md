# Design amendment: reserve Context-Fabric `.cfm` outside converter-payload integrity (#97 / #99 / #100)

## Required correction

The parent plan's whole-artifact integrity wording must be interpreted as integrity of the **converter-owned published payload**, not every future byte below the directory Context-Fabric loads.

Current Context-Fabric intentionally writes `.cfm/<CFM_VERSION>/...` into the corpus path during cold compilation. Treating that consumer cache as materializer output would make ordinary loading invalidate the artifact.

A second current-runtime constraint is equally important: `GitStore.compile_lock(path)` is **not** a generic lock for arbitrary Text-Fabric directories. It first resolves `path` through `GitStore._managed_path()`, which accepts only GitStore `snapshots/` and `overlays/`. Managed materialization artifacts deliberately live outside that namespace. #100 therefore needs an explicit managed-artifact cold-compile lock rather than passing an external artifact path into the canonical GitStore lock.

## #99 changes

### Receipt contract

The managed-artifact receipt must contain an explicit deterministic payload manifest (or semantically equivalent structure) that binds every materializer-produced path at publication time by relative path, kind and content hash.

The receipt may additionally store one aggregate SHA-256 over that canonical manifest.

The top-level `.cfm` namespace is reserved for Context-Fabric and must be absent at materializer publication. A materializer attempting to emit it fails before final publication.

### Validation contract

Reuse/lookup validates the payload manifest rather than blindly hashing all descendants after consumers have used the artifact.

Validation must:

- fail on missing/modified recorded payload paths;
- re-check required materializer output paths;
- reject symlink/path escapes;
- allow only the explicitly reserved `.cfm/` consumer namespace outside the converter payload;
- not adopt unknown extra files into the payload after publication;
- not let `.cfm` bytes influence request identity/cacheability attestation.

### Lock namespace handoff

#99 must expose or reserve a stable cross-process lock namespace keyed by canonical `artifact_id`, or a small helper that #100 can safely reuse for artifact-scoped operations. Lock identity is the validated artifact ID, never a caller-supplied filesystem path.

The publication/build lock and later cold-compile lock may be distinct lock objects if that keeps lock ordering simple, but their ordering must be documented and tested. #100 must not hold a publication/mutation lock while entering a long Context-Fabric cold compile unless a later design explicitly proves that ordering safe.

### RED additions

Before GREEN implementation, add tests for reserved `.cfm` publication rejection, payload-manifest completeness, post-publication `.cfm` tolerance, payload tamper failure with `.cfm` present, rejection of unrelated unmanifested additions, and stable artifact-ID lock identity independent of cache-root/path spelling.

## #100 changes

The managed-artifact loader must treat `.cfm` as Context-Fabric-owned disposable compile state while preserving the converter payload receipt unchanged.

### Managed-artifact compile locking

Do **not** call canonical `GitStore.compile_lock()` with the managed-artifact path. That API is intentionally restricted to GitStore-managed cache objects and should remain unchanged for canonical Git-backed resources.

For managed artifacts, use a dedicated cross-process, crash-safe compile lock keyed by the already validated `artifact_id`. Prefer the stable lock namespace/helper established by #99 so lock identity is independent of absolute artifact path and cannot be redirected by a caller.

The managed-artifact compile lock must:

- be acquired only after artifact ID/receipt/payload validation succeeds;
- serialize cold compilation of the same artifact ID across processes;
- allow different artifact IDs to compile independently;
- survive process crashes through OS-backed lock release rather than stale sentinel ownership;
- use a finite wait/timeout policy consistent with existing cold-load UX;
- never derive authority or lock identity from an arbitrary public path;
- have an explicit acyclic ordering relative to #99 publication/validation locks and `.cfm` lifecycle operations.

If validation is repeated after waiting for the compile lock, it must use artifact ID/receipt identity and fail closed on payload drift without widening the lock to arbitrary filesystem state.

RED contracts must prove:

1. cold loading a verified artifact may create `.cfm/<version>/...`;
2. payload validation and artifact ID remain unchanged afterwards;
3. deleting/rebuilding `.cfm` leaves payload identity unchanged;
4. public provenance reports converter/artifact identity, not consumer-cache bytes/paths;
5. artifact validation completes before entering potentially long Context-Fabric compile locking;
6. two processes cannot cold-compile the same artifact ID concurrently;
7. different artifact IDs do not block one another;
8. managed-artifact compile-lock identity is artifact-ID based and cannot be selected by arbitrary caller path;
9. process death releases the managed-artifact compile lock;
10. canonical Git-backed `GitStore.compile_lock` behavior remains unchanged;
11. publication/validation/compile lock ordering has no cycle and a waiting compile never holds a publication lock unnecessarily.

No change to ordinary Git-backed Context-Fabric resource semantics is implied.

## Review focus

Independent reviews for #99/#100 must explicitly challenge:

- whether `.cfm` is the **only** consumer-owned exemption;
- whether a materializer can smuggle converter output into the reserved namespace;
- whether any scholarly `.tf`/metadata path can escape manifest hashing;
- whether unknown files are silently accepted after publication;
- whether artifact publication/validation/compile locks can deadlock;
- whether any managed-artifact path is incorrectly passed to canonical `GitStore.compile_lock`;
- whether a caller can choose lock identity through a path instead of validated artifact ID;
- whether `.cfm` state accidentally leaks into public materializer provenance or reusable cache identity.

This amendment is blocking for composition implementation. The design is not complete if it still requires normal Context-Fabric cold compilation to mutate bytes that are claimed to be immutable materializer payload, or if managed artifacts rely on a GitStore-only compile lock that rejects their namespace.
