from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.agora_materialize import build_sandbox_command


class ParentSandboxConstructionTests(unittest.TestCase):
    @mock.patch("scripts.agora_materialize.platform.system", return_value="Linux")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/bwrap")
    def test_linux_parent_is_a_distinct_read_only_mount(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            parent = root / "cuc"
            staging_parent = root / "private-stage"
            output = staging_parent / "output"
            plugin = root / "plugin"
            work = root / "work"
            for path in (source, parent, output, plugin, work):
                path.mkdir(parents=True)

            command, backend = build_sandbox_command(
                plugin_root=plugin,
                source=source,
                parent=parent,
                output=output,
                work_dir=work,
                module="example.cli",
                args=["{source}", "{parent}", "{output}"],
            )

        self.assertEqual(backend, "bubblewrap")
        parent_index = command.index(str(parent.resolve()))
        self.assertEqual(command[parent_index - 1], "--ro-bind")
        self.assertEqual(command[parent_index + 1], "/agora-parent")
        self.assertIn("/input", command)
        self.assertIn("/agora-parent", command)
        self.assertIn("/agora-output/output", command)
        self.assertNotIn("--bind " + str(parent.resolve()), " ".join(command))

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Darwin")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/sandbox-exec")
    def test_macos_parent_is_readable_but_never_writable(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            parent = root / "cuc"
            staging_parent = root / "private-stage"
            output = staging_parent / "output"
            plugin = root / "plugin"
            work = root / "work"
            for path in (source, parent, output, plugin, work):
                path.mkdir(parents=True)

            command, backend = build_sandbox_command(
                plugin_root=plugin,
                source=source,
                parent=parent,
                output=output,
                work_dir=work,
                module="example.cli",
                args=["{source}", "{parent}", "{output}"],
            )
            profile = (work / "materializer.sb").read_text(encoding="utf-8")

        self.assertEqual(backend, "sandbox-exec")
        quoted_parent = json.dumps(str(parent.resolve()))
        self.assertIn(f"(allow file-read* (subpath {quoted_parent}))", profile)
        self.assertNotIn(f"(allow file-write* (subpath {quoted_parent}))", profile)
        self.assertIn(str(parent.resolve()), command)
        self.assertEqual(command[0], "/usr/bin/sandbox-exec")


if __name__ == "__main__":
    unittest.main()
