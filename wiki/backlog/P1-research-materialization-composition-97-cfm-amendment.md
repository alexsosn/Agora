# Research amendment: Context-Fabric compile state versus managed-artifact integrity (#97 / #99 / #100)

## Adversarial finding

Independent review of the managed-artifact design found a lifecycle conflict between two otherwise-correct assumptions:

1. #99 intended to publish a key-addressed artifact whose output tree is hash-verified on reuse.
2. Context-Fabric cold loading intentionally writes compiled state below the corpus directory.

Current Agora code makes this explicit in `plugins/context-fabric/src/agora_context_fabric/load_safety.py`:

```text
cfm_version_dir(path, version) = path / ".cfm" / <CFM_VERSION>
cfm_marker(path, version)      = ... / "meta.json"
```

`source_tf_bytes()` separately treats the direct `*.tf` files as the source compiled from that path. Existing lifecycle tests verify `.cfm/<version>/meta.json` creation after successful cold compile.

Therefore a naive "hash the whole artifact directory forever" rule is incompatible with normal Context-Fabric consumption: the first load would create `.cfm/`, and the next artifact validation would incorrectly classify the valid artifact as modified.

## Ownership decision

A managed materialization needs two ownership classes even if they share one filesystem root:

### Converter-owned payload

Everything produced by the approved materializer at publication time, excluding Agora's outer managed-artifact receipt.

Properties:

- immutable after publication;
- explicitly enumerated in the managed-artifact receipt by relative path + file type/hash (or equivalent lossless manifest);
- required materializer paths are a subset and are revalidated;
- forms the scholarly/output integrity boundary;
- contributes to exact published-artifact integrity and, where applicable, reusable request identity/provenance.

### Context-Fabric-owned compile state

The reserved top-level `.cfm/` namespace created after publication by Context-Fabric.

Properties:

- absent from converter-owned payload at publication;
- rejected if a materializer attempts to publish `.cfm` itself;
- not part of the materializer payload hash, cacheability attestation, or request identity;
- disposable/rebuildable consumer cache, versioned by Context-Fabric's `CFM_VERSION` and governed by existing load-safety lifecycle;
- may be created/removed without invalidating the scholarly payload receipt.

No other unmanifested top-level or nested file is silently exempt from payload integrity. `.cfm/` is a narrow consumer-owned reserved namespace, not a general "ignore hidden files" rule.

## Validation consequence

#99 should not use an undifferentiated recursive whole-directory hash as its sole reuse validator after Context-Fabric consumption.

Instead, at publication it must capture a deterministic manifest of converter-owned paths and their content/type identity. On reuse/load validation:

1. every recorded payload path must still exist with the recorded type/hash;
2. required output paths must still satisfy the materializer contract;
3. symlink/path-escape checks remain fail-closed;
4. unexpected files/directories outside explicitly Agora/consumer-owned reserved namespaces fail closed or are handled by a separately specified policy;
5. `.cfm/` may exist and is ignored **only for converter-payload integrity**, not represented as converter output;
6. a converter output containing top-level `.cfm` is rejected before publication so ownership can never be ambiguous.

The receipt may still include a deterministic aggregate digest over the converter-owned manifest for compact identity/checking, but that digest must not change merely because Context-Fabric compiled the artifact later.

## Context-Fabric load consequence

#100 may hand the verified payload directory directly to the existing loader only if the managed-artifact validator and storage permissions permit the loader to own `.cfm/` there.

This does not make `.cfm` trusted scholarly data. It is a consumer cache. Existing Context-Fabric version/marker/cold-compile rules remain responsible for its lifecycle. If later research finds that hostile/tampered `.cfm` state needs stronger validation, that is a Context-Fabric cache-hardening issue rather than a reason to mix compile bytes into materializer provenance.

The public artifact/provenance response must continue to describe converter payload identity, not `.cfm` byte state.

## Concurrency consequence

Artifact publication remains transactional before any `.cfm` exists. Equivalent materialization builders synchronize around the converter-owned payload publication/reuse decision. Context-Fabric compile locking remains a separate consumer concern after an artifact is published.

#99 and #100 must ensure their lock ordering does not create a cycle between artifact-validation/build locks and Context-Fabric compile/cache locks. Artifact payload validation should complete before entering long-running Context-Fabric cold compilation.

## TDD additions

### #99

Add contracts proving:

- a materializer that emits top-level `.cfm` is rejected as using a reserved consumer namespace;
- published receipt enumerates/hash-binds all converter-owned payload paths;
- adding valid `.cfm/<version>/...` after publication does not invalidate converter payload integrity;
- modifying/deleting any recorded payload file still fails closed even when `.cfm` exists;
- an unrelated unexpected unmanifested file is not silently ignored merely because `.cfm` is allowed.

### #100

Add contracts proving:

- loading a verified managed TF artifact may create `.cfm` without changing artifact ID/payload provenance;
- the same artifact still validates after cold compile;
- removal/rebuild of `.cfm` does not alter payload identity;
- canonical Git-backed Context-Fabric cache behavior remains unchanged;
- public provenance does not expose `.cfm` filesystem details as materializer output.

## Conclusion

The immutable unit is the **converter-owned payload manifest**, not every future byte below the load directory. Context-Fabric's known `.cfm/` compile namespace is separately owned, disposable consumer state. This split is required before #99/#100 can safely combine materializer integrity with Context-Fabric loading.
