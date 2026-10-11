"""#251 RED: downloader for exact, time-bounded GitHub Release assets."""
from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins/context-fabric/src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.operation import OperationCancelled, OperationControl
from agora_context_fabric.release_download import (
    SafeReleaseRedirect, download_pinned_release,
)

PAYLOAD = b"tiny pinned upstream ZIP substitute\n"


class Response(io.BytesIO):
    def __init__(self, payload=PAYLOAD, url=None):
        super().__init__(payload)
        self.url = url or (
            "https://release-assets.githubusercontent.com/github-production-release-asset/123/fixture"
        )

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, payload=PAYLOAD, url=None, exc=None):
        self.payload = payload
        self.url = url
        self.exc = exc
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append((request.full_url, timeout))
        if self.exc is not None:
            raise self.exc
        return Response(self.payload, self.url)


class ReleaseDownload251Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.opts = dict(
            repository="alexsosn/Pseudepigrapha-TF",
            release_tag="v1.0.0",
            asset_name="tf-1.0.zip",
            asset_sha256=hashlib.sha256(PAYLOAD).hexdigest(),
            asset_bytes=len(PAYLOAD),
            temporary_parent=self.root,
        )

    def download(self, opener, **overrides):
        return download_pinned_release(**{**self.opts, **overrides}, opener=opener)

    def test_bounded_https_fetch_yields_exact_verified_bytes_only_temporarily(self):
        opener = FakeOpener()
        with self.download(opener) as path:
            self.assertEqual(PAYLOAD, path.read_bytes())
            self.assertEqual(1, len(opener.requests))
            self.assertEqual(
                "https://github.com/alexsosn/Pseudepigrapha-TF/releases/download/v1.0.0/tf-1.0.zip",
                opener.requests[0][0],
            )
            self.assertGreater(opener.requests[0][1], 0)
            temporary = path
        self.assertFalse(temporary.exists())
        self.assertEqual([], list(self.root.iterdir()))

    def test_invalid_repository_tag_asset_url_and_pin_fail_before_network(self):
        invalid = (
            dict(repository="http://localhost/data"),
            dict(repository="github.com.evil/project"),
            dict(repository="x/../../other"),
            dict(release_tag="../latest"),
            dict(release_tag="latest"),
            dict(asset_name="../other.zip"),
            dict(asset_name="data.py"),
            dict(asset_name="http://example.invalid/file.zip"),
            dict(asset_sha256="deadbeef"),
            dict(asset_bytes=-1),
        )
        for bad in invalid:
            with self.subTest(bad=bad):
                opener = FakeOpener()
                with self.assertRaises(ValueError):
                    with self.download(opener, **bad):
                        self.fail("untrusted source reached staging")
                self.assertEqual([], opener.requests)
        self.assertEqual([], list(self.root.iterdir()))

    def test_redirect_handler_refuses_http_private_arbitrary_and_userinfo_targets(self):
        handler = SafeReleaseRedirect()
        request = Request("https://github.com/alexsosn/Pseudepigrapha-TF/releases/download/v1.0.0/tf-1.0.zip")
        for target in (
            "http://release-assets.githubusercontent.com/download",
            "https://127.0.0.1/download",
            "https://github.com.evil.invalid/download",
            "https://localhost/download",
            "https://user:pass@release-assets.githubusercontent.com/download",
            "https://release-assets.githubusercontent.com:444/download",
            "https://169.254.169.254/download",
        ):
            with self.subTest(target=target), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", Message(), target)
        allowed = handler.redirect_request(
            request, None, 302, "Found", Message(),
            "https://release-assets.githubusercontent.com/github-production-release-asset/123/fixture"
        )
        self.assertEqual("release-assets.githubusercontent.com", allowed.host)

    def test_mismatch_overflow_and_untrusted_final_url_clean_up(self):
        for overrides, opener in (
            (dict(asset_sha256="0" * 64), FakeOpener()),
            (dict(asset_bytes=len(PAYLOAD) + 1), FakeOpener()),
            (dict(asset_bytes=len(PAYLOAD) - 1), FakeOpener()),
            (dict(asset_bytes=len(PAYLOAD)), FakeOpener(url="https://example.invalid/asset")),
        ):
            with self.subTest(overrides=overrides, opener_url=opener.url):
                with self.assertRaises(ValueError):
                    with self.download(opener, **overrides):
                        self.fail("unverified bytes exposed")
                self.assertEqual([], list(self.root.iterdir()))
        with self.assertRaises(ValueError):
            with self.download(FakeOpener(), max_download_bytes=len(PAYLOAD) - 1):
                self.fail("over-budget archive exposed")

    def test_partial_network_failure_and_cancellation_clean_up(self):
        with self.assertRaises(RuntimeError):
            with self.download(FakeOpener(exc=OSError("network lost"))):
                self.fail("failed network returned output")
        op = OperationControl()
        op.cancel()
        with self.assertRaises(OperationCancelled):
            with self.download(FakeOpener(), operation=op):
                self.fail("cancelled transfer started")
        self.assertEqual([], list(self.root.iterdir()))

    def test_real_pinned_release_download_workflow_requires_offline_reopen(self):
        workflow = (
            ROOT / ".github/workflows/pseudepigrapha-release-download.yml"
        ).read_text(encoding="utf-8")
        for required in (
            "download_pinned_release",
            "PINNED_RELEASE_ASSETS",
            "tf-1.0.zip",
            "ReleaseSnapshots",
            "source_revision",
            "persist-credentials: false",
            "no corpus discovery",
        ):
            self.assertIn(required, workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("latest", workflow.lower())

    def test_monotonic_deadline_rejects_trickling_response(self):
        opener = FakeOpener()
        from agora_context_fabric import release_download
        operation = Mock()
        operation.remaining_acquisition_seconds.return_value = 100
        # Deadline 2s; the read completes after the deadline.
        with patch.object(release_download.time, "monotonic", side_effect=[0.0, 0.5, 3.0]):
            with self.assertRaisesRegex(TimeoutError, "deadline"):
                with self.download(opener, operation=operation, max_seconds=2):
                    self.fail("slow trickle bypassed wall deadline")
        self.assertEqual([], list(self.root.iterdir()))


if __name__ == "__main__":
    unittest.main()
