from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Iterator

from . import gitstore as _gitstore_module
from .gitstore import GitStore as _BaseGitStore
from .gitstore import _core as _core_module
from .operation import current_operation, watch_subprocess


class GitStore(_BaseGitStore):
    """GitStore layer that bounds Git work owned by prepare/load operations.

    Cache maintenance/status keeps its existing explicit budgets. Only Git
    commands executed while an Agora long-operation scope is active consume the
    request's acquisition/materialization deadline and cancellation token.
    """

    def _run_refresh(self, *args: str, cwd: Path | None = None) -> str:
        operation = current_operation()
        if operation is None:
            return super()._run_refresh(*args, cwd=cwd)

        command = ["git"]
        if cwd is not None:
            command += ["-C", str(cwd)]
        command += list(args)
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["GIT_TERMINAL_PROMPT"] = "0"
        process = _gitstore_module.subprocess.Popen(
            command,
            text=True,
            stdout=_gitstore_module.subprocess.PIPE,
            stderr=_gitstore_module.subprocess.PIPE,
            env=env,
        )
        try:
            while True:
                remaining = operation.remaining_acquisition_seconds()
                try:
                    stdout, stderr = process.communicate(timeout=min(0.1, remaining))
                    break
                except _gitstore_module.subprocess.TimeoutExpired:
                    continue
        except BaseException:
            if process.poll() is None:
                try:
                    process.kill()
                except (OSError, ProcessLookupError):
                    pass
            try:
                process.communicate(timeout=1.0)
            except BaseException:
                pass
            raise

        if process.returncode:
            raise _gitstore_module.subprocess.CalledProcessError(
                int(process.returncode),
                command,
                output=stdout,
                stderr=stderr,
            )
        return stdout.strip()

    def _run(self, *args: str, cwd: Path | None = None) -> str:
        # Inside a prepare/load operation every Git subprocess observes the same
        # acquisition deadline. Outside it, preserve the existing implementation
        # except for refresh/fetch diagnostics handled by _run_refresh.
        if current_operation() is not None or (args and args[0] == "fetch"):
            return self._run_refresh(*args, cwd=cwd)
        return super()._run(*args, cwd=cwd)

    def _git_show_lines(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> Iterator[str]:
        with self._repository_lock(repo.name, shared=True):
            relative = self._safe_relative_path(relative_path)
            treeish = self._treeish(repo, revision)
            spec = f"{treeish}:{relative}"
            process = _core_module.subprocess.Popen(
                ["git", "-C", str(repo), "show", spec],
                text=True,
                stdout=_core_module.subprocess.PIPE,
                stderr=_core_module.subprocess.PIPE,
            )
            assert process.stdout is not None
            with watch_subprocess(process):
                try:
                    for line in process.stdout:
                        yield line.rstrip("\r\n")
                finally:
                    process.stdout.close()
                    stderr = process.stderr.read() if process.stderr is not None else ""
                    returncode = process.wait()
                    if process.stderr is not None:
                        process.stderr.close()
                    if returncode:
                        raise _core_module.subprocess.CalledProcessError(
                            returncode,
                            ["git", "show", spec],
                            stderr=stderr,
                        )

    def tf_header_metadata(
        self,
        repo: Path,
        relative_path: str,
        revision: str | None = None,
    ) -> dict[str, Any]:
        with self._repository_lock(repo.name, shared=True):
            relative = self._safe_relative_path(relative_path)
            treeish = self._treeish(repo, revision)
            spec = f"{treeish}:{relative}"
            command = ["git", "-C", str(repo), "show", spec]
            process = _core_module.subprocess.Popen(
                command,
                text=True,
                stdout=_core_module.subprocess.PIPE,
                stderr=_core_module.subprocess.PIPE,
            )
            assert process.stdout is not None
            metadata: dict[str, Any] = {}
            header_complete = False
            with watch_subprocess(process):
                try:
                    for raw_line in process.stdout:
                        line = raw_line.rstrip("\r\n")
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
                        raise _core_module.subprocess.CalledProcessError(
                            returncode,
                            command,
                            stderr=stderr,
                        )
            return metadata

    def _export_snapshot(
        self,
        repo: Path,
        revision: str,
        relative: str,
        destination: Path,
        validate,
    ) -> None:
        self._ensure_free_reserve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_root = Path(tempfile.mkdtemp(prefix="snapshot-", dir=self.tmp_dir))
        export_repo = temp_root / "export"
        extracted = temp_root / "data"
        stderr_path = temp_root / "archive.stderr"
        extracted.mkdir()
        process = None
        try:
            source = self._run("remote", "get-url", "origin", cwd=repo)
            self._run("init", "-q", str(export_repo))
            self._disable_archive_transformations(export_repo)
            self._run("remote", "add", "origin", source, cwd=export_repo)
            self._ensure_free_reserve()
            self._run(
                "fetch",
                "--quiet",
                "--no-tags",
                "--filter=blob:none",
                "--depth",
                "1",
                "origin",
                revision,
                cwd=export_repo,
            )
            self._ensure_free_reserve()
            export_revision = self._run("rev-parse", "FETCH_HEAD", cwd=export_repo)
            command = ["git", "-C", str(export_repo), "archive", "--format=tar", export_revision]
            if relative != ".":
                command += ["--", relative]
            with stderr_path.open("wb") as stderr_file:
                process = _core_module.subprocess.Popen(
                    command,
                    stdout=_core_module.subprocess.PIPE,
                    stderr=stderr_file,
                )
                assert process.stdout is not None
                with watch_subprocess(process):
                    try:
                        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
                            for member in archive:
                                self._validate_archive_member(member)
                                required_bytes = member.size if member.isfile() else 0
                                self._ensure_free_reserve(required_bytes)
                                archive.extract(member, extracted, filter="fully_trusted")
                                self._ensure_free_reserve()
                    except tarfile.ReadError as exc:
                        self._raise_archive_process_error(process, command, stderr_path, exc)
                    self._raise_archive_process_error(process, command, stderr_path)

            exported = extracted if relative == "." else extracted / Path(relative)
            validate(exported)
            try:
                os.replace(exported, destination)
            except FileExistsError:
                validate(destination)
        finally:
            if process is not None:
                if process.stdout is not None and not process.stdout.closed:
                    process.stdout.close()
                if process.poll() is None:
                    process.kill()
                    process.wait()
            shutil.rmtree(temp_root, ignore_errors=True)
