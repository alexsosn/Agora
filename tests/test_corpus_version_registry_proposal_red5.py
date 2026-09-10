from __future__ import annotations

import copy
import unittest

import yaml

from scripts import check_corpus_versions as versions


OLD_REF = "1" * 40
NEW_REF = "2" * 40


def _apply():
    value = getattr(versions, "apply_promotions_to_text", None)
    if not callable(value):
        raise AssertionError("RED5: apply_promotions_to_text is missing")
    return value


def _text() -> str:
    return f"""schema_version: 1
resources:
- id: fixture
  name: Fixture corpus
  plugin: context-fabric
  provider: context-fabric
  kind: corpus
  languages: [hebrew]
  disciplines: [biblical-studies]
  description: Keep this exact comment-sensitive text. # untouched
  upstream:
    repository: example/corpus
    ref: {OLD_REF}
    tf_path: tf/1.0.0
  acquisition: {{strategy: repository, lazy: true}}
  licenses:
    data: CC-BY-4.0
    redistribution: permitted
    evidence: {{status: resolved, checked_at: '2026-09-01', sources: [https://example.invalid/license]}}
  verification:
    status: verified
    evidence:
    - check_id: resource-load/fixture
  version_tracking:
    discovery: {{mode: github-releases, channel: stable}}
    dataset: {{mode: release-version-match, root: tf, ordering: semver}}
    promotion: {{mode: proposal}}
    accepted:
      publication_version: 1.0.0
      signal: v1.0.0
      source_revision: {OLD_REF}
      tf_path: tf/1.0.0
"""


def _promotion() -> dict:
    return {
        "resource_id": "fixture",
        "previous": {
            "publication_version": "1.0.0",
            "signal": "v1.0.0",
            "source_revision": OLD_REF,
            "tf_path": "tf/1.0.0",
        },
        "candidate": {
            "publication_version": "1.1.0",
            "signal": "v1.1.0",
            "source_revision": NEW_REF,
            "tf_path": "tf/1.1.0",
        },
        "verification_status": "community",
    }


class CorpusVersionRegistryProposalRed5Tests(unittest.TestCase):
    def test_promotion_atomically_updates_runtime_tracking_and_invalidates_old_verification(self):
        original = _text()
        parsed = yaml.safe_load(original)
        changed = _apply()(original, parsed, [_promotion()])
        updated = yaml.safe_load(changed)["resources"][0]

        self.assertEqual(updated["upstream"]["ref"], NEW_REF)
        self.assertEqual(updated["upstream"]["tf_path"], "tf/1.1.0")
        self.assertEqual(
            updated["version_tracking"]["accepted"],
            {
                "publication_version": "1.1.0",
                "signal": "v1.1.0",
                "source_revision": NEW_REF,
                "tf_path": "tf/1.1.0",
            },
        )
        self.assertEqual(updated["verification"]["status"], "community")
        self.assertNotIn("evidence", updated["verification"])

    def test_patch_preserves_unowned_bytes(self):
        original = _text()
        parsed = yaml.safe_load(original)
        changed = _apply()(original, parsed, [_promotion()])

        before_prefix = original.split("  upstream:", 1)[0]
        after_prefix = changed.split("  upstream:", 1)[0]
        self.assertEqual(after_prefix, before_prefix)
        self.assertIn("description: Keep this exact comment-sensitive text. # untouched\n", changed)
        self.assertIn("evidence: {status: resolved, checked_at: '2026-09-01', sources: [https://example.invalid/license]}\n", changed)

    def test_noop_is_byte_identical(self):
        original = _text()
        parsed = yaml.safe_load(original)
        self.assertEqual(_apply()(original, parsed, []), original)

    def test_stale_previous_state_fails_closed(self):
        original = _text()
        parsed = yaml.safe_load(original)
        stale = _promotion()
        stale["previous"] = copy.deepcopy(stale["previous"])
        stale["previous"]["source_revision"] = "f" * 40
        with self.assertRaisesRegex(Exception, r"(?i)changed|stale|expected|revision|state"):
            _apply()(original, parsed, [stale])

    def test_multiple_promotions_are_deterministic_independent_of_input_order(self):
        original = _text().replace(
            "\n- id: fixture\n",
            "\n- id: second\n"
            "  name: Second corpus\n"
            "  plugin: context-fabric\n"
            "  provider: context-fabric\n"
            "  kind: corpus\n"
            "  languages: [hebrew]\n"
            "  disciplines: [biblical-studies]\n"
            "  description: Second.\n"
            f"  upstream: {{repository: example/second, ref: {'3' * 40}, tf_path: tf/1.0.0}}\n"
            "  acquisition: {strategy: repository, lazy: true}\n"
            "  licenses:\n"
            "    data: CC-BY-4.0\n"
            "    redistribution: permitted\n"
            "    evidence: {status: resolved, checked_at: '2026-09-01', sources: [https://example.invalid/license]}\n"
            "  verification: {status: community}\n"
            "  version_tracking:\n"
            "    discovery: {mode: github-releases, channel: stable}\n"
            "    dataset: {mode: release-version-match, root: tf, ordering: semver}\n"
            "    promotion: {mode: proposal}\n"
            "    accepted:\n"
            "      publication_version: 1.0.0\n"
            "      signal: v1.0.0\n"
            f"      source_revision: {'3' * 40}\n"
            "      tf_path: tf/1.0.0\n"
            "- id: fixture\n",
        )
        parsed = yaml.safe_load(original)
        second = {
            "resource_id": "second",
            "previous": {
                "publication_version": "1.0.0",
                "signal": "v1.0.0",
                "source_revision": "3" * 40,
                "tf_path": "tf/1.0.0",
            },
            "candidate": {
                "publication_version": "1.2.0",
                "signal": "v1.2.0",
                "source_revision": "4" * 40,
                "tf_path": "tf/1.2.0",
            },
            "verification_status": "community",
        }
        first = _apply()(original, parsed, [_promotion(), second])
        second_order = _apply()(original, parsed, [second, _promotion()])
        self.assertEqual(first, second_order)


if __name__ == "__main__":
    unittest.main()
