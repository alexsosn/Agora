# Issue #279 — race in helper-process liveness probe

Observed live CI failure: [Foundation run 38235673066](https://github.com/alexsosn/Agora/actions/runs/38235673066), job `114766502919`, `test_cancelled_git_fetch_kills_transport_helpers`. Source at `tests/test_context_fabric_client_timeout_181_182.py`, `_process_alive`, lines ~59–75 before this fix.

`os.kill(pid, 0)` can complete while a cancellation helper still exists, then the same PID can vanish before `Path('/proc/<pid>/stat').exists()`; observed Linux Python 3.13 traceback raised `ProcessLookupError: [Errno 3] No such process` **from Path.exists**, rather than yielding False. The existing code only catches `OSError` around `stat.read_text()`, not around `stat.exists()`. This is a race in a testing helper, not evidence the actual subprocess cancellation failed.

Safe semantics: a disappearance after a previous liveness probe means no live helper remains; return False. Keep `PermissionError` around `os.kill` as an existing signal that the process may still be alive; preserve zombie-state handling. Test by patching `os.kill` to return success then `Path.exists` to raise `ProcessLookupError`, without launching processes or mutating real /proc. One small test-helper error boundary is sufficient. Do not weaken the outer assertion or production `gitstore` code.

Scope is separate from CAL-MCP Agora integration PR #268 and BHSA module revision pin PR #271. No CAL traffic.
