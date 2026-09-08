# Research Burns Workbooks materializer registration (#87)

## Question

What is the smallest truthful Agora integration for the merged Burns Workbooks Text-Fabric converter in `alexsosn/ugarit-context-parsing`, while preserving Agora's installation, sandbox, licensing, and consumer-composition boundaries?

## Baseline inspected

Agora main: `807db7dcdf09f1aaaae04a7a6a19f193d22af4b9`.

Upstream Burns converter: merged commit `e1218b88d9d849c58ee25541339f32b0d8f5a7d3`, project/manifest version `0.2.0`.

Upstream materializer IDs:

- `burns-workbooks-csv-text-fabric`
- `burns-workbooks-pdf-text-fabric`

## Findings

### Existing Agora materializer contract is sufficient

Agora already owns the required host responsibilities:

- an immutable third-party materializer registry;
- passive source fetch and manifest validation without packaging execution;
- explicit approval for Python packaging/build execution;
- managed runtime/distribution receipts and integrity hashes;
- user-local source acquisition;
- source symlink policy enforcement;
- Python-module execution without a shell;
- required sandbox backends and network denial;
- staging/output validation, protected provenance, and atomic publication.

No new materializer schema or runtime primitive is needed for Burns.

### The upstream converter has the right trust boundary

The merged upstream manifest accepts only user-local directories, denies network access during conversion, rejects source symlinks, and exposes distinct CSV and PDF materializers. The PDF path uses the repository's existing Workbook parser rather than downloading data or introducing a second scholarly interpretation.

The converter emits ordinary Text-Fabric 13.x artifacts plus `conversion-report.json`. Its CUC interoperability is deliberately narrow: exact KTU identifiers receive a `cuc_tablet="KTU …"` join feature and records receive `language=Ugaritic`; it does not fabricate CUC sign/word/line/column structure absent from Burns.

### Data must remain local-only

Burns' source is CC BY-NC-ND 2.5. Agora may register and execute the converter, but should not redistribute the source PDFs, generated CSVs, generated TF artifact, or CI artifacts containing Burns-derived content. End-to-end smoke fixtures must therefore be synthetic.

The upstream repository currently does not declare a software license. Agora must record that truthfully (`NOASSERTION`) rather than infer MIT from other projects.

### Automatic materializer release discovery now exists

Since the earlier #87 research, Agora gained `release_tracking` metadata and scheduled stable GitHub-release discovery. `ugarit-context-parsing` has no verified GitHub release/tag for version `0.2.0` at this research point, so the registry entry should use:

```yaml
release_tracking:
  mode: disabled
```

The runtime pin remains the immutable merged commit. Release tracking can be enabled later, after a stable upstream GitHub release exists and its manifest version matches.

### Automatic resource → materializer → consumer composition is still separate

`wiki/backlog/P1-design-local-materialization-composition.md` remains the design boundary for automatic binding of a resource to an approved materializer, artifact cache lifecycle, and consumer hand-off such as Context-Fabric. #87 must not bypass that design by embedding executable materializer fields in resource/catalog metadata or pretending `load_corpus` automatically materializes Burns.

What #87 can truthfully provide now is discovery, fetch/install, and direct Agora materialization. The produced TF directory is then a normal local Text-Fabric artifact suitable for Context-Fabric/cfabric-mcp once supplied through its supported local source path.

## Verification strategy

1. Pin the registry to `e1218b88d9d849c58ee25541339f32b0d8f5a7d3` and version `0.2.0`.
2. Add a registry test first; it must fail before the registry entry exists.
3. Register both exact upstream materializer IDs, `explicit-code-execution`, truthful license metadata, and disabled release tracking.
4. Extend the registered-materializer install smoke to passively fetch the immutable source, explicitly install it, verify receipt/distribution identity, and import both the package CLI and packaged existing PDF parser.
5. If the current host/runtime API permits it without new composition architecture, generate a synthetic Workbook CSV tree, run the registered CSV materializer through Agora's real sandbox host, and verify the resulting TF artifact/report without uploading the artifact.
6. Run canonical registry/foundation/materializer workflows, then independently review the frozen head.

## Out of scope

- redistributing Burns-derived source or output;
- inventing CUC diplomatic structure;
- Appendix → TF (different schema);
- automatic resource → materializer → Context-Fabric composition;
- enabling release discovery before an upstream stable release exists;
- assigning an unverified software license.
