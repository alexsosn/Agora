from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.agora_materialize import build_sandbox_command


class MaterializerSandboxWorkspaceConstructionTests(unittest.TestCase):
    def _paths(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        source = root / "source"
        plugin = root / "plugin"
        work = root / "work"
        destination_parent = root / "user-destination"
        staging_parent = destination_parent / ".artifact.agora-stage-fixture"
        output = staging_parent / "output"
        for path in (source, plugin, work, output):
            path.mkdir(parents=True)
        return source, plugin, work, destination_parent, output

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Linux")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/bwrap")
    @mock.patch("scripts.agora_materialize._linux_python_path", return_value=("/usr/bin/python3", []))
    def test_linux_binds_private_output_parent_and_passes_child(
        self, _python_path, _which, _system
    ):
        with tempfile.TemporaryDirectory() as tmp:
            source, plugin, work, destination_parent, output = self._paths(Path(tmp))
            command, backend = build_sandbox_command(
                plugin_root=plugin,
                source=source,
                output=output,
                work_dir=work,
                module="example.cli",
                args=["{source}", "{output}"],
            )

        self.assertEqual(backend, "bubblewrap")
        bind_pairs = list(zip(command, command[1:]))
        self.assertIn((str(output.parent.resolve()), "/agora-output"), bind_pairs)
        self.assertNotIn((str(output.resolve()), "/output"), bind_pairs)
        self.assertIn("/agora-output/output", command)
        self.assertNotIn(str(destination_parent.resolve()), command)

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Darwin")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/sandbox-exec")
    def test_macos_grants_write_to_private_output_parent_not_destination_parent(
        self, _which, _system
    ):
        with tempfile.TemporaryDirectory() as tmp:
            source, plugin, work, destination_parent, output = self._paths(Path(tmp))
            command, backend = build_sandbox_command(
                plugin_root=plugin,
                source=source,
                output=output,
                work_dir=work,
                module="example.cli",
                args=["{output}"],
            )
            profile = (work / "materializer.sb").read_text(encoding="utf-8")

        self.assertEqual(backend, "sandbox-exec")
        self.assertIn(
            f'(allow file-write* (subpath "{output.parent.resolve()}"))',
            profile,
        )
        self.assertNotIn(
            f'(allow file-write* (subpath "{destination_parent.resolve()}"))',
            profile,
        )
        self.assertIn("(deny network*)", profile)
        self.assertIn(str(output.resolve()), command)


if __name__ == "__main__":
    unittest.main()
