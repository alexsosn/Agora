# Registry

This directory contains Agora's canonical machine-readable marketplace metadata and schemas.

Phase 1 defines the registry schema around the fixed v0.1 implementation set:

- four plugin families: `context-fabric`, `perseus`, `sefaria`, and `sedra`;
- 35 corpus resources from the current Context-Fabric corpus catalog;
- `alexsosn/TLHdig-TF` as an additional Context-Fabric resource;
- 36 Context-Fabric corpus resources in total.

The exact baseline is documented in [`wiki/v0.1-scope.md`](../wiki/v0.1-scope.md).

The canonical model must distinguish plugin/integration metadata from resource/data metadata, including separate verification status and licensing/provenance fields. Client-specific marketplace manifests must be derived from this canonical data rather than maintained here as parallel sources of truth.
