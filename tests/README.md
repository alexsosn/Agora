# Tests

Agora tests both repository metadata and generated client artifacts, with real scholarly integration tests added in later phases.

Current layers include:

- canonical registry/schema validation;
- duplicate/reference/controlled-vocabulary negative tests;
- deterministic marketplace generation tests;
- committed-artifact freshness checks;
- Claude and Codex marketplace shape/order checks;
- fixed v0.1 scope checks.

Later phases add plugin installation/startup, MCP initialization/tool discovery, corpus acquisition/loading, and representative integration smoke tests.

Run all current tests with:

```bash
python -m unittest discover -s tests -v
```
