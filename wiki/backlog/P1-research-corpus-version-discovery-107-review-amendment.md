# Research review amendment: persist accepted publication identity (#107)

## Adversarial finding

The first #107 design separated Git publication identity, TF dataset identity, and Agora-supported/default identity, but it did not explicitly persist the **logical publication version/tag that Agora last accepted**.

That omission makes future update comparison ambiguous whenever release version and TF dataset version differ.

BHSA is the concrete counterexample:

- accepted publication might be GitHub release/tag `v1.8.1`;
- the validated runtime TF root is `tf/2021`;
- the immutable source commit is a third value.

Neither `tf/2021` nor the commit SHA tells a later updater that Agora's accepted logical release version was `1.8.1`. If the upstream tag is later deleted or retargeted, rediscovering historical state from current GitHub metadata is unsafe.

Pseudepigrapha-TF provides the same shape (`v0.1.0` → `tf/0.1`), and TLHdig's compound release tag (`tlhdig-0.3_tf-0.2.0`) further shows that project release version, TF version, tag text, and commit may all have distinct semantics.

## Required state distinction

A tracked resource that has an accepted publication needs durable state equivalent to:

```text
accepted publication logical version
accepted signal/tag identity
accepted immutable source commit
accepted TF path/version (corpus only)
```

The canonical runtime fields remain `upstream.ref` and `upstream.tf_path`; tracking state records *why/how that runtime state was accepted* and must cross-validate against it.

For proposal-mode corpus promotion, accepting a candidate therefore must atomically bind:

1. the immutable candidate commit into `upstream.ref`;
2. the validated candidate TF root into `upstream.tf_path`;
3. the matching accepted publication version/tag/source/path tracking state.

A bot must never validate an immutable candidate and then leave runtime loading pointed at a mutable default branch.

## Retag consequence

On a later discovery run, if the same accepted logical publication/tag resolves to a different terminal commit, that is a retag/supply-chain anomaly. It must fail closed and require review; it is not a normal version upgrade.

This comparison must use the persisted accepted logical publication state. Re-deriving the old version from TF directory names is invalid for BHSA/Pseudepigrapha-shaped repositories.

## Migration consequence

#109 must establish initial accepted publication state from primary evidence when opting a resource into proposal/pinned tracking.

If the current Agora path/branch state cannot be mapped confidently to a historical publication/tag, the migration must choose `discovery-only` or disabled/pinned behavior rather than fabricating an accepted version.

## Conclusion

Automatic version discovery needs both **policy** and **accepted state**. The accepted state is not redundant registry bookkeeping: it is necessary for deterministic upgrade ordering, retag detection, idempotency, and proving that the runtime commit/path are exactly the ones Agora reviewed.
