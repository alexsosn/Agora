from pathlib import Path

CORE = Path("plugins/context-fabric/src/agora_context_fabric/gitstore/_core.py")
STATUS = Path("plugins/context-fabric/src/agora_context_fabric/gitstore/__init__.py")


def replace_section(text: str, *, label: str, start: str, end: str, replacement: str) -> str:
    if text.count(start) != 1:
        raise SystemExit(f"{label}: start anchor count {text.count(start)} != 1")
    start_index = text.index(start)
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise SystemExit(f"{label}: end anchor not found")
    if text.find(end, end_index + len(end)) >= 0:
        raise SystemExit(f"{label}: end anchor is ambiguous")
    return text[:start_index] + replacement + text[end_index:]


core = CORE.read_text(encoding="utf-8")

core = replace_section(
    core,
    label="repository lock",
    start="    @contextmanager\n    def _repository_lock(",
    end="\n    @contextmanager\n    def cache_transition(",
    replacement='''    @contextmanager
    def _repository_lock(
        self,
        key: str,
        timeout: float = 30.0,
        *,
        shared: bool = False,
    ) -> Iterator[None]:
        """Coordinate persistent repository use with a crash-safe lock."""
        lock_path = self.locks_dir / f"repository-{self.safe_cache_key(key)}.lock"
        lock = self._acquire_file_lock(
            lock_path,
            shared=shared,
            timeout=timeout,
            description="Git cache lock",
        )
        try:
            yield
        finally:
            lock.release()
''',
)

core = replace_section(
    core,
    label="git show generator",
    start="    def _git_show_lines(",
    end="\n    def tf_header_metadata(",
    replacement='''    def _git_show_lines(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Iterator[str]:
        with self._repository_lock(repo.name, shared=True):
            relative = self._safe_relative_path(relative_path)
            treeish = self._treeish(repo, revision)
            spec = f"{treeish}:{relative}"
            process = subprocess.Popen(
                ["git", "-C", str(repo), "show", spec],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdout is not None
            try:
                for line in process.stdout:
                    yield line.rstrip("\\r\\n")
            finally:
                process.stdout.close()
                stderr = process.stderr.read() if process.stderr is not None else ""
                returncode = process.wait()
                if process.stderr is not None:
                    process.stderr.close()
                if returncode:
                    raise subprocess.CalledProcessError(
                        returncode,
                        ["git", "show", spec],
                        stderr=stderr,
                    )
''',
)

core = replace_section(
    core,
    label="header reader",
    start="    def tf_header_metadata(",
    end="\n    def tf_feature_summary(",
    replacement='''    def tf_header_metadata(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> dict[str, Any]:
        """Read Text-Fabric metadata header fields without consuming feature rows."""
        with self._repository_lock(repo.name, shared=True):
            relative = self._safe_relative_path(relative_path)
            treeish = self._treeish(repo, revision)
            spec = f"{treeish}:{relative}"
            command = ["git", "-C", str(repo), "show", spec]
            process = subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdout is not None
            metadata: dict[str, Any] = {}
            header_complete = False
            try:
                for raw_line in process.stdout:
                    line = raw_line.rstrip("\\r\\n")
                    if not line or not line.startswith("@"):
                        header_complete = True
                        break
                    if "=" in line:
                        key, value = line[1:].split("=", 1)
                        if key:
                            metadata[key] = value
            finally:
                process.stdout.close()
                stderr = process.stderr.read() if process.stderr is not None else ""
                returncode = process.wait()
                if process.stderr is not None:
                    process.stderr.close()
                if returncode and not header_complete:
                    raise subprocess.CalledProcessError(
                        returncode,
                        command,
                        stderr=stderr,
                    )
            return metadata
''',
)

CORE.write_text(core, encoding="utf-8")

status = STATUS.read_text(encoding="utf-8")
old = "with self._repository_lock(repo.name, timeout=remaining):"
new = "with self._repository_lock(repo.name, timeout=remaining, shared=True):"
if status.count(old) != 1:
    raise SystemExit(f"status lock anchor count {status.count(old)} != 1")
STATUS.write_text(status.replace(old, new), encoding="utf-8")
