"""Issue #235: one reviewed plugin release SHA; verified receipt and upstream source remain exact."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import unittest

import yaml

from scripts.agora_install_materializer import (
    MaterializerRegistryError,
    load_registry,
    select_plugin,
)

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = (
    ".github/workflows/coptic-registered-full-source.yml",
    "tests/test_copticscriptorium_materializer_registry.py",
    "tests/test_issue214_coptic_full_registered.py",
    "tests/live_issue214_full_coptic.py",
)


class SingleSourceCopticReleasePinRed235(unittest.TestCase):
    @staticmethod
    def plugin():
        return select_plugin(load_registry(), "copticscriptorium-tf")

    def test_no_live_expected_release_sha_literals_outside_registry(self):
        plugin = self.plugin()
        pin = plugin["ref"]
        self.assertRegex(pin, r"^[0-9a-f]{40}$")
        self.assertEqual(plugin["repository"], "alexsosn/CopticScriptorium-TF")
        for path in ACTIVE:
            with self.subTest(path=path):
                self.assertNotIn(
                    pin,
                    (ROOT / path).read_text(encoding="utf-8"),
                    "duplicate live SHA defeats canonical one-pin update",
                )

    def test_registry_ref_is_never_mutable_or_short(self):
        for invalid in ("main", "v0.1.0", "a" * 39, "a" * 41, "A" * 40):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as tmp:
                doc = deepcopy(load_registry())
                plugin = select_plugin(doc, "copticscriptorium-tf")
                plugin["ref"] = invalid
                path = Path(tmp) / "registry.yaml"
                path.write_text(yaml.safe_dump(doc), encoding="utf-8")
                with self.assertRaises(MaterializerRegistryError):
                    load_registry(path)

    def test_real_acceptance_uses_registry_sha_for_receipt_and_preserves_distinct_tt_pin(self):
        verifier = (ROOT / "tests/live_issue214_full_coptic.py").read_text()
        workflow = (ROOT / ".github/workflows/coptic-registered-full-source.yml").read_text()
        self.assertIn('receipt["plugin"]["commit"] == plugin["ref"]', verifier)
        self.assertIn('assert plugin["repository"] == "alexsosn/CopticScriptorium-TF"', workflow)
        self.assertIn('re.fullmatch(r"[0-9a-f]{40}", plugin["ref"])', workflow)
        self.assertIn('source["requested_ref"] == UPSTREAM_COMMIT', verifier)
        self.assertIn('source["resolved_commit"] == UPSTREAM_COMMIT', verifier)
        self.assertIn('"3ac067f1709a0012daf39ea8da2fac79980176a5"', verifier)
        self.assertIn('len(receipt["execution_identity_sha256"]) == 64', verifier)

    def test_exact_installer_commit_and_receipt_guards_are_still_present(self):
        installer = (ROOT / "scripts/agora_install_materializer.py").read_text()
        self.assertIn('resolved != plugin["ref"]', installer)
        self.assertIn('receipt["plugin"]["commit"] == plugin["ref"]', installer)
        self.assertIn("execution_identity_sha256", installer)


if __name__ == "__main__":
    unittest.main()
