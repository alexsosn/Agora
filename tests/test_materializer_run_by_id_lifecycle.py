from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered


PLUGIN = {
    "id": "example-converter",
    "name": "Example converter",
    "description": "Synthetic converter for lifecycle tests.",
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
REGISTRY = {"schema_version": 1, "plugins": [PLUGIN]}


class RegisteredMaterializerLifecycleTests(unittest.TestCase):
    def test_final_integrity_check_and_execution_share_installer_runtime_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = installer.installation_path(PLUGIN, root)
            manifest = target / "runtime" / PLUGIN["manifest"]
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
            state = {"locked": False}
            checked_while_locked: list[bool] = []
            executed_while_locked: list[bool] = []
            lock_paths: list[Path] = []

            @contextmanager
            def fake_lock(path: Path, **_kwargs):
                lock_paths.append(Path(path))
                self.assertFalse(state["locked"])
                state["locked"] = True
                try:
                    yield
                finally:
                    state["locked"] = False

            def fake_current(plugin, actual_target):
                self.assertEqual(plugin, PLUGIN)
                self.assertEqual(actual_target, target)
                checked_while_locked.append(state["locked"])
                return True

            def fake_materialize(**_kwargs):
                executed_while_locked.append(state["locked"])
                return root / "output"

            with (
                mock.patch.object(installer, "load_registry", return_value=REGISTRY),
                mock.patch.object(installer, "_environment_current", side_effect=fake_current),
                mock.patch.object(installer, "_lock", side_effect=fake_lock),
                mock.patch.object(host, "materialize", side_effect=fake_materialize),
            ):
                result = registered.materialize_registered(
                    plugin_id="example-converter",
                    materializer_id="example-to-tf",
                    output=root / "output",
                    source=root / "source",
                    sandbox="off",
                    install_root=root,
                )

        self.assertEqual(result, root / "output")
        self.assertTrue(checked_while_locked, "registered execution must re-check integrity")
        self.assertTrue(all(checked_while_locked), "integrity check escaped installer runtime lock")
        self.assertEqual(executed_while_locked, [True], "materializer execution escaped installer runtime lock")
        expected_lock = target.parent / f".{target.name}.lock"
        self.assertEqual(lock_paths, [expected_lock])


if __name__ == "__main__":
    unittest.main()
