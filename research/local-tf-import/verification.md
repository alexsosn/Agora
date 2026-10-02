# Verification of local TF import

The focused regression was run before production implementation and failed with `ModuleNotFoundError: agora_context_fabric.local_import`, establishing the missing acquisition path. The final focused suite covers discovery/restart, source independence, exact-parent overlays, integrity checks, bounds, cancellation during copying, concurrent publication, and leases/removal.

The real stdio MCP smoke uses the installed cfabric-mcp runtime and only public MCP calls: install local corpus, prepare offline, install local module, load overlay with cold compilation supervision, describe, search, unload, and remove. It completed successfully with a tiny two-word Coptic fixture. This is consumer integration evidence, not certification of CopticScriptorium-TF conversion or annotation quality.

Registry validation, marketplace freshness, Context-Fabric catalog/index freshness, release-status freshness, and runtime dependency freshness passed. Dependency freshness required a writable temporary uv cache and network access; no dependency inputs or locks were changed.

An author adversarial diff pass checked source/file races, staging cleanup, generated IDs and path derivation, receipt/payload integrity, module parent identity, cache transitions/leases, standalone packaging, public upstream boundaries, and documentation scope. It led to rejecting Windows device filenames and detecting source mutations across the full copy. This pass is not a separate independent reviewer; independent review remains a pre-merge gate under CONTRIBUTING.md.

Full Foundation result is recorded after completion below.

On the original `feature/parent-input-135` working branch (HEAD `4f4662c`), the follow-up Foundation run completed **816 tests in 740.710 seconds**, with 3 failures and 13 errors. All **277 Context-Fabric tests passed** (the argparse rejection case emits its expected usage/error text before reporting `ok`). The full run had already imported the old documentation generator before the generated-page fix; the corrected 7-test plugin-documentation suite and `generate_plugin_docs.py --check` passed in fresh processes.

The unrelated environment failures were separately resolved/rechecked: seeding pip in the dev `.venv` made all 5 execution-identity research tests pass; running outside the enclosing agent sandbox made all 3 real macOS sandbox tests pass. The remaining materializer registry-binding fixture failures reproduce independently in `test_materializer_run_by_id_edge_cases.py`, which imports only unchanged materializer scripts. They are outside this local TF acquisition change. Foundation is therefore not claimed fully green.

Final focused local-import suite: **9 passed**. Real stdio import/module/load/describe/search/unload/remove smoke: passed. No canonical resource additions, dependency changes, generated-manifest edits, converter changes, or upstream semantic patches were made.

## Isolated PR branch

The PR was extracted onto current `main` (`367abffd7f70cf3bdfa255f5a3f03a30149e6a81`) in a separate worktree. No parent-input implementation commits or unrelated local files are included. On this isolated branch, the 9 local import tests, 7 plugin documentation tests, real stdio MCP smoke, registry validation, and generated metadata/catalog/documentation checks passed. The earlier broad-checkout failures are not evidence of failures on this PR base. Full Foundation for the isolated branch and independent review are pending; the PR is opened as a draft.
