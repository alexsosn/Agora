# Issue #251 — typed release-backed corpus resolver (no public registry advertisement yet)

## Real research, 2026-10-11
- Merged PRs #255/#256/#257 prove SHA256-pinned upstream ZIP layout, bounded native TF staging and durable receipt/lease-based snapshots. PR #259 under CI implements reviewed plugin-owned strictly HTTPS pinned release download.
- Agora registry/schema/resources.schema.json and Context-Fabric Catalog intentionally reject unknown acquisition strategies (#252). Current resolver.prepare/corpus_versions/default_corpus_version all assume a Git repository except user-local; release archives cannot masquerade as Git tf_path or commit.
- ContextFabricService controls source_mode via GitStore.source_policy and wraps prepare with its operation acquisition deadline. Asset SHA256 is a valid immutable *release* revision, but not a Git commit.
- Generated installed resource catalogs are selected by registry/v0.1.yaml required_resources. A speculative row would falsely advertise support before clean-cache native TF load/query/unload is proven.

## Research → preserved RED → GREEN → skeptical review
1. RED schema+consumer tests require github-release-archive typed archive fields (release_tag, asset_name, sha256, compressed_bytes, version) only for corpus; reject missing, unknown, malformed values; preserve existing repository, collection and CUC Burns local-module.
2. RED resolver tests use true local native TF ZIPs with fake transport: exact SHA asset pin, no Git clone, canonical stable PreparedCorpus identity, configured versions without network, offline mode cache-only and missing-cache error, wrong version/revision refusal, corrupt-cache refusal, require-fresh pinned validation.
3. GREEN resource metadata, schema/catalog validator, special resolver prepare and version path via reviewed plugin downloader and ReleaseSnapshots. Never route SHA256 to Git. Keep public registry unchanged while this internal integration is reviewed.
4. Real pinned GitHub asset gate must establish fresh-cache native corpus prepare, load/query/unload, offline reload before an independent registration PR updates registry resources, v0.1 scope, generated plugin catalog and scholarly/license provenance.
5. Independent adversarial reviewer challenges redirects, source policy, immutable identity, malformed configuration, rollback and no false discoverability; exact-head Foundation and Context-Fabric load CI gate all changes.

## Not yet complete
Even passing a resolver fixture does not make the Pseudepigrapha corpus public. Issues #251 and #226 remain OPEN for all consumer, source rights, and corpus registration acceptance.