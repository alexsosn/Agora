from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from scripts.agora_materialize import (
    AcquisitionError,
    acquire_source,
    ManifestError,
    acquire_http_archive_source,
    load_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "registry/schema/materializer-plugin.schema.json").read_text(encoding="utf-8")
)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _zip_bytes_with_symlink(name: str, target: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo(name)
        # 0xA1FF -> symlink mode in the external attributes' high 16 bits.
        info.external_attr = 0xA1FF << 16
        archive.writestr(info, target)
    return buffer.getvalue()


def _tar_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, payload in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strategy(payload: bytes, **overrides) -> dict:
    strategy = {
        "type": "http-archive",
        "url": "https://example.invalid/deposit/Workbooks.zip",
        "sha256": _digest(payload),
        "format": "zip",
        "subpath": "Workbooks",
    }
    strategy.update(overrides)
    return strategy


def _materializer() -> dict:
    return {
        "id": "fixture",
        "description": "Fixture materializer.",
        "acquisition": [],
        "input": {
            "type": "directory",
            "required_globs": ["*/*.pdf"],
            "allow_symlinks": False,
        },
        "execution": {
            "type": "python-module",
            "module": "fixture.cli",
            "args": ["{source}", "{output}"],
            "network": "deny",
        },
        "output": {"format": "text-fabric", "required_paths": ["otype.tf"]},
    }


def _manifest(acquisition: list[dict]) -> dict:
    materializer = _materializer()
    materializer["acquisition"] = acquisition
    return {
        "schema_version": 1,
        "plugin": {"id": "fixture-plugin", "name": "Fixture", "version": "1.0.0"},
        "materializers": [materializer],
    }


def _valid_payload() -> bytes:
    return _zip_bytes(
        {
            "Workbooks/01 Workbook I/sheet 1.pdf": b"%PDF-1.4 one\n",
            "Workbooks/02 Workbook II/sheet 2.pdf": b"%PDF-1.4 two\n",
        }
    )


class _FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, url: str = "https://example.invalid/deposit/Workbooks.zip"):
        super().__init__(payload)
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _urlopen(payload: bytes, url: str | None = None):
    def opener(request, *args, **kwargs):
        target = url or (request if isinstance(request, str) else request.full_url)
        return _FakeResponse(payload, target)

    return opener


class HttpArchiveSchemaTests(unittest.TestCase):
    def test_schema_accepts_pinned_http_archive_acquisition(self):
        document = _manifest([_strategy(_valid_payload())])
        self.assertEqual(list(Draft202012Validator(SCHEMA).iter_errors(document)), [])

    def test_schema_requires_a_sha256_digest(self):
        strategy = _strategy(_valid_payload())
        del strategy["sha256"]
        errors = list(Draft202012Validator(SCHEMA).iter_errors(_manifest([strategy])))
        self.assertTrue(errors)

    def test_schema_rejects_a_non_sha256_digest(self):
        document = _manifest([_strategy(_valid_payload(), sha256="deadbeef")])
        self.assertTrue(list(Draft202012Validator(SCHEMA).iter_errors(document)))

    def test_schema_rejects_plaintext_and_credentialed_urls(self):
        for url in (
            "http://example.invalid/Workbooks.zip",
            "https://user:pw@example.invalid/Workbooks.zip",
        ):
            with self.subTest(url=url):
                document = _manifest([_strategy(_valid_payload(), url=url)])
                self.assertTrue(list(Draft202012Validator(SCHEMA).iter_errors(document)))

    def test_schema_rejects_an_escaping_subpath(self):
        document = _manifest([_strategy(_valid_payload(), subpath="../outside")])
        self.assertTrue(list(Draft202012Validator(SCHEMA).iter_errors(document)))

    def test_manifest_semantics_reject_a_repeated_http_archive_strategy(self):
        payload = _valid_payload()
        document = _manifest([_strategy(payload), _strategy(payload)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agora.materializer.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "repeats strategy type"):
                load_manifest(path)


class HttpArchiveAcquisitionTests(unittest.TestCase):
    def test_pinned_archive_is_downloaded_verified_and_extracted(self):
        payload = _valid_payload()
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            prepared = acquire_http_archive_source(strategy, _materializer())
        try:
            self.assertTrue((prepared.path / "01 Workbook I" / "sheet 1.pdf").is_file())
            self.assertEqual(prepared.provenance["type"], "http-archive")
            self.assertEqual(prepared.provenance["url"], strategy["url"])
            self.assertEqual(prepared.provenance["sha256"], strategy["sha256"])
            self.assertEqual(prepared.provenance["subpath"], "Workbooks")
        finally:
            prepared.cleanup()

    def test_digest_mismatch_fails_without_extracting(self):
        payload = _valid_payload()
        strategy = _strategy(payload, sha256="0" * 64)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaisesRegex(AcquisitionError, "sha256"):
                acquire_http_archive_source(strategy, _materializer())

    def test_tar_archives_are_supported(self):
        payload = _tar_bytes(
            {
                "Workbooks/01 Workbook I/sheet 1.pdf": b"%PDF-1.4 one\n",
                "Workbooks/02 Workbook II/sheet 2.pdf": b"%PDF-1.4 two\n",
            }
        )
        strategy = _strategy(payload, format="tar", url="https://example.invalid/w.tar.gz")
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            prepared = acquire_http_archive_source(strategy, _materializer())
        try:
            self.assertTrue((prepared.path / "02 Workbook II" / "sheet 2.pdf").is_file())
        finally:
            prepared.cleanup()

    def test_archive_member_escaping_the_root_is_rejected(self):
        for name in ("../escape/sheet 1.pdf", "/absolute/sheet 1.pdf"):
            with self.subTest(name=name):
                payload = _zip_bytes({name: b"%PDF-1.4\n"})
                strategy = _strategy(payload)
                with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
                    with self.assertRaises(AcquisitionError):
                        acquire_http_archive_source(strategy, _materializer())

    def test_symlink_members_are_rejected(self):
        payload = _zip_bytes_with_symlink("Workbooks/link.pdf", "/etc/passwd")
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaisesRegex(AcquisitionError, "symlink|link"):
                acquire_http_archive_source(strategy, _materializer())

    def test_oversized_download_is_refused(self):
        payload = _valid_payload()
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with mock.patch("scripts.agora_materialize.MAX_ARCHIVE_DOWNLOAD_BYTES", 8):
                with self.assertRaisesRegex(AcquisitionError, "too large|exceeds"):
                    acquire_http_archive_source(strategy, _materializer())

    def test_oversized_extraction_is_refused(self):
        payload = _valid_payload()
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with mock.patch("scripts.agora_materialize.MAX_ARCHIVE_EXTRACTED_BYTES", 4):
                with self.assertRaisesRegex(AcquisitionError, "too large|exceeds"):
                    acquire_http_archive_source(strategy, _materializer())

    def test_redirect_away_from_https_is_refused(self):
        payload = _valid_payload()
        strategy = _strategy(payload)
        opener = _urlopen(payload, url="http://example.invalid/downgraded.zip")
        with mock.patch("scripts.agora_materialize.urlopen", opener):
            with self.assertRaisesRegex(AcquisitionError, "https"):
                acquire_http_archive_source(strategy, _materializer())

    def test_missing_subpath_inside_the_archive_is_reported(self):
        payload = _zip_bytes({"Other/01 Workbook I/sheet 1.pdf": b"%PDF-1.4\n"})
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaisesRegex(AcquisitionError, "Workbooks"):
                acquire_http_archive_source(strategy, _materializer())

    def test_extracted_source_must_satisfy_the_declared_input_contract(self):
        payload = _zip_bytes({"Workbooks/notes.txt": b"not a pdf\n"})
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaises(ValueError):
                acquire_http_archive_source(strategy, _materializer())


class HttpArchiveStrategySelectionTests(unittest.TestCase):
    def test_declared_http_archive_is_used_automatically(self):
        payload = _valid_payload()
        materializer = _materializer()
        materializer["acquisition"] = [_strategy(payload)]
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            prepared = acquire_source(materializer)
        try:
            self.assertEqual(prepared.provenance["type"], "http-archive")
        finally:
            prepared.cleanup()

    def test_archive_failure_is_reported_when_no_source_can_be_acquired(self):
        payload = _valid_payload()
        materializer = _materializer()
        materializer["acquisition"] = [
            _strategy(payload, sha256="0" * 64),
            {
                "type": "user-local",
                "path_type": "directory",
                "prompt": "Select the source directory",
            },
        ]
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with mock.patch("sys.stdin.isatty", return_value=False):
                with self.assertRaises(RuntimeError) as caught:
                    acquire_source(materializer)
        self.assertIn("sha256", str(caught.exception))

    def test_user_override_still_wins_over_a_declared_archive(self):
        payload = _valid_payload()
        materializer = _materializer()
        materializer["acquisition"] = [
            _strategy(payload),
            {
                "type": "user-local",
                "path_type": "directory",
                "prompt": "Select the source directory",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "Workbooks" / "01 Workbook I"
            local.mkdir(parents=True)
            (local / "sheet 1.pdf").write_bytes(b"%PDF-1.4 local\n")
            with mock.patch("scripts.agora_materialize.urlopen") as opener:
                prepared = acquire_source(
                    materializer, source_override=Path(tmp) / "Workbooks"
                )
            opener.assert_not_called()
        self.assertEqual(prepared.provenance["type"], "user-local")


if __name__ == "__main__":
    unittest.main()
