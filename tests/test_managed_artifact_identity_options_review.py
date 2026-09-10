from __future__ import annotations

import unittest

from scripts import agora_managed_artifacts as managed
from test_managed_artifact_identity import _request_kwargs


class ManagedArtifactOptionsIdentityReviewTests(unittest.TestCase):
    """Adversarial RED1c: request options must be one canonical JSON object."""

    def build(self, options):
        kwargs = _request_kwargs()
        kwargs["options"] = options
        return managed.build_reusable_request_identity(**kwargs)

    def test_top_level_options_must_be_an_object(self):
        for value in ([], ["alpha"], "alpha", 1, True, None):
            with self.subTest(value=value):
                with self.assertRaisesRegex((TypeError, ValueError), r"options|object|mapping"):
                    self.build(value)

    def test_non_string_mapping_keys_are_rejected_before_json_key_coercion(self):
        # json.dumps({1: "x"}) and json.dumps({"1": "x"}) both produce a
        # string-keyed JSON object. Accepting the Python integer key would let
        # semantically distinct caller inputs collapse onto one reusable key.
        with self.assertRaisesRegex((TypeError, ValueError), r"options|key|string"):
            self.build({1: "integer-key"})

    def test_nested_non_string_mapping_keys_are_rejected(self):
        with self.assertRaisesRegex((TypeError, ValueError), r"options|key|string"):
            self.build({"nested": {1: "integer-key"}})

    def test_python_tuple_is_not_silently_coerced_to_json_array(self):
        with self.assertRaisesRegex((TypeError, ValueError), r"options|JSON|tuple|array"):
            self.build({"items": ("a", "b")})

    def test_nested_json_objects_and_arrays_remain_valid(self):
        identity = self.build(
            {"alpha": 1, "nested": {"enabled": True, "items": ["a", None, 2.5]}}
        )
        self.assertRegex(identity.key, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
