from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import agora_install_materializer as installer


REF = "0123456789abcdef0123456789abcdef01234567"


def _plugin() -> dict:
    return {
        "id": "research-probe",
        "name": "Research probe",
        "description": "Synthetic offline package for execution-identity research.",
        "repository": "example/research-probe",
        "ref": REF,
        "version": "1.0.0",
        "manifest": "agora.materializer.json",
        "package": {
            "type": "python-project",
            "path": ".",
            "install_trust": "explicit-code-execution",
        },
        "materializers": ["research-probe-to-tf"],
        "disciplines": ["digital-philology"],
        "licenses": {"software": "MIT", "data": "synthetic"},
        "verification": {"status": "experimental"},
    }


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "plugin": {
            "id": "research-probe",
            "name": "Research probe",
            "version": "1.0.0",
            "repository": "example/research-probe",
        },
        "materializers": [
            {
                "id": "research-probe-to-tf",
                "description": "Synthetic materializer used only for installer research.",
                "acquisition": [
                    {
                        "type": "user-local",
                        "path_type": "directory",
                        "prompt": "Select synthetic input",
                    }
                ],
                "input": {
                    "type": "directory",
                    "required_globs": ["*.txt"],
                    "allow_symlinks": False,
                },
                "execution": {
                    "type": "python-module",
                    "module": "research_probe.cli",
                    "args": ["{source}", "{output}"],
                    "network": "deny",
                },
                "output": {
                    "format": "text-fabric",
                    "required_paths": ["otype.tf", "oslots.tf"],
                },
            }
        ],
    }


def _backend_source() -> str:
    # A tiny local PEP-517 backend with no build requirements. It produces a
    # deterministic wheel so any installed-tree drift comes from the installer
    # / target topology, not network resolution or a changing build backend.
    return r'''from __future__ import annotations
import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path

DIST = "research_probe-1.0.0"
WHEEL = f"{DIST}-py3-none-any.whl"


def _digest(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    files = {
        "research_probe/__init__.py": b"",
        "research_probe/cli.py": b"def main():\n    return 0\n",
        f"{DIST}.dist-info/METADATA": (
            b"Metadata-Version: 2.1\nName: research-probe\nVersion: 1.0.0\n"
        ),
        f"{DIST}.dist-info/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: agora-research-probe\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
        f"{DIST}.dist-info/entry_points.txt": (
            b"[console_scripts]\nresearch-probe = research_probe.cli:main\n"
        ),
    }
    record_path = f"{DIST}.dist-info/RECORD"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for path in sorted(files):
        data = files[path]
        writer.writerow([path, _digest(data), str(len(data))])
    writer.writerow([record_path, "", ""])
    files[record_path] = stream.getvalue().encode("utf-8")

    destination = Path(wheel_directory) / WHEEL
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.writestr(path, files[path])
    return WHEEL
'''


def _write_source(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "backend.py").write_text(_backend_source(), encoding="utf-8")
    (path / "pyproject.toml").write_text(
        "[build-system]\nrequires = []\nbuild-backend = 'backend'\nbackend-path = ['.']\n\n"
        "[project]\nname = 'research-probe'\nversion = '1.0.0'\n",
        encoding="utf-8",
    )
    (path / "agora.materializer.json").write_text(
        json.dumps(_manifest(), sort_keys=True), encoding="utf-8"
    )


def _registry(path: Path) -> Path:
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "plugins": [_plugin()]}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _populate(_plugin_metadata: dict, destination: Path) -> str:
    _write_source(destination)
    return REF


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_inventory(root: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows[rel] = {"kind": "symlink", "target": os.readlink(path)}
        elif path.is_dir():
            rows[rel] = {"kind": "dir"}
        else:
            rows[rel] = {
                "kind": "file",
                "size": path.stat().st_size,
                "sha256": _file_sha(path),
            }
    return rows


def _text_excerpt(path: Path) -> str | None:
    if not path.is_file() or path.stat().st_size > 65536:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    # This is synthetic temporary-path metadata only; limit diagnostics so the
    # research log stays compact.
    return text[:2000]


class MaterializerExecutionIdentityResearchProbe(unittest.TestCase):
    def test_two_real_clean_installs_inventory_current_identity_drift(self):
        """Temporary research probe for #111; remove after evidence is recorded.

        This deliberately asserts the *current* defect, not the desired final
        contract. Its job is to produce empirical evidence before the design is
        finalized. The later TDD RED must instead require equal canonical
        execution identities and fail until production is fixed.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = _registry(root / "materializers.yaml")
            installs: list[tuple[Path, dict]] = []

            with mock.patch.object(installer, "_checkout", side_effect=_populate):
                for name in ("install-a", "install-b"):
                    target = installer.install_materializer(
                        "research-probe",
                        install_root=root / name,
                        registry_path=registry,
                        approve_code_execution=True,
                    )
                    receipt = json.loads(
                        (target / installer.INSTALLATION_RECEIPT).read_text(encoding="utf-8")
                    )
                    self.assertTrue(installer._environment_current(_plugin(), target))
                    installs.append((target, receipt))

            (left_target, left), (right_target, right) = installs
            self.assertEqual(left["source"]["tree_sha256"], right["source"]["tree_sha256"])
            self.assertEqual(left["runtime"], right["runtime"])
            self.assertEqual(
                left["environment"]["distributions"],
                right["environment"]["distributions"],
            )

            left_runtime = left_target / "runtime"
            right_runtime = right_target / "runtime"
            left_inventory = _tree_inventory(left_runtime)
            right_inventory = _tree_inventory(right_runtime)
            all_paths = sorted(set(left_inventory) | set(right_inventory))
            differing = [
                rel
                for rel in all_paths
                if left_inventory.get(rel) != right_inventory.get(rel)
            ]

            details = []
            for rel in differing:
                left_path = left_runtime / rel
                right_path = right_runtime / rel
                details.append(
                    {
                        "path": rel,
                        "left": left_inventory.get(rel),
                        "right": right_inventory.get(rel),
                        "left_text": _text_excerpt(left_path),
                        "right_text": _text_excerpt(right_path),
                    }
                )

            diagnostic = {
                "source_tree_equal": left["source"]["tree_sha256"] == right["source"]["tree_sha256"],
                "runtime_identity_equal": left["runtime"] == right["runtime"],
                "distributions_equal": left["environment"]["distributions"] == right["environment"]["distributions"],
                "raw_environment_equal": left["environment"]["tree_sha256"] == right["environment"]["tree_sha256"],
                "execution_identity_equal": left["execution_identity_sha256"] == right["execution_identity_sha256"],
                "pip_report_equal": left["environment"]["pip_report_sha256"] == right["environment"]["pip_report_sha256"],
                "differing_runtime_paths": differing,
                "differing_runtime_details": details,
            }
            print("EXECUTION_IDENTITY_RESEARCH=" + json.dumps(diagnostic, sort_keys=True))

            # Standards-backed expectation to verify against the real production
            # pip path. If this is false, the hypothesis must be revised.
            direct_url_paths = [rel for rel in differing if rel.endswith(".dist-info/direct_url.json")]
            self.assertTrue(direct_url_paths, diagnostic)
            direct_url_text = "\n".join(
                (_text_excerpt(left_runtime / rel) or "") + "\n" + (_text_excerpt(right_runtime / rel) or "")
                for rel in direct_url_paths
            )
            self.assertIn("agora-materializer-build-", direct_url_text)

            # The issue hypothesis is only established if the raw environment
            # and therefore schema-v2 execution identity really differ.
            self.assertNotEqual(
                left["environment"]["tree_sha256"],
                right["environment"]["tree_sha256"],
                diagnostic,
            )
            self.assertNotEqual(
                left["execution_identity_sha256"],
                right["execution_identity_sha256"],
                diagnostic,
            )


if __name__ == "__main__":
    unittest.main()
