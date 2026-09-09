from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from scripts import agora_managed_artifacts as managed


ARTIFACT_ID = "art-" + "a" * 32
HEX64 = "b" * 64
REF = "c" * 40


def _api(name: str):
    value = getattr(managed, name, None)
    if value is None:
        raise AssertionError(f"RED2: {name} is missing")
    return value


def _payload(root: Path) -> Path:
    payload = root / "payload"
    payload.mkdir()
    (payload / "otype.tf").write_text("@node\n", encoding="utf-8")
    (payload / "oslots.tf").write_text("@edge\n", encoding="utf-8")
    (payload / "agora-materialization.json").write_text(
        json.dumps({"schema_version": 1, "plugin": {"id": "fixture"}}),
        encoding="utf-8",
    )
    empty = payload / "empty"
    empty.mkdir()
    return payload


def _manifest(payload: Path):
    return _api("build_payload_manifest")(
        payload,
        required_paths=("otype.tf", "oslots.tf"),
    )


def _receipt(artifact_id: str, manifest: dict):
    return _api("build_artifact_receipt")(
        artifact_id=artifact_id,
        disposition="one-shot",
        request_key=None,
        plugin={
            "id": "fixture",
            "repository": "example/fixture",
            "ref": REF,
            "version": "1.0.0",
        },
        materializer_id="fixture-to-tf",
        execution_identity_sha256=HEX64,
        cacheability={"mode": "unknown", "reuse_allowed": False},
        source={"type": "directory", "tree_sha256": HEX64, "resolved_commit": None},
        manifest_sha256=HEX64,
        materializer_contract_sha256=HEX64,
        output_format="text-fabric",
        required_paths=("otype.tf", "oslots.tf"),
        payload_manifest=manifest,
        sandbox={"policy": "required", "backend": "synthetic"},
    )


class ManagedArtifactPayloadRed2Tests(unittest.TestCase):
    def test_payload_manifest_is_complete_and_includes_host_provenance_and_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = _payload(Path(tmp))
            manifest = _manifest(payload)

        by_path = {entry["path"]: entry for entry in manifest["entries"]}
        self.assertEqual(
            set(by_path),
            {"otype.tf", "oslots.tf", "agora-materialization.json", "empty"},
        )
        self.assertEqual(by_path["empty"]["kind"], "directory")
        self.assertRegex(by_path["otype.tf"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(manifest["digest_sha256"], r"^[0-9a-f]{64}$")

    def test_payload_manifest_rejects_symlink_and_materializer_owned_cfm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = _payload(root)
            target = payload / "otype.tf"
            link = payload / "linked.tf"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, r"symlink|link"):
                _manifest(payload)

        with tempfile.TemporaryDirectory() as tmp:
            payload = _payload(Path(tmp))
            (payload / ".cfm").mkdir()
            (payload / ".cfm" / "compiled.bin").write_bytes(b"forbidden")
            with self.assertRaisesRegex(ValueError, r"\.cfm|reserved"):
                _manifest(payload)

    def test_validation_rejects_modified_missing_kind_changed_and_unknown_payload_entries(self):
        validator = _api("validate_payload_manifest")
        mutations = ("modified", "missing", "kind", "unknown")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                payload = _payload(Path(tmp))
                manifest = _manifest(payload)
                if mutation == "modified":
                    (payload / "otype.tf").write_text("tampered\n", encoding="utf-8")
                elif mutation == "missing":
                    (payload / "oslots.tf").unlink()
                elif mutation == "kind":
                    (payload / "otype.tf").unlink()
                    (payload / "otype.tf").mkdir()
                else:
                    (payload / "extra.txt").write_text("smuggled\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, r"integrity|manifest|payload|required|unexpected|kind"):
                    validator(payload, manifest, required_paths=("otype.tf", "oslots.tf"))

    def test_post_publication_cfm_is_ignored_only_as_contained_non_symlink_consumer_state(self):
        validator = _api("validate_payload_manifest")
        with tempfile.TemporaryDirectory() as tmp:
            payload = _payload(Path(tmp))
            manifest = _manifest(payload)
            before = manifest["digest_sha256"]
            cfm = payload / ".cfm"
            cfm.mkdir()
            (cfm / "compiled.bin").write_bytes(b"compiled")
            validated = validator(payload, manifest, required_paths=("otype.tf", "oslots.tf"))
            self.assertEqual(validated, before)
            (cfm / "compiled.bin").write_bytes(b"rebuilt")
            self.assertEqual(
                validator(payload, manifest, required_paths=("otype.tf", "oslots.tf")),
                before,
            )

    def test_cfm_cannot_mask_tamper_in_immutable_payload(self):
        validator = _api("validate_payload_manifest")
        with tempfile.TemporaryDirectory() as tmp:
            payload = _payload(Path(tmp))
            manifest = _manifest(payload)
            (payload / ".cfm").mkdir()
            (payload / ".cfm" / "compiled.bin").write_bytes(b"compiled")
            (payload / "otype.tf").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"integrity|payload|manifest"):
                validator(payload, manifest, required_paths=("otype.tf", "oslots.tf"))


class ManagedArtifactReceiptAndLayoutRed2Tests(unittest.TestCase):
    def test_receipt_binds_authority_and_never_leaks_local_paths(self):
        validator = _api("validate_artifact_receipt")
        with tempfile.TemporaryDirectory() as tmp:
            payload = _payload(Path(tmp))
            manifest = _manifest(payload)
            receipt = _receipt(ARTIFACT_ID, manifest)
            validator(receipt, artifact_id=ARTIFACT_ID)

        self.assertEqual(receipt["artifact_id"], ARTIFACT_ID)
        self.assertEqual(receipt["disposition"], "one-shot")
        self.assertIsNone(receipt.get("request_key"))
        self.assertEqual(receipt["redistribution"], "local-only")
        self.assertEqual(receipt["plugin"]["ref"], REF)
        self.assertEqual(receipt["execution_identity_sha256"], HEX64)
        rendered = json.dumps(receipt, sort_keys=True)
        self.assertNotIn("/tmp/", rendered)
        self.assertNotIn("\\Users\\", rendered)
        self.assertNotIn("payload", receipt.get("source", {}).get("type", ""))

    def test_reusable_receipt_requires_request_key_and_one_shot_forbids_it(self):
        builder = _api("build_artifact_receipt")
        with tempfile.TemporaryDirectory() as tmp:
            manifest = _manifest(_payload(Path(tmp)))
            kwargs = dict(
                artifact_id=ARTIFACT_ID,
                plugin={"id": "fixture", "repository": "example/fixture", "ref": REF, "version": "1.0.0"},
                materializer_id="fixture-to-tf",
                execution_identity_sha256=HEX64,
                cacheability={"mode": "reusable", "reuse_allowed": True, "attestation_sha256": HEX64},
                source={"type": "directory", "tree_sha256": HEX64, "resolved_commit": None},
                manifest_sha256=HEX64,
                materializer_contract_sha256=HEX64,
                output_format="text-fabric",
                required_paths=("otype.tf", "oslots.tf"),
                payload_manifest=manifest,
                sandbox={"policy": "required", "backend": "synthetic"},
            )
            with self.assertRaisesRegex(ValueError, r"request|key|reusable"):
                builder(disposition="reusable", request_key=None, **kwargs)
            with self.assertRaisesRegex(ValueError, r"request|key|one-shot"):
                builder(disposition="one-shot", request_key=HEX64, **kwargs)

    def test_store_layout_is_contained_receipt_outside_payload_and_private_on_posix(self):
        Store = _api("ManagedArtifactStore")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            store = Store(root)
            paths = store.paths(ARTIFACT_ID)
            resolved_root = root.resolve()
            for value in (paths.object, paths.payload, paths.receipt, paths.staging):
                self.assertTrue(value.resolve(strict=False).is_relative_to(resolved_root))
            self.assertTrue(paths.receipt.parent == paths.object)
            self.assertFalse(paths.receipt.is_relative_to(paths.payload))
            if os.name != "nt":
                store.ensure_private_root()
                mode = stat.S_IMODE(root.stat().st_mode)
                self.assertEqual(mode & 0o077, 0)

    def test_store_rejects_symlinked_object_path_before_resolution(self):
        Store = _api("ManagedArtifactStore")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "managed"
            root.mkdir()
            outside = Path(tmp) / "outside"
            outside.mkdir()
            objects = root / "objects"
            objects.mkdir()
            link = objects / ARTIFACT_ID
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            store = Store(root)
            with self.assertRaisesRegex(ValueError, r"symlink|contain|escape"):
                store.paths(ARTIFACT_ID, require_safe_existing=True)


if __name__ == "__main__":
    unittest.main()
