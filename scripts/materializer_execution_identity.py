from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

_CANONICAL_LOCAL_PROJECT_URI = "agora+identity://managed-local-project/source"
_STAGING_DIR_RE = re.compile(r"^agora-materializer-build-[^/\\]+$")


class CanonicalExecutionIdentityError(ValueError):
    pass


def _sha256_record_value(data: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _is_agora_staging_uri(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme != "file" or parsed.netloc or parsed.query or parsed.fragment:
        return False
    path = unquote(parsed.path)
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in {".", ".."} for part in parts):
        return False
    compact = [part for part in parts if part]
    return (
        len(compact) >= 2
        and compact[-1] == "source"
        and _STAGING_DIR_RE.fullmatch(compact[-2]) is not None
    )


def _requested_local_project_uri(report_path: Path) -> str:
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalExecutionIdentityError(f"cannot parse stored pip report: {exc}") from exc

    installs = report.get("install")
    if not isinstance(installs, list):
        raise CanonicalExecutionIdentityError("pip report install field is not a list")

    candidates: list[str] = []
    for row in installs:
        if (
            not isinstance(row, dict)
            or row.get("requested") is not True
            or row.get("is_direct") is not True
        ):
            continue
        download = row.get("download_info")
        if not isinstance(download, dict):
            continue
        if set(download) != {"url", "dir_info"} or download.get("dir_info") != {}:
            continue
        url = download.get("url")
        if isinstance(url, str) and _is_agora_staging_uri(url):
            candidates.append(url)

    if len(candidates) != 1:
        raise CanonicalExecutionIdentityError(
            "pip report must contain exactly one requested Agora staging local-project origin"
        )
    return candidates[0]


def _parse_direct_url(path: Path, expected_uri: str) -> tuple[bytes, bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalExecutionIdentityError(f"cannot parse {path.name}: {exc}") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"dir_info", "url"}
        or value.get("dir_info") != {}
    ):
        raise CanonicalExecutionIdentityError(
            "managed direct_url.json has unexpected local-directory shape"
        )
    url = value.get("url")
    if not isinstance(url, str) or url != expected_uri or not _is_agora_staging_uri(url):
        raise CanonicalExecutionIdentityError(
            "managed direct_url.json origin does not match the verified pip report"
        )
    canonical = dict(value)
    canonical["url"] = _CANONICAL_LOCAL_PROJECT_URI
    return raw, _canonical_json_bytes(canonical)


def _canonical_record_bytes(
    record_path: Path,
    direct_url_rel: str,
    raw_direct_url: bytes,
    canonical_direct_url: bytes,
) -> bytes:
    try:
        text = record_path.read_text(encoding="utf-8")
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise CanonicalExecutionIdentityError(f"cannot parse RECORD: {exc}") from exc
    if not rows or any(len(row) != 3 for row in rows):
        raise CanonicalExecutionIdentityError(
            "RECORD must contain exactly three columns per row"
        )

    matches = [index for index, row in enumerate(rows) if row[0] == direct_url_rel]
    if len(matches) != 1:
        raise CanonicalExecutionIdentityError(
            "RECORD must contain exactly one row for managed direct_url.json"
        )
    index = matches[0]
    expected_hash = _sha256_record_value(raw_direct_url)
    expected_size = str(len(raw_direct_url))
    if rows[index][1:] != [expected_hash, expected_size]:
        raise CanonicalExecutionIdentityError(
            "RECORD direct_url.json row does not match installed bytes"
        )

    seen: set[str] = set()
    for row in rows:
        if not row[0] or row[0] in seen:
            raise CanonicalExecutionIdentityError(
                "RECORD contains an empty or duplicate path"
            )
        seen.add(row[0])

    rows[index][1] = _sha256_record_value(canonical_direct_url)
    rows[index][2] = str(len(canonical_direct_url))
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def _canonical_distlib_launcher(data: bytes) -> bytes:
    signature = b"PK\x03\x04"
    starts = [match.start() for match in re.finditer(re.escape(signature), data)]
    parsed_start: int | None = None
    info: zipfile.ZipInfo | None = None
    for start in reversed(starts):
        try:
            with zipfile.ZipFile(io.BytesIO(data[start:]), "r") as archive:
                infos = archive.infolist()
                if len(infos) != 1 or infos[0].filename != "__main__.py":
                    continue
                if archive.comment:
                    continue
                archive.read("__main__.py")
                parsed_start = start
                info = infos[0]
                break
        except (OSError, ValueError, zipfile.BadZipFile, RuntimeError):
            continue
    if parsed_start is None or info is None:
        raise CanonicalExecutionIdentityError(
            "Windows launcher is not the recognized distlib single-entry format"
        )

    archive_bytes = bytearray(data[parsed_start:])
    local_offset = info.header_offset
    if archive_bytes[local_offset : local_offset + 4] != b"PK\x03\x04":
        raise CanonicalExecutionIdentityError(
            "Windows launcher local ZIP header is inconsistent"
        )
    # DOS modification time/date in the local file header.
    archive_bytes[local_offset + 10 : local_offset + 14] = b"\0" * 4

    central_starts = [
        match.start()
        for match in re.finditer(re.escape(b"PK\x01\x02"), bytes(archive_bytes))
    ]
    if len(central_starts) != 1:
        raise CanonicalExecutionIdentityError(
            "Windows launcher must contain exactly one central-directory entry"
        )
    central = central_starts[0]
    archive_bytes[central + 12 : central + 16] = b"\0" * 4

    return data[:parsed_start] + bytes(archive_bytes)


def canonical_execution_tree_hash(
    runtime: Path,
    pip_report_path: Path,
    *,
    excludes: set[str] | None = None,
) -> str:
    runtime = Path(runtime).resolve()
    expected_uri = _requested_local_project_uri(Path(pip_report_path))
    excludes = excludes or set()

    direct_urls = [
        path for path in runtime.glob("*.dist-info/direct_url.json") if path.is_file()
    ]
    matched: list[tuple[Path, bytes, bytes]] = []
    for path in direct_urls:
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanonicalExecutionIdentityError(f"cannot parse {path}: {exc}") from exc
        if isinstance(value, dict) and value.get("url") == expected_uri:
            raw, canonical = _parse_direct_url(path, expected_uri)
            matched.append((path, raw, canonical))
    if len(matched) != 1:
        raise CanonicalExecutionIdentityError(
            "installed runtime must contain exactly one direct_url.json matching the verified pip report"
        )

    direct_path, raw_direct, canonical_direct = matched[0]
    dist_info = direct_path.parent
    record_path = dist_info / "RECORD"
    if not record_path.is_file():
        raise CanonicalExecutionIdentityError("managed distribution RECORD is missing")
    direct_rel = direct_path.relative_to(runtime).as_posix()
    canonical_record = _canonical_record_bytes(
        record_path, direct_rel, raw_direct, canonical_direct
    )

    overrides: dict[str, bytes] = {
        direct_rel: canonical_direct,
        record_path.relative_to(runtime).as_posix(): canonical_record,
    }

    entry_points = dist_info / "entry_points.txt"
    launcher_names: set[str] = set()
    if entry_points.is_file():
        section: str | None = None
        try:
            for raw_line in entry_points.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith(("#", ";")):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    continue
                if section in {"console_scripts", "gui_scripts"} and "=" in line:
                    name = line.split("=", 1)[0].strip()
                    if name:
                        launcher_names.add(name)
        except (OSError, UnicodeDecodeError) as exc:
            raise CanonicalExecutionIdentityError(
                f"cannot parse entry_points.txt: {exc}"
            ) from exc

    for name in sorted(launcher_names):
        candidates = [
            runtime / "bin" / f"{name}.exe",
            runtime / "Scripts" / f"{name}.exe",
        ]
        existing = [path for path in candidates if path.is_file()]
        if len(existing) > 1:
            raise CanonicalExecutionIdentityError(
                f"ambiguous Windows launcher for {name!r}"
            )
        if existing:
            launcher = existing[0]
            overrides[launcher.relative_to(runtime).as_posix()] = (
                _canonical_distlib_launcher(launcher.read_bytes())
            )

    digest = hashlib.sha256()
    for path in sorted(
        runtime.rglob("*"), key=lambda item: item.relative_to(runtime).as_posix()
    ):
        rel = path.relative_to(runtime)
        if any(part in excludes for part in rel.parts):
            continue
        rel_name = rel.as_posix()
        name = rel_name.encode()
        if path.is_symlink():
            digest.update(b"L\0" + name + b"\0" + os.readlink(path).encode() + b"\0")
        elif path.is_dir():
            digest.update(b"D\0" + name + b"\0")
        elif path.is_file():
            digest.update(b"F\0" + name + b"\0")
            data = overrides.get(rel_name)
            if data is None:
                data = path.read_bytes()
            digest.update(data)
            digest.update(b"\0")
    return digest.hexdigest()
