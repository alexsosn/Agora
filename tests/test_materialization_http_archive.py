from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tarfile
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from scripts import agora_materialize

from scripts.agora_materialize import (
    HTTP_TIMEOUT_SECONDS,
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


def _tar_bytes_from_members(members: list[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    """Build a tar whose members may be any type, not only plain regular files."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info, payload in members:
            if payload is None:
                archive.addfile(info)
            else:
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _tar_regular(name: str, *, mode: int = 0o644) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.mode = mode
    return info, b"%PDF-1.4\n"


def _tar_member(name: str, member_type: bytes, *, linkname: str = "") -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type = member_type
    info.linkname = linkname
    info.size = 0
    return info, None


def _recording_urlopen(payload: bytes):
    """Like `_urlopen`, but records how the production code called it."""
    calls: list[dict] = []

    def opener(request, *args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        target = request if isinstance(request, str) else request.full_url
        return _FakeResponse(payload, target)

    return opener, calls


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
        """The name of this contract is the contract: nothing may be extracted.

        Asserting only that an `AcquisitionError` mentioning "sha256" is raised
        leaves the ordering free -- production could extract first and verify
        afterwards with this test still green. Observing the extractors proves
        the digest actually gates them.
        """
        payload = _valid_payload()
        strategy = _strategy(payload, sha256="0" * 64)
        with (
            mock.patch("scripts.agora_materialize._extract_zip_archive") as extract_zip,
            mock.patch("scripts.agora_materialize._extract_tar_archive") as extract_tar,
            mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)),
        ):
            with self.assertRaisesRegex(AcquisitionError, "sha256"):
                acquire_http_archive_source(strategy, _materializer())
        self.assertFalse(extract_zip.called, "digest mismatch still reached zip extraction")
        self.assertFalse(extract_tar.called, "digest mismatch still reached tar extraction")

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
        """The member is named `alias.pdf` on purpose.

        The previous fixture was named `link.pdf` and the assertion accepted
        "symlink|link", so the error merely echoing the member name satisfied
        it: deleting the symlink branch entirely left this test green.
        """
        payload = _zip_bytes_with_symlink("Workbooks/alias.pdf", "/etc/passwd")
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("symlink member", str(caught.exception))

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
        # "Workbooks" also occurs in the strategy URL, so matching it proved
        # nothing about the subpath check.
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("does not contain the declared subpath", str(caught.exception))

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


class HttpArchiveExtractionHardeningTests(unittest.TestCase):
    """Contracts for guards the suite previously left unconstrained.

    An adversarial review of the merged change mutated each production guard in
    turn and found that nine of ten survived the original suite, including
    deleting both of the tar path's independent anti-traversal layers. The tests
    below are written so that removing the guard they name makes them fail.

    Two rules are followed throughout: assert the *reason* rather than a string
    that a fixture name or a URL could also supply, and assert observable state
    rather than only that some exception was raised.
    """

    TAR_URL = "https://example.invalid/deposit/Workbooks.tar.gz"

    def _acquire_tar(self, payload: bytes):
        strategy = _strategy(payload, format="tar", url=self.TAR_URL)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            return acquire_http_archive_source(strategy, _materializer())

    def _refuse_tar(self, payload: bytes) -> str:
        with self.assertRaises(AcquisitionError) as caught:
            self._acquire_tar(payload)
        return str(caught.exception)

    # --- tar member types: `_tar_bytes` only ever built regular files ---

    def test_tar_symlink_members_are_rejected(self):
        payload = _tar_bytes_from_members(
            [_tar_member("Workbooks/alias.pdf", tarfile.SYMTYPE, linkname="/etc/passwd")]
        )
        self.assertIn("link member", self._refuse_tar(payload))

    def test_tar_hardlink_members_are_rejected(self):
        payload = _tar_bytes_from_members(
            [
                _tar_regular("Workbooks/01 Workbook I/sheet 1.pdf"),
                _tar_member(
                    "Workbooks/01 Workbook I/alias.pdf",
                    tarfile.LNKTYPE,
                    linkname="Workbooks/01 Workbook I/sheet 1.pdf",
                ),
            ]
        )
        self.assertIn("link member", self._refuse_tar(payload))

    def test_tar_device_members_are_rejected(self):
        payload = _tar_bytes_from_members(
            [_tar_member("Workbooks/console", tarfile.CHRTYPE)]
        )
        self.assertIn("non-regular member", self._refuse_tar(payload))

    def test_tar_members_escaping_the_extraction_root_are_rejected(self):
        for name in (
            "../escape/sheet 1.pdf",
            "/absolute/sheet 1.pdf",
            "Workbooks/../../escape/sheet 1.pdf",
            "..\\escape\\sheet 1.pdf",
        ):
            with self.subTest(name=name):
                payload = _tar_bytes_from_members([_tar_regular(name)])
                self.assertIn("escapes the extraction root", self._refuse_tar(payload))

    def test_extracted_tar_files_do_not_keep_setuid_bits(self):
        """Pins `extractall(..., filter="data")` by its effect, not its spelling.

        Our own member checks accept a regular file whose mode happens to carry
        setuid; only the data filter clamps it. On Python 3.13 omitting the
        filter preserves 0o4755, so deleting it fails this test.
        """
        payload = _tar_bytes_from_members(
            [_tar_regular("Workbooks/01 Workbook I/privileged.pdf", mode=0o4755)]
        )
        prepared = self._acquire_tar(payload)
        try:
            extracted = prepared.path / "01 Workbook I" / "privileged.pdf"
            mode = extracted.stat().st_mode
            self.assertFalse(stat.S_ISUID & mode, oct(stat.S_IMODE(mode)))
            self.assertFalse(stat.S_ISGID & mode, oct(stat.S_IMODE(mode)))
        finally:
            prepared.cleanup()

    # --- caps that no test previously exercised ------------------------

    def test_zip_member_count_cap_is_enforced(self):
        payload = _zip_bytes(
            {f"Workbooks/01 Workbook I/sheet {index}.pdf": b"%PDF-1.4\n" for index in range(3)}
        )
        strategy = _strategy(payload)
        with (
            mock.patch("scripts.agora_materialize.MAX_ARCHIVE_MEMBERS", 2),
            mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)),
        ):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("too many members", str(caught.exception))

    def test_tar_member_count_cap_is_enforced(self):
        payload = _tar_bytes_from_members(
            [_tar_regular(f"Workbooks/01 Workbook I/sheet {index}.pdf") for index in range(3)]
        )
        strategy = _strategy(payload, format="tar", url=self.TAR_URL)
        with (
            mock.patch("scripts.agora_materialize.MAX_ARCHIVE_MEMBERS", 2),
            mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)),
        ):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("too many members", str(caught.exception))

    def test_tar_extraction_size_cap_is_enforced(self):
        """The existing cap test only ever exercised the zip path."""
        payload = _tar_bytes_from_members(
            [_tar_regular("Workbooks/01 Workbook I/sheet 1.pdf")]
        )
        strategy = _strategy(payload, format="tar", url=self.TAR_URL)
        with (
            mock.patch("scripts.agora_materialize.MAX_ARCHIVE_EXTRACTED_BYTES", 4),
            mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)),
        ):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("exceeds", str(caught.exception))

    # --- runtime URL checks, independent of the schema -----------------

    def test_runtime_refuses_a_credentialed_or_plaintext_url(self):
        """Defence in depth: the schema also rejects these, but the schema is
        not what guards a strategy reaching the acquisition helper directly.
        """
        payload = _valid_payload()
        for url in (
            "https://user:pw@example.invalid/deposit/Workbooks.zip",
            "http://example.invalid/deposit/Workbooks.zip",
        ):
            with self.subTest(url=url):
                strategy = _strategy(payload, url=url)
                with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
                    with self.assertRaises(AcquisitionError) as caught:
                        acquire_http_archive_source(strategy, _materializer())
                self.assertIn("credential-free https URL", str(caught.exception))

    # --- the download call itself --------------------------------------

    def test_download_passes_the_configured_timeout(self):
        """Pins that a timeout is passed at all; its semantics are a separate
        defect. `urlopen(timeout=...)` bounds each socket operation, not the
        whole transfer, so a trickling server is still unbounded. Tightening
        that is tracked separately; this only stops the argument vanishing.
        """
        payload = _valid_payload()
        opener, calls = _recording_urlopen(payload)
        strategy = _strategy(payload)
        with mock.patch("scripts.agora_materialize.urlopen", opener):
            prepared = acquire_http_archive_source(strategy, _materializer())
        prepared.cleanup()
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0]["kwargs"].get("timeout"), HTTP_TIMEOUT_SECONDS)


class HttpArchiveFailureReportingTests(unittest.TestCase):
    """A corrupt or mis-declared deposit must fail as an acquisition failure.

    `zipfile.BadZipFile` and `tarfile.ReadError` are not `AcquisitionError`, so
    they escape `acquire_source`'s `except AcquisitionError` handler: the user
    gets a bare stdlib traceback with no mention of the materializer, the URL or
    acquisition, and the declared `user-local` fallback is never offered.
    """

    def _mismatched(self) -> tuple[bytes, dict]:
        """Real tar bytes whose digest matches, declared as a zip."""
        payload = _tar_bytes({"Workbooks/01 Workbook I/sheet 1.pdf": b"%PDF-1.4\n"})
        return payload, _strategy(payload, format="zip")

    def test_a_mis_declared_zip_is_reported_as_an_acquisition_error(self):
        payload, strategy = self._mismatched()
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        message = str(caught.exception)
        self.assertIn(strategy["url"], message)
        self.assertIn("could not be read as a zip archive", message)

    def test_a_mis_declared_tar_is_reported_as_an_acquisition_error(self):
        payload = _valid_payload()
        strategy = _strategy(payload, format="tar")
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("could not be read as a tar archive", str(caught.exception))

    def test_a_corrupt_archive_does_not_defeat_the_declared_fallback(self):
        """The whole point of wrapping: `acquire_source` must stay in control."""
        payload, strategy = self._mismatched()
        materializer = _materializer()
        materializer["acquisition"] = [
            strategy,
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
        message = str(caught.exception)
        self.assertNotIsInstance(caught.exception, zipfile.BadZipFile)
        self.assertIn("could not be read as a zip archive", message)

    def test_a_corrupt_archive_offers_the_interactive_fallback(self):
        payload, strategy = self._mismatched()
        materializer = _materializer()
        materializer["acquisition"] = [
            strategy,
            {
                "type": "user-local",
                "path_type": "directory",
                "prompt": "Select the source directory",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "Workbooks" / "01 Workbook I"
            local.mkdir(parents=True)
            (local / "sheet 1.pdf").write_bytes(b"%PDF-1.4\n")
            with (
                mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)),
                mock.patch("sys.stdin.isatty", return_value=True),
                mock.patch("builtins.input", return_value=str(local.parent)),
            ):
                prepared = acquire_source(materializer)
            try:
                self.assertEqual(prepared.provenance["type"], "user-local")
            finally:
                prepared.cleanup()


def _tar_with_pax_metadata(metadata_bytes: int) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo("Workbooks/01 Workbook I/sheet 1.pdf")
        info.pax_headers = {"comment": "x" * metadata_bytes}
        payload = b"%PDF-1.4\n"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _tar_sized(name: str, payload: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.mode = 0o644
    return info, payload


class _CountingFile:
    """A read-through file wrapper that records how much was pulled."""

    def __init__(self, handle, counter: dict):
        self._handle = handle
        self._counter = counter

    def read(self, size=-1):
        data = self._handle.read(size)
        self._counter["bytes"] += len(data)
        return data

    def seek(self, *args):
        return self._handle.seek(*args)

    def tell(self):
        return self._handle.tell()

    def close(self):
        return self._handle.close()

    def readable(self):
        return True

    def seekable(self):
        return True


class _TricklingResponse:
    """A server that trickles: slow enough that only a deadline stops it early.

    Finite on purpose. Without a deadline the transfer runs to completion and
    fails on the digest instead, so the RED failure names the missing deadline
    rather than hanging or tripping the download size cap.
    """

    def __init__(self, url: str, chunks: int = 5000):
        self.url = url
        self.reads = 0
        self._chunks = chunks

    def read(self, size=-1):
        if self.reads >= self._chunks:
            return b""
        self.reads += 1
        return b"x" * 16

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class HttpArchiveTransferBoundsTests(unittest.TestCase):
    """Bounds that must hold against a server or deposit that misbehaves slowly.

    `urlopen(timeout=...)` bounds each socket operation and resets on every
    read, so it does not bound a transfer at all; and walking a compressed tar
    index forces the whole payload through the decompressor before any size cap
    is consulted. Both were measured against the merged implementation.
    """

    TAR_URL = "https://example.invalid/deposit/Workbooks.tar.gz"

    def test_download_is_bounded_by_a_wall_clock_deadline(self):
        """A server trickling bytes forever must not hang acquisition forever."""
        response = _TricklingResponse("https://example.invalid/deposit/Workbooks.zip")
        clock = {"now": 0.0}

        def monotonic() -> float:
            clock["now"] += 10.0
            return clock["now"]

        strategy = _strategy(b"", sha256="0" * 64)
        with (
            mock.patch.object(
                agora_materialize, "time", types.SimpleNamespace(monotonic=monotonic), create=True
            ),
            mock.patch("scripts.agora_materialize.urlopen", lambda *a, **k: response),
        ):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("deadline", str(caught.exception))
        self.assertLess(response.reads, 5000, "the read loop ran to completion anyway")

    def test_tar_extension_metadata_has_its_own_decompression_budget(self):
        payload = _tar_with_pax_metadata(64 * 1024)
        strategy = _strategy(payload, format="tar", url=self.TAR_URL)
        with (
            mock.patch(
                "scripts.agora_materialize.MAX_ARCHIVE_TAR_METADATA_BYTES",
                1024,
                create=True,
            ),
            mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)),
        ):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("metadata", str(caught.exception))

    def test_gnu_sparse_tar_members_are_refused_before_sparse_metadata_processing(self):
        payload = _tar_bytes_from_members(
            [_tar_member("Workbooks/01 Workbook I/sparse.pdf", tarfile.GNUTYPE_SPARSE)]
        )
        strategy = _strategy(payload, format="tar", url=self.TAR_URL)
        with mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("sparse", str(caught.exception).casefold())

    def test_tar_index_walk_stops_before_inflating_the_whole_stream(self):
        """The cap must bound decompression work, not only bytes written.

        The filler member is incompressible, so walking the full index pulls
        essentially the whole archive through the decompressor. Enforcing the
        cap while walking stops at the first offending member instead.
        """
        payload = _tar_bytes_from_members(
            [
                _tar_sized("Workbooks/01 Workbook I/sheet 1.pdf", b"%PDF-1.4" + b"0" * 64),
                _tar_sized("Workbooks/01 Workbook I/filler.pdf", os.urandom(1 << 20)),
            ]
        )
        counter = {"bytes": 0}
        real_open = tarfile.open
        # tarfile never closes an externally supplied fileobj, so close it here.
        handles: list = []

        def counting_open(name=None, *args, **kwargs):
            handle = open(name, "rb")
            handles.append(handle)
            self.addCleanup(handle.close)
            return real_open(fileobj=_CountingFile(handle, counter), *args, **kwargs)

        strategy = _strategy(payload, format="tar", url=self.TAR_URL)
        with (
            mock.patch("scripts.agora_materialize.MAX_ARCHIVE_EXTRACTED_BYTES", 16),
            mock.patch.object(agora_materialize.tarfile, "open", counting_open),
            mock.patch("scripts.agora_materialize.urlopen", _urlopen(payload)),
        ):
            with self.assertRaises(AcquisitionError) as caught:
                acquire_http_archive_source(strategy, _materializer())
        self.assertIn("exceeds", str(caught.exception))
        self.assertLess(
            counter["bytes"],
            len(payload) // 4,
            f"pulled {counter['bytes']} of {len(payload)} compressed bytes before refusing",
        )


if __name__ == "__main__":
    unittest.main()
