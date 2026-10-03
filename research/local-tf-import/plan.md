# User-supplied Text-Fabric import

## Evidence and scope

The live catalog cannot discover CopticScriptorium-TF, and the canonical materializer installer rejects its ID. Already-generated TF data needs resource selection rather than converter registration. cfabric-mcp's public corpus manager accepts a TF directory; Agora already supplies snapshot leases, ordered module overlays, cold compilation supervision, cancellation, and cache removal. Release tracker #148 is closed completed (checked 2026-10-02).

Implement import of direct local TF feature directories, without converters, archives, Python execution, canonical registry edits, or scholarly validation. Store isolated copies under the existing snapshot namespace and discover their versioned receipts as a separate local catalog view. IDs are generated, revisions are content hashes, and modules require an explicitly declared parent version and immutable revision. Existing prepare/load paths consume these snapshots and preserve upstream semantics.

## Integrity and lifecycle

Copy only regular UTF-8 `.tf` files, rejecting symlinks, special files, incomplete corpora, and module warp/config replacements. Ignore compiled caches and unrelated files. Bound bytes, file count, wall time, and free space during copying; observe cancellation and remove staging on failure. Publish atomically under the shared cache transition. Verify receipt identity and all feature hashes before preparation. Prune/removal use existing leases; removed imports disappear from discovery and must be imported again. Never write into user source directories.

## Gates

Preserve failing import/prepare/module/integrity regressions before implementation. Run focused tests, real TF load/search smoke through the MCP handlers, and Foundation. Review the final diff independently of implementation assumptions for integrity, packaging, lifecycle, and documented scope.
