# Design amendment: empirically bounded execution-identity canonicalization (#111)

**Status: normative amendment.** This amendment narrows `P1-design-materializer-execution-identity-111.md` using the real Linux/macOS/Windows two-install evidence recorded in `P1-research-materializer-execution-identity-111-empirical-amendment.md`.

## Selected architecture

Use a receipt-v3 split between:

1. **raw integrity identity** — the existing full managed-runtime tree hash plus raw pip-report hash, preserved for tamper detection;
2. **canonical execution identity** — a second runtime-tree digest that transforms only the empirically classified volatile installer provenance graph.

Do not make raw installation artifacts reproducible merely to simplify hashing. Do not weaken `_environment_current()` by excluding raw files that it currently protects.

## Canonical transform set

The initial v3 canonicalizer may recognize only these transformations.

### 1. Agora local-project `direct_url.json`

For an installed distribution whose `direct_url.json` is the PEP 610 record of the Agora staging project used for this managed install:

- parse JSON structurally;
- require the expected local-directory shape;
- require the URL to be a `file://` URI whose path resolves to the current Agora-created `agora-materializer-build-*/source` staging pattern known to this installation operation;
- replace only that ephemeral staging URI with one fixed domain-separated canonical token before hashing;
- preserve every other JSON key/value semantically and fail closed on an unexpected origin shape rather than treating it as equivalent.

Do not normalize arbitrary `file://` origins belonging to dependencies or user-installed packages.

### 2. Derived `RECORD` row

When a distribution's `direct_url.json` is canonically transformed:

- parse that distribution's `RECORD`;
- locate the exact row for the transformed `direct_url.json`;
- recompute the canonical SHA-256 digest and byte length from the canonicalized JSON bytes;
- hash a deterministic canonical `RECORD` representation containing that recomputed row;
- preserve all unrelated rows, paths, hashes, sizes and ordering semantics;
- fail closed on duplicate/missing/ambiguous expected rows or malformed CSV.

No entire-`RECORD` ignore is permitted.

### 3. Windows distlib launcher timestamp

For a generated Windows console/gui launcher that is structurally recognized as the pip/distlib launcher format used by the managed install:

- preserve the executable launcher stub bytes;
- preserve the shebang bytes;
- parse the appended ZIP archive;
- require the expected embedded entry-point archive structure before applying any transform;
- canonicalize only ZIP timestamp fields proven volatile by the cross-platform research;
- preserve embedded `__main__.py` bytes and every other ZIP field/content that can affect execution;
- reserialize/hash deterministically or construct an equivalent canonical manifest whose byte domain includes all non-timestamp launcher content;
- fail closed if the launcher cannot be parsed as the recognized structure.

Do not ignore `bin/*.exe`, do not normalize arbitrary PE timestamps, and do not erase interpreter/shebang/path differences that are not the classified ZIP member timestamp.

### 4. Pip report

`pip-report.json` remains raw receipt provenance. Its SHA-256 remains part of integrity verification exactly as today. Its volatile `download_info.url` does not need a canonical counterpart because the pip report is not an execution-tree file.

If later design chooses to include pip-report semantics in canonical execution identity, that requires a separate RED and review; it is not part of this change.

## Receipt v3 contract

Conceptual shape:

```json
{
  "schema_version": 3,
  "environment": {
    "tree_sha256": "<raw full runtime tree>",
    "execution_tree_sha256": "<canonical runtime tree>",
    "pip_report_sha256": "<raw report>",
    "...": "existing descriptor/distribution fields"
  },
  "execution_identity_sha256": "<source tree + canonical execution tree + runtime identity>"
}
```

The existing raw tree and raw pip-report hashes remain the authority for installation integrity. The cacheability identity uses `execution_tree_sha256`.

## v2 compatibility

Schema-v2 receipts must never be silently interpreted under the v3 formula.

Preferred contract:

- ordinary direct execution may continue to verify a valid v2 receipt using the historical v2 formula;
- cacheability authorization treats v2 as non-reproducible/legacy and denies reusable authorization;
- explicit `--repair`/reinstall produces a v3 receipt and new execution identity;
- no background receipt rewrite occurs;
- a 64-hex v2 identity matching a registry value by coincidence does not authorize v3 cache reuse.

If implementation evidence shows dual v2/v3 verification materially compromises integrity clarity, fail closed and require repair for v2 instead. That deviation must be documented and independently reviewed before merge.

## TDD sequence after this research/design PR merges

### RED 1 — canonical clean-install identity

Commit tests first requiring two real clean installs of the synthetic local materializer to produce:

- unequal raw environment hashes where raw provenance differs;
- equal `environment.execution_tree_sha256`;
- equal v3 `execution_identity_sha256`;
- valid raw `_environment_current()` verification for both installs;
- no random `agora-materializer-build-*` spelling in canonical identity inputs.

Run on Linux, macOS and Windows.

### GREEN 1

Implement receipt v3 plus only the three runtime transforms above: local-project origin, its derived `RECORD` row, and recognized Windows launcher ZIP timestamp metadata.

### RED 2 — negative controls

Freeze failures/digest changes for:

- installed Python module byte changes;
- distribution version/metadata changes;
- entry-point changes;
- non-ephemeral `direct_url.json` changes;
- unrelated or malformed `RECORD` rows;
- Windows launcher stub, shebang, embedded `__main__.py`, or non-timestamp ZIP metadata changes;
- unexpected absolute build/install paths in any unclassified runtime file;
- malformed recognized provenance shapes;
- v2 receipt presented to reusable authorization.

Also prove raw tampering continues to make environment verification fail even if the canonical transform would otherwise remove a volatile field from execution identity.

### GREEN 2

Implement only the strict validation/fail-closed behavior needed by those controls.

### RED 3 — #103 integration

Before any reusable registry disposition:

- trusted cacheability authorization accepts a valid reviewed v3 execution identity;
- it denies v2 legacy receipts;
- a repair/reinstall v2→v3 migration changes the identity contract explicitly;
- Burns/Pseudepigrapha evidence records the exact v3 identity actually replayed.

### GREEN 3

Wire #103 authorization to the v3 contract and add only evidence-backed reusable dispositions. No artifact cache/storage implementation belongs here.

## Cross-platform gate

The implementation PR is not mergeable until the real-pip two-install desired-state regression is green on Linux, macOS and Windows. Platform identities may differ from each other; equivalent installs on the same platform/runtime must match.

The canonicalizer must be tested against the observed Windows launcher structure rather than assuming POSIX behavior.

## Review blockers

Final review must reject the implementation if it:

- weakens raw tree/pip-report integrity;
- ignores whole `.dist-info`, `RECORD`, script or launcher areas;
- normalizes arbitrary local origins rather than the exact Agora staging origin;
- changes an unrelated `RECORD` row while canonicalizing one origin;
- erases any Windows launcher byte outside recognized ZIP timestamp metadata without evidence;
- accepts malformed metadata by fallback normalization;
- lets a v2 receipt authorize v3 reusable cache policy;
- adds converter/domain behavior or cache storage.

## Definition of done

#111 is ready for implementation when this amendment and its empirical research are merged after exact-head CI and independent review. The implementation ticket is complete only when equivalent same-platform clean installs share the v3 execution identity while raw integrity remains fully tamper-sensitive and every allowed canonical transform is explicitly evidence-backed and negatively tested.
