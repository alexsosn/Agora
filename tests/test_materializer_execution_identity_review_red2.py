from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.materializer_execution_identity import (
    CanonicalExecutionIdentityError,
    canonical_execution_tree_hash,
)


def _record_hash(data: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


def _launcher_bytes(payload: bytes = b"print('ok')\n", *, prefix: bytes | None = None) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("__main__.py", payload)
    # Minimal structural stand-in for the researched distlib layout: a native
    # Windows launcher prefix, an appended shebang, then a single-entry ZIP.
    # Production must not classify an arbitrary opaque prefix as distlib merely
    # because a parseable __main__.py ZIP happens to be appended.
    if prefix is None:
        prefix = b"MZ" + (b"\0" * 30) + b"#!C:/Python/python.exe\n"
    return prefix + archive.getvalue()


def _write_runtime(
    root: Path,
    *,
    launcher_record_path: str = "../../bin/probe.exe",
    launcher_prefix: bytes | None = None,
) -> tuple[Path, Path]:
    runtime = root / "runtime"
    dist_info = runtime / "research_probe-1.0.0.dist-info"
    package = runtime / "research_probe"
    launcher = runtime / "bin" / "probe.exe"
    dist_info.mkdir(parents=True)
    package.mkdir(parents=True)
    launcher.parent.mkdir(parents=True)

    (package / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(
        "[console_scripts]\nprobe = research_probe.cli:main\n",
        encoding="utf-8",
    )

    staging = root / "agora-materializer-build-red2"
    source = staging / "source"
    source.mkdir(parents=True)
    source_uri = source.resolve().as_uri()
    direct_bytes = json.dumps({"dir_info": {}, "url": source_uri}).encode("utf-8")
    (dist_info / "direct_url.json").write_bytes(direct_bytes)

    launcher_bytes = _launcher_bytes(prefix=launcher_prefix)
    launcher.write_bytes(launcher_bytes)

    rows = [
        [
            "research_probe-1.0.0.dist-info/direct_url.json",
            _record_hash(direct_bytes),
            str(len(direct_bytes)),
        ],
        [launcher_record_path, _record_hash(launcher_bytes), str(len(launcher_bytes))],
        ["research_probe/cli.py", "sha256=unrelated-control", "25"],
        ["research_probe-1.0.0.dist-info/RECORD", "", ""],
    ]
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\n").writerows(rows)
    (dist_info / "RECORD").write_text(out.getvalue(), encoding="utf-8")

    report = root / "pip-report.json"
    report.write_text(
        json.dumps(
            {
                "version": "1",
                "install": [
                    {
                        "download_info": {"url": source_uri, "dir_info": {}},
                        "is_direct": True,
                        "requested": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return runtime, report


class ExecutionIdentityReviewRed2Tests(unittest.TestCase):
    def test_observed_pip_launcher_record_path_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, report = _write_runtime(Path(tmp))
            digest = canonical_execution_tree_hash(runtime, report)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_same_basename_and_integrity_at_unrelated_record_path_fails_closed(self):
        """Only the pip path corresponding to runtime/bin/probe.exe may be normalized.

        The Windows research probe observed ../../bin/<entry-point>.exe. Matching
        merely by basename plus raw integrity would let an unrelated RECORD row
        authorize normalization while the real launcher row is missing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runtime, report = _write_runtime(
                Path(tmp), launcher_record_path="bogus/probe.exe"
            )
            with self.assertRaisesRegex(
                CanonicalExecutionIdentityError,
                r"RECORD|launcher|correspond|path",
            ):
                canonical_execution_tree_hash(runtime, report)

    def test_arbitrary_opaque_prefix_is_not_treated_as_distlib_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, report = _write_runtime(
                Path(tmp),
                launcher_prefix=b"custom-program-with-self-inspected-zip-metadata\n",
            )
            with self.assertRaisesRegex(
                CanonicalExecutionIdentityError,
                r"distlib|launcher|native|shebang|format",
            ):
                canonical_execution_tree_hash(runtime, report)

    def test_unrelated_record_row_remains_identity_significant(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, report = _write_runtime(Path(tmp))
            before = canonical_execution_tree_hash(runtime, report)
            record = runtime / "research_probe-1.0.0.dist-info" / "RECORD"
            text = record.read_text(encoding="utf-8")
            record.write_text(
                text.replace("sha256=unrelated-control", "sha256=changed-control"),
                encoding="utf-8",
            )
            after = canonical_execution_tree_hash(runtime, report)
        self.assertNotEqual(before, after)

    def test_launcher_payload_change_with_matching_record_remains_identity_significant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, report = _write_runtime(root)
            before = canonical_execution_tree_hash(runtime, report)

            launcher = runtime / "bin" / "probe.exe"
            changed = _launcher_bytes(b"print('changed')\n")
            launcher.write_bytes(changed)
            record = runtime / "research_probe-1.0.0.dist-info" / "RECORD"
            rows = list(csv.reader(io.StringIO(record.read_text(encoding="utf-8"))))
            for row in rows:
                if row[0] == "../../bin/probe.exe":
                    row[1] = _record_hash(changed)
                    row[2] = str(len(changed))
            out = io.StringIO(newline="")
            csv.writer(out, lineterminator="\n").writerows(rows)
            record.write_text(out.getvalue(), encoding="utf-8")

            after = canonical_execution_tree_hash(runtime, report)
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
