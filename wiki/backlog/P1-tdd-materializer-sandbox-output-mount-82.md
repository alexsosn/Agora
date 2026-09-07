# TDD log: materializer sandbox output workspace (#82)

## RED target

The pre-implementation tests intentionally require behavior the current sandbox does not provide.

Deterministic construction expectations:

- Linux must bind the converter output **parent** to `/agora-output` and render `{output}` as `/agora-output/output`.
- macOS must grant write permission to the private output parent rather than only the output child.
- neither backend may grant the user's destination parent as its writable sandbox surface.

Real-sandbox expectation:

- a fixture creates `output.parent/.fixture-stage`, writes required files there, and atomically `os.replace()`s them into output.
- current Linux topology is expected to fail with `EXDEV` because `/output` is a separate bind mount.
- current macOS topology is expected to fail because the sibling staging directory lies outside the current write allow-list.

The test commits precede any production-code change. The next gate is CI evidence that the new regression fails on the old implementation, followed by the minimal implementation described in the plan.