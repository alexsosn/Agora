# Design amendment: reserve Context-Fabric `.cfm` outside converter-payload integrity (#97 / #99 / #100)

## Required correction

The parent plan's whole-artifact integrity wording must be interpreted as integrity of the **converter-owned published payload**, not every future byte below the directory Context-Fabric loads.

Current Context-Fabric intentionally writes `.cfm/<CFM_VERSION>/...` into the corpus path during cold compilation. Treating that consumer cache as materializer output would make ordinary loading invalidate the artifact.

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

### RED additions

Before GREEN implementation, add tests for reserved `.cfm` publication rejection, payload-manifest completeness, post-publication `.cfm` tolerance, payload tamper failure with `.cfm` present, and rejection of unrelated unmanifested additions.

## #100 changes

The managed-artifact loader must treat `.cfm` as Context-Fabric-owned disposable compile state while preserving the converter payload receipt unchanged.

RED contracts must prove:

1. cold loading a verified artifact may create `.cfm/<version>/...`;
2. payload validation and artifact ID remain unchanged afterwards;
3. deleting/rebuilding `.cfm` leaves payload identity unchanged;
4. public provenance reports converter/artifact identity, not consumer-cache bytes/paths;
5. artifact validation completes before entering potentially long Context-Fabric compile locking, avoiding lock-order coupling between materialization and CFM lifecycle.

No change to ordinary Git-backed Context-Fabric resource semantics is implied.

## Review focus

Independent reviews for #99/#100 must explicitly challenge:

- whether `.cfm` is the **only** consumer-owned exemption;
- whether a materializer can smuggle converter output into the reserved namespace;
- whether any scholarly `.tf`/metadata path can escape manifest hashing;
- whether unknown files are silently accepted after publication;
- whether artifact and Context-Fabric compile locks can deadlock;
- whether `.cfm` state accidentally leaks into public materializer provenance or reusable cache identity.

This amendment is blocking for composition implementation. The design is not complete if it still requires normal Context-Fabric cold compilation to mutate bytes that are claimed to be immutable materializer payload.
