# Generated artifacts

This directory is reserved for derived marketplace artifacts that are intentionally committed.

## Policy

Commit generated files only when a target client requires them at a stable repository path or when committing them materially improves marketplace installation/discovery.

Other derived output should be generated locally or in CI and remain untracked.

Every committed generated artifact must eventually have:

1. a deterministic generator;
2. a documented source of truth;
3. a CI freshness check.

The generators and freshness checks are Phase 2 work. No generated marketplace manifest belongs here yet.
