"""Inspection-only research gate for pinned public TF GitHub Release ZIP assets.

This is NOT an archive-backed Context-Fabric corpus resolver. It downloads only
known v1.0.0 assets through Agora's existing bounded, checksum-validating HTTPS
helper, and examines ZIP central directories without extracting or executing code.
"""
from __future__ import annotations

import argparse
import json
import posixpath
import stat
import tempfile
import zipfile
from pathlib import Path

from scripts.agora_materialize import (
    MAX_ARCHIVE_EXTRACTED_BYTES,
    MAX_ARCHIVE_MEMBERS,
    _check_archive_member_name,
    _download_pinned_archive,
)

_RELEASE_URL = "https://github.com/alexsosn/Pseudepigrapha-TF/releases/download/v1.0.0/"
PINNED_RELEASE_ASSETS = {
    "complete.zip": {
        "sha256": "1ea4488202d1e9fbc008abaabff14f220328118fc52bed3a06a2d331b145bb7d",
        "size": 9_643_332,
    },
    "tf-1.0.zip": {
        "sha256": "d2dfad7e643699617a9493b9f5d724868f8027dd5f2e88bd558451e3e7819b7a",
        "size": 9_632_449,
    },
}


def inspect_zip(
    archive_path: Path, *, max_members: int = MAX_ARCHIVE_MEMBERS,
    max_expanded_bytes: int = MAX_ARCHIVE_EXTRACTED_BYTES,
) -> dict[str, object]:
    """Read ZIP metadata only; reject unsafe names/types and report TF warp roots."""
    names: set[str] = set()
    roots: dict[str, set[str]] = {}
    declared_total = 0
    regular_members = 0
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > max_members:
            raise ValueError("archive exceeds member count cap")
        for info in infos:
            name = info.filename
            _check_archive_member_name(name)
            # Extraction safety is deliberately stricter than simple lookup:
            # reject platform-specific aliases rather than normalizing them.
            if (
                not name or "\\" in name or "//" in name
                or name.startswith("./") or name.startswith("/")
                or any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in name)
                or posixpath.normpath(name) != name.rstrip("/")
            ):
                raise ValueError(f"archive contains unsafe or noncanonical member: {name!r}")
            normalized = name.rstrip("/")
            if normalized in names:
                raise ValueError(f"archive has duplicate member: {normalized!r}")
            names.add(normalized)
            file_type = stat.S_IFMT(info.external_attr >> 16)
            if file_type == stat.S_IFLNK:
                raise ValueError(f"archive contains symlink: {name!r}")
            if info.is_dir():
                if file_type not in (0, stat.S_IFDIR):
                    raise ValueError(f"archive contains non-directory type: {name!r}")
                continue
            if file_type not in (0, stat.S_IFREG):
                raise ValueError(f"archive contains unsupported special member: {name!r}")
            declared_total += info.file_size
            regular_members += 1
            if declared_total > max_expanded_bytes:
                raise ValueError("archive exceeds declared expanded byte cap")
            root, _, leaf = normalized.rpartition("/")
            if leaf in ("otype.tf", "oslots.tf"):
                roots.setdefault(root, set()).add(leaf)
    tf_roots = sorted(root for root, features in roots.items() if features == {"otype.tf", "oslots.tf"})
    if not tf_roots:
        raise ValueError("archive contains no paired otype.tf/oslots.tf Text-Fabric warp root")
    return {
        "tf_roots": tf_roots,
        "warp_roots": len(tf_roots),
        "members": regular_members,
        "declared_bytes": declared_total,
        "other_partial_warp_roots": sorted(set(roots) - set(tf_roots)),
    }


def probe_pinned_asset(name: str) -> dict[str, object]:
    if name not in PINNED_RELEASE_ASSETS:
        raise ValueError(f"unknown immutable release asset: {name}")
    spec = PINNED_RELEASE_ASSETS[name]
    with tempfile.TemporaryDirectory(prefix="agora-release-probe-") as temp:
        archive_path = Path(temp) / "pinned.zip"
        _download_pinned_archive(
            {"url": _RELEASE_URL + name, "sha256": spec["sha256"]},
            archive_path,
        )
        size = archive_path.stat().st_size
        if size != spec["size"]:
            raise ValueError(f"pinned asset size changed: expected {spec['size']}, got {size}")
        report = inspect_zip(archive_path)
    return {
        "release": "v1.0.0",
        "asset": name,
        "sha256": spec["sha256"],
        "compressed_bytes": size,
        **report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and inspect immutable Text-Fabric release assets")
    parser.add_argument("--asset", choices=sorted(PINNED_RELEASE_ASSETS), required=True)
    args = parser.parse_args()
    print(json.dumps(probe_pinned_asset(args.asset), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
