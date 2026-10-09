"""RED2: read-only trusted-parent sandbox binding and placeholder rendering.

The execution and publication path stays contract-only until later #135 gates.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_materialize as host


def _fixture(root: Path):
    plugin = root / "plugin"
    source = root / "source"
    parent = root / "parent"
    work = root / "work"
    output = root / "stage" / "output"
    for directory in (plugin, source, parent, work, output):
        directory.mkdir(parents=True)
    binding = host.ParentBinding(
        path=parent,
        resource_id="cuc",
        version="0.2.8",
        source_revision="a" * 40,
        trusted=True,
    )
    return plugin, source, parent, work, output, binding


class ParentSandboxContractTests(unittest.TestCase):
    def test_parent_placeholders_include_embedded_arguments(self):
        rendered = host._render_args(
            ["--parent={parent}", "--revision={parent_revision}", "{parent_version}", "{source}"],
            source="/input", output="/agora-output/output",
            parent="/parent", parent_revision="a" * 40, parent_version="0.2.8",
        )
        self.assertEqual(rendered, [
            "--parent=/parent", "--revision=" + "a" * 40, "0.2.8", "/input",
        ])

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Linux")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/bwrap")
    def test_linux_parent_is_ro_bind_and_uses_sandbox_path(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            plugin, source, parent, work, output, binding = _fixture(Path(tmp))
            command, backend = host.build_sandbox_command(
                plugin_root=plugin, source=source, output=output, work_dir=work,
                module="example.cli", parent=binding,
                args=["{source}", "--parent={parent}", "{parent_revision}", "{parent_version}"],
            )
            self.assertEqual(backend, "bubblewrap")
            self.assertIn(["--ro-bind", str(parent), "/parent"], [
                command[i:i+3] for i in range(len(command)-2)
            ])
            self.assertIn("--parent=/parent", command)
            self.assertIn("a" * 40, command)
            self.assertIn("0.2.8", command)
            self.assertNotIn(str(parent), command[command.index("example.cli")+1:])

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Darwin")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/sandbox-exec")
    def test_macos_parent_readable_but_not_writable(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            plugin, source, parent, work, output, binding = _fixture(Path(tmp))
            command, backend = host.build_sandbox_command(
                plugin_root=plugin, source=source, output=output, work_dir=work,
                module="example.cli", parent=binding,
                args=["--parent={parent}", "{parent_revision}", "{parent_version}"],
            )
            profile = (work / "materializer.sb").read_text(encoding="utf-8")
            quoted = json.dumps(str(parent.resolve()))
            self.assertEqual(backend, "sandbox-exec")
            self.assertIn(f"(allow file-read* (subpath {quoted}))", profile)
            self.assertNotIn(f"(allow file-write* (subpath {quoted}))", profile)
            self.assertIn("--parent=" + str(parent.resolve()), command)
            self.assertIn("a" * 40, command)
            self.assertIn("0.2.8", command)

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Darwin")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/sandbox-exec")
    def test_reject_parent_beneath_writable_output_mount(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            plugin, source, parent, work, output, binding = _fixture(Path(tmp))
            nested_parent = output.parent / "parent"
            nested_parent.mkdir()
            binding = host.ParentBinding(
                path=nested_parent, resource_id="cuc", version="0.2.8",
                source_revision="a" * 40, trusted=True,
            )
            with self.assertRaisesRegex(ValueError, "overlap|writable"):
                host.build_sandbox_command(
                    plugin_root=plugin, source=source, output=output, work_dir=work,
                    module="example.cli", parent=binding, args=["{parent}"],
                )

    @mock.patch("scripts.agora_materialize.platform.system", return_value="Linux")
    @mock.patch("scripts.agora_materialize.shutil.which", return_value="/usr/bin/bwrap")
    def test_parentless_command_does_not_gain_parent_mount(self, _which, _system):
        with tempfile.TemporaryDirectory() as tmp:
            plugin, source, parent, work, output, binding = _fixture(Path(tmp))
            common = dict(plugin_root=plugin, source=source, output=output,
                          work_dir=work, module="example.cli",
                          args=["{source}", "{output}", "{source_revision}"])
            implicit = host.build_sandbox_command(**common)
            explicit = host.build_sandbox_command(**common, parent=None)
            self.assertEqual(implicit, explicit)
            self.assertNotIn("/parent", implicit[0])


if __name__ == "__main__":
    unittest.main()
