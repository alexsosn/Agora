from __future__ import annotations

import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered


PLUGIN = {
    "id": "example-converter",
    "name": "Example converter",
    "description": "Synthetic converter for parent-forwarding tests.",
    "repository": "example/converter",
    "ref": "0123456789abcdef0123456789abcdef01234567",
    "version": "1.2.3",
    "manifest": "agora.materializer.json",
    "package": {
        "type": "python-project",
        "path": ".",
        "install_trust": "explicit-code-execution",
    },
    "materializers": ["example-to-tf"],
    "disciplines": ["digital-philology"],
    "licenses": {"software": "MIT", "data": "synthetic"},
    "verification": {"status": "experimental"},
}


class RegisteredParentForwardingTests(unittest.TestCase):
    def test_registered_runner_forwards_trusted_parent_under_runtime_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "managed-environment"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            manifest = runtime / "agora.materializer.json"
            source = root / "source"
            source.mkdir()
            parent_path = root / "cuc"
            parent_path.mkdir()
            output = root / "out"
            install_root = root / "managed-root"
            registry_path = root / "materializers.yaml"
            parent = host.ParentResourceBinding(
                resource_id="cuc",
                version="0.2.8",
                source_revision="a" * 40,
                path=parent_path,
            )

            with (
                mock.patch.object(registered, "_registered_target", return_value=(PLUGIN, target)),
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(installer, "_lock", return_value=nullcontext()) as lock_mock,
                mock.patch.object(installer, "_validate_binding", return_value={}),
                mock.patch.object(host, "materialize", return_value=output) as materialize_mock,
                mock.patch.object(installer, "fetch_materializer") as fetch_mock,
                mock.patch.object(installer, "install_materializer") as install_mock,
            ):
                result = registered.materialize_registered(
                    plugin_id="example-converter",
                    materializer_id="example-to-tf",
                    output=output,
                    source=source,
                    sandbox="off",
                    install_root=install_root,
                    registry_path=registry_path,
                    parent=parent,
                )

            self.assertEqual(result, output)
            lock_mock.assert_called_once_with(target.parent / f".{target.name}.lock")
            materialize_mock.assert_called_once_with(
                manifest_path=manifest,
                materializer_id="example-to-tf",
                output=output,
                source=source,
                sandbox="off",
                parent=parent,
            )
            fetch_mock.assert_not_called()
            install_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
