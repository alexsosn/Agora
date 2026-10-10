"""#135 RED3b: carry a resolved parent through registered execution and provenance.

The #135 RED3a resolver returns a verified identity, but does not run materializers.
These tests stay red until host and registered runner accept that binding explicitly.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from scripts import agora_materialize as host
from scripts import agora_materialize_registered as registered
from scripts import agora_install_materializer as installer
from tests.test_materialization import _manifest


REV = "a" * 40


def _fixture(root: Path, *, write_parent_warp=False):
    plugin, source, parent = root / "plugin", root / "source", root / "parent"
    output = root / "published" / "artifact"
    for directory in (plugin, source, parent, output.parent):
        directory.mkdir(parents=True)
    (source / "data.xml").write_text("<data/>", encoding="utf-8")
    for name in ("otype.tf", "oslots.tf", "otext.tf"):
        (parent / name).write_text("parent "+name, encoding="utf-8")
    (plugin / "parent_converter.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "source, parent, output = map(Path, sys.argv[1:4])\n"
        "revision, version = sys.argv[4:6]\n"
        "assert (source / 'data.xml').read_text() == '<data/>'\n"
        "assert (parent / 'otype.tf').read_text() == 'parent otype.tf'\n"
        "assert revision == 'a' * 40 and version == '0.2.8'\n"
        "(output / 'burns.tf').write_text('module')\n"
        + ("(output / 'otype.tf').write_text('smuggled')\n" if write_parent_warp else ""),
        encoding="utf-8",
    )
    manifest = _manifest()
    spec = manifest["materializers"][0]
    spec["parent_input"] = {
        "resource": "cuc",
        "parent_versions": ["0.2.8"],
        "required_paths": ["otype.tf", "oslots.tf", "otext.tf"],
    }
    spec["execution"]["module"] = "parent_converter"
    spec["execution"]["args"] = [
        "{source}", "{parent}", "{output}", "{parent_revision}", "{parent_version}"
    ]
    spec["output"] = {
        "format": "text-fabric", "required_paths": ["burns.tf"],
        "composition": {
            "kind": "feature-module", "parent": "cuc",
            "compatibility": {"parent_versions": ["0.2.8"]},
        },
    }
    manifest_path = plugin / "agora.materializer.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    binding = host.ParentBinding(
        path=parent, resource_id="cuc", version="0.2.8",
        source_revision=REV, trusted=True,
    )
    return source, parent, output, manifest_path, binding


def _unsandboxed_probe(**kwargs):
    """Test-only command implementation to inspect propagation without OS bwrap."""
    parent = kwargs["parent"]
    assert parent is not None
    args = host._render_args(
        kwargs["args"], source=str(kwargs["source"]),
        output=str(kwargs["output"]),
        source_revision=kwargs["source_revision"],
        parent=str(parent.path), parent_revision=parent.source_revision,
        parent_version=parent.version,
    )
    return [sys.executable, "-m", kwargs["module"], *args], "bubblewrap-test-double"


class ParentBoundHostRed3bTests(unittest.TestCase):
    def test_missing_parent_binding_fails_before_source_or_output_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _parent, output, manifest, _binding = _fixture(Path(tmp))
            with mock.patch.object(host, "acquire_source") as acquire:
                with self.assertRaisesRegex(host.ManifestError, "parent"):
                    host.materialize(
                        manifest_path=manifest, materializer_id="example-to-tf",
                        source=source, output=output, sandbox="required",
                    )
            acquire.assert_not_called()
            self.assertFalse(output.exists())

    def test_mismatched_resource_and_version_rejected_pre_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, parent, output, manifest, binding = _fixture(Path(tmp))
            for resource_id, version in (("bhsa", "0.2.8"), ("cuc", "1935")):
                forged = host.ParentBinding(
                    path=parent, resource_id=resource_id, version=version,
                    source_revision=REV, trusted=True,
                )
                with self.subTest(resource_id=resource_id, version=version):
                    with mock.patch.object(host, "acquire_source") as acquire:
                        with self.assertRaisesRegex(ValueError, "parent|version"):
                            host.materialize(
                                manifest_path=manifest, materializer_id="example-to-tf",
                                source=source, output=output, sandbox="required", parent=forged,
                            )
                    acquire.assert_not_called()
                    self.assertFalse(output.exists())

    def test_parent_bound_run_writes_resolved_identity_to_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, parent, output, manifest, binding = _fixture(Path(tmp))
            with (
                mock.patch.object(host, "_sandbox_backend_preflight", return_value=("bubblewrap", "bwrap")),
                mock.patch.object(host, "build_sandbox_command", side_effect=_unsandboxed_probe) as sandbox,
            ):
                result = host.materialize(
                    manifest_path=manifest, materializer_id="example-to-tf",
                    source=source, output=output, sandbox="required", parent=binding,
                )
            self.assertEqual(result, output.resolve())
            self.assertEqual((output / "burns.tf").read_text(), "module")
            provenance = json.loads((output / "agora-materialization.json").read_text())
            self.assertEqual(
                {key: provenance["parent"][key] for key in
                 ("resource_id", "version", "source_revision", "trusted")},
                dict(resource_id="cuc", version="0.2.8", source_revision=REV, trusted=True),
            )
            self.assertEqual(provenance["output"]["composition"]["parent"], "cuc")
            self.assertEqual((parent / "otype.tf").read_text(), "parent otype.tf")
            self.assertEqual(sandbox.call_args.kwargs["parent"], binding)
            self.assertFalse((output / "otype.tf").exists())

    def test_parent_bound_run_rejects_unsandboxed_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _parent, output, manifest, binding = _fixture(Path(tmp))
            with mock.patch.object(host, "acquire_source") as acquire:
                with self.assertRaisesRegex(ValueError, "sandbox|parent"):
                    host.materialize(
                        manifest_path=manifest, materializer_id="example-to-tf",
                        source=source, output=output, sandbox="off", parent=binding,
                    )
            acquire.assert_not_called()

    def test_rejects_warp_smuggling_before_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _parent, output, manifest, binding = _fixture(
                Path(tmp), write_parent_warp=True,
            )
            with (
                mock.patch.object(host, "_sandbox_backend_preflight", return_value=("bubblewrap", "bwrap")),
                mock.patch.object(host, "build_sandbox_command", side_effect=_unsandboxed_probe),
            ):
                with self.assertRaisesRegex(ValueError, "otype.tf|warp|feature-module"):
                    host.materialize(
                        manifest_path=manifest, materializer_id="example-to-tf",
                        source=source, output=output, sandbox="required", parent=binding,
                    )
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob(".artifact.agora-stage-*")), [])

    def test_single_source_run_does_not_gain_parent_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin, source, out = root / "plugin", root / "source", root / "out"
            plugin.mkdir()
            source.mkdir()
            (source / "a.xml").write_text("a")
            (plugin / "solo.py").write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "(Path(sys.argv[1]) / 'otype.tf').write_text('x')\n"
                "(Path(sys.argv[1]) / 'oslots.tf').write_text('y')\n"
            )
            doc = _manifest()
            doc["materializers"][0]["execution"]["module"] = "solo"
            doc["materializers"][0]["execution"]["args"] = ["{output}"]
            manifest = plugin / "agora.materializer.json"
            manifest.write_text(json.dumps(doc))
            host.materialize(
                manifest_path=manifest, materializer_id="example-to-tf",
                source=source, output=out, sandbox="off",
            )
            receipt = json.loads((out / "agora-materialization.json").read_text())
            self.assertNotIn("parent", receipt)


class RegisteredParentForwardingRed3bTests(unittest.TestCase):
    def test_registered_run_forwards_binding_inside_existing_runtime_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _source, _parent, _output, _manifest, binding = _fixture(root)
            target = root / "managed" / "plugin"
            runtime = target / "runtime"
            runtime.mkdir(parents=True)
            manifest = runtime / "agora.materializer.json"
            plugin = {
                "id": "example", "materializers": ["example-to-tf"],
            }
            with (
                mock.patch.object(registered, "_registered_target", return_value=(plugin, target)),
                mock.patch.object(registered, "resolve_installed_manifest", return_value=manifest),
                mock.patch.object(installer, "_lock", return_value=nullcontext()) as lock,
                mock.patch.object(installer, "_validate_binding"),
                mock.patch.object(host, "materialize", return_value=root / "published") as materialize,
            ):
                registered.materialize_registered(
                    plugin_id="example", materializer_id="example-to-tf",
                    source=root / "source", output=root / "published",
                    parent=binding,
                )
            lock.assert_called_once()
            self.assertEqual(materialize.call_args.kwargs["parent"], binding)


if __name__ == "__main__":
    unittest.main()
