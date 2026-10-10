"""#135 RED3d: bundled resolver must be constructed internally, never injected.

The existing low-level lease helper intentionally accepts fake resolvers for
tests. This new gate gives it a facade with a fixed Agora-bundled catalog.
"""
from __future__ import annotations

import inspect
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import agora_compose_feature_module as compose


ROOT = Path(__file__).resolve().parents[1]


class TrustedBundledResolverRed3dTests(unittest.TestCase):
    def test_internal_resolver_uses_canonical_immutable_cuc_catalog_not_an_injected_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            factory = getattr(compose, "_bundled_context_fabric_resolver", None)
            self.assertTrue(callable(factory), "RED3d: bundled resolver factory missing")
            resolver = factory(cache_dir=cache)
            self.assertEqual(resolver.catalog.get("cuc").kind, "corpus")
            self.assertEqual(resolver.catalog.get("cuc").ref, "0408967b1808c1f22c69e299d302b1e7b5e26354")
            self.assertEqual(resolver.catalog.get("cuc").tf_path, "tf/0.2.8")
            self.assertEqual(resolver.store.cache_dir, cache.resolve())

    def test_facade_signature_exposes_no_resolver_catalog_plugin_root_or_parent_path(self):
        fn = getattr(compose, "materialize_registered_managed_feature_module", None)
        self.assertTrue(callable(fn), "RED3d: trustworthy parent orchestration facade missing")
        signature = inspect.signature(fn)
        for forbidden in ("resolver", "catalog", "plugin_root", "parent_path", "trusted"):
            self.assertNotIn(forbidden, signature.parameters)
        self.assertNotIn(inspect.Parameter.VAR_KEYWORD,
                         {p.kind for p in signature.parameters.values()})

    def test_facade_rejects_forged_resolver_argument_before_build_or_execution(self):
        fn = getattr(compose, "materialize_registered_managed_feature_module", None)
        self.assertTrue(callable(fn), "RED3d: facade missing")
        with (
            mock.patch.object(compose, "_bundled_context_fabric_resolver") as build,
            mock.patch.object(compose, "materialize_managed_feature_module") as run,
        ):
            with self.assertRaises(TypeError):
                fn(
                    plugin_id="test", materializer_id="cuc-burns",
                    source=Path("fake"), output=Path("module"),
                    resolver=mock.Mock(),
                )
            build.assert_not_called()
            run.assert_not_called()

    def test_facade_construction_then_delegation_preserves_exact_run_constraints(self):
        fn = getattr(compose, "materialize_registered_managed_feature_module", None)
        self.assertTrue(callable(fn), "RED3d: facade missing")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = object()
            output = root / "produced-module"
            with (
                mock.patch.object(compose, "_bundled_context_fabric_resolver",
                                  return_value=parent) as build,
                mock.patch.object(compose, "materialize_managed_feature_module",
                                  return_value=output) as run,
            ):
                actual = fn(
                    plugin_id="fixture", materializer_id="cuc-burns",
                    source=root / "source", output=output,
                    requested_version="0.2.8",
                    cache_dir=root / "cache", install_root=root / "install",
                    registry_path=root / "registry.yaml",
                )
            self.assertEqual(actual, output)
            build.assert_called_once_with(cache_dir=root / "cache")
            run.assert_called_once_with(
                resolver=parent, plugin_id="fixture", materializer_id="cuc-burns",
                source=root / "source", output=output,
                requested_version="0.2.8", install_root=root / "install",
                registry_path=root / "registry.yaml",
            )


if __name__ == "__main__":
    unittest.main()
