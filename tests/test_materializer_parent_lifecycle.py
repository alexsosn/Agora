from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered
from tests.test_materializer_registered_parent_forwarding import PLUGIN


class _TrackingContext:
    def __init__(self, events: list[str], label: str):
        self.events = events
        self.label = label

    def __enter__(self):
        self.events.append(f"{self.label}-enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append(f"{self.label}-exit")
        return False


class RegisteredParentLifetimeTests(unittest.TestCase):
    def _fixture(self, root: Path):
        target = root / "managed-environment"
        runtime = target / "runtime"
        runtime.mkdir(parents=True)
        manifest = runtime / "agora.materializer.json"
        source = root / "source"
        source.mkdir()
        parent_path = root / "cuc"
        parent_path.mkdir()
        output = root / "out"
        parent = host.ParentResourceBinding(
            resource_id="cuc",
            version="0.2.8",
            source_revision="a" * 40,
            path=parent_path,
        )
        return target, manifest, source, output, parent

    def _common_patches(self, target: Path, manifest: Path, events: list[str]):
        return (
            mock.patch.object(registered, "_registered_target", return_value=(PLUGIN, target)),
            mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
            mock.patch.object(
                installer,
                "_lock",
                side_effect=lambda _path: _TrackingContext(events, "runtime"),
            ),
            mock.patch.object(installer, "_validate_binding", return_value={}),
        )

    def test_parent_lease_is_entered_inside_runtime_lock_and_wraps_complete_host_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, manifest, source, output, parent = self._fixture(root)
            events: list[str] = []

            def lease_factory():
                events.append("lease-factory")
                return _TrackingContext(events, "lease")

            def materialize(**kwargs):
                self.assertEqual(
                    events,
                    ["runtime-enter", "lease-factory", "lease-enter"],
                )
                self.assertIs(kwargs["parent"], parent)
                events.append("host")
                return output

            patches = self._common_patches(target, manifest, events)
            with patches[0], patches[1], patches[2], patches[3], mock.patch.object(
                host, "materialize", side_effect=materialize
            ):
                result = registered.materialize_registered(
                    plugin_id="example-converter",
                    materializer_id="example-to-tf",
                    output=output,
                    source=source,
                    sandbox="off",
                    parent=parent,
                    parent_lease_factory=lease_factory,
                )

            self.assertEqual(result, output)
            self.assertEqual(
                events,
                [
                    "runtime-enter",
                    "lease-factory",
                    "lease-enter",
                    "host",
                    "lease-exit",
                    "runtime-exit",
                ],
            )

    def test_parent_lease_is_released_after_host_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, manifest, source, output, parent = self._fixture(root)
            events: list[str] = []

            def lease_factory():
                events.append("lease-factory")
                return _TrackingContext(events, "lease")

            def fail(**_kwargs):
                events.append("host")
                raise RuntimeError("converter failed")

            patches = self._common_patches(target, manifest, events)
            with patches[0], patches[1], patches[2], patches[3], mock.patch.object(
                host, "materialize", side_effect=fail
            ):
                with self.assertRaisesRegex(RuntimeError, "converter failed"):
                    registered.materialize_registered(
                        plugin_id="example-converter",
                        materializer_id="example-to-tf",
                        output=output,
                        source=source,
                        sandbox="off",
                        parent=parent,
                        parent_lease_factory=lease_factory,
                    )

            self.assertEqual(
                events,
                [
                    "runtime-enter",
                    "lease-factory",
                    "lease-enter",
                    "host",
                    "lease-exit",
                    "runtime-exit",
                ],
            )

    def test_parent_without_lifetime_factory_fails_before_host_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, manifest, source, output, parent = self._fixture(root)
            events: list[str] = []
            patches = self._common_patches(target, manifest, events)
            with patches[0], patches[1], patches[2], patches[3], mock.patch.object(
                host, "materialize"
            ) as materialize_mock:
                with self.assertRaisesRegex(ValueError, "lease|lifetime|parent"):
                    registered.materialize_registered(
                        plugin_id="example-converter",
                        materializer_id="example-to-tf",
                        output=output,
                        source=source,
                        sandbox="off",
                        parent=parent,
                    )
            materialize_mock.assert_not_called()

    def test_lifetime_factory_without_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, manifest, source, output, _parent = self._fixture(root)
            events: list[str] = []
            patches = self._common_patches(target, manifest, events)
            lease_factory = mock.Mock(return_value=_TrackingContext(events, "lease"))
            with patches[0], patches[1], patches[2], patches[3], mock.patch.object(
                host, "materialize"
            ) as materialize_mock:
                with self.assertRaisesRegex(ValueError, "parent|lease|lifetime"):
                    registered.materialize_registered(
                        plugin_id="example-converter",
                        materializer_id="example-to-tf",
                        output=output,
                        source=source,
                        sandbox="off",
                        parent_lease_factory=lease_factory,
                    )
            lease_factory.assert_not_called()
            materialize_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
