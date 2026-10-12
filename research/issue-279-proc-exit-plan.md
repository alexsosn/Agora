# #279 — planned test-first race closure

Research commit `aed912776bb3cda00809d9143030e5f1f6861664` precedes this plan.

1. **RED** in `tests/test_context_fabric_client_timeout_181_182.py`: patch `os.kill(pid,0)` to succeed and patch `Path.exists` for the /proc path to raise `ProcessLookupError(3, "No such process")`. `_process_alive(987654)` should return False, not leak that error. Add a normal /proc-missing false case too if independent behavior needs preservation. No subprocess creation and no CAL requests.
2. Commit RED tests independently, run focused test job/CI where possible and require intended failure (not lint failure).
3. **GREEN**: narrow `OSError` catch wrapping both `stat.exists()` and `stat.read_text()`; preserve `PermissionError` at earlier `os.kill` and existing zombie `Z/X` semantics.
4. Full Foundation including process cancellation regression, other required checks; independent exact-head adversarial review before merge.
5. Keep this test-harness stability ticket independent of ongoing CAL integration PR #268. No change to Context-Fabric transport itself or data identity.
