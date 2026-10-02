# User-supplied TF corpora and modules

Use `install_local_corpus` to import an already-generated native Text-Fabric directory on the **MCP server host**. This works without adding the corpus to Agora's canonical registry. For example:

```text
install_local_corpus(source="/absolute/path/to/coptic-tf", name="My Coptic corpus")
```

Keep the returned `id` and use it with `describe_available_corpus`, `prepare_corpus`, and `load_corpus`. Imported corpora also appear in `list_available_corpora`; imported modules appear with `kind="feature-module"`. Load first, then inspect the node types, features, and text formats with the ordinary Context-Fabric tools before querying.

The input directory must directly contain regular UTF-8 `.tf` files. Corpora require `otype.tf`, `oslots.tf`, and `otext.tf`. Agora copies feature files into its own cache and records a SHA-256 identity derived from the copied feature names, sizes, and hashes; changes to display metadata such as the import name do not change that payload identity, and changes to the original directory do not change the imported copy. Compiled caches (`.tf`/`.cfm`), code, and unrelated files are not imported. Symlink feature files, nonregular files, invalid text encoding, and incomplete inputs are rejected. Import validates the data container and identity, not annotation semantics or scholarly quality. Licenses remain those of the supplied source; import grants no new rights.

For a feature module, prepare the intended parent and supply its exact version and `source_revision`:

```text
install_local_corpus(
  source="/absolute/path/to/extra-features",
  name="My extra annotations",
  parent="<parent-resource-id>",
  parent_version="<version-from-prepare>",
  parent_revision="<source_revision-from-prepare>"
)
load_corpus(resource_id="<parent-resource-id>", modules=["<returned-module-id>"])
```

Modules cannot replace `otype.tf`, `oslots.tf`, or `otext.tf`. Compatibility is declared by the caller: Agora enforces the selected parent identity but cannot establish that the module's node numbering or annotations are correct. Existing ordered-last-wins feature precedence and cold-overlay compilation costs apply. Local modules can extend registered corpora as well as imported corpora.

Import defaults to a 2 GiB byte limit (`max_bytes` can explicitly override it), at most 2,048 feature files, the configured acquisition deadline, and the host's free-space reserve. Client cancellation stops copying and cleans staging. Loading uses the existing compile byte/time guardrails, status, cancellation, and leases. `source_mode="offline"` works for resident imports; `require-fresh` cannot refresh a local corpus. A local corpus revision is a SHA-256 payload-content identity, not an upstream Git commit. Receipt metadata has a separate integrity hash, so descriptive import metadata is integrity-checked without changing the payload revision.

Imports are **evictable cache snapshots**, not permanent installations. They survive server restarts while resident. `prune_corpus_cache` and `remove_cached_corpus` can remove unused imports; loaded corpora remain leased until `unload_corpus`. Removed imports disappear from discovery and must be imported again. Keep your source TF directory and provenance separately. This tool does not convert raw Coptic Scriptorium TT sources, run materializers, fetch arbitrary repositories, upload files from another computer, or provide converter-to-consumer automation.
