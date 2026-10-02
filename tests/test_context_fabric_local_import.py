from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/context-fabric/src'))
from agora_context_fabric.catalog import Catalog, ResourceSpec
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.local_import import LocalImports, LocalCatalog, _digest
from agora_context_fabric.resolver import ContextFabricResolver
from agora_context_fabric.service import ContextFabricService


def corpus(path):
    path.mkdir()
    (path / 'otype.tf').write_text('@node\n@valueType=str\n\n1-2\tword\n3\tdocument\n', encoding='utf-8')
    (path / 'oslots.tf').write_text('@edge\n\n3\t1-2\n', encoding='utf-8')
    (path / 'otext.tf').write_text('@config\n@sectionTypes=document\n@sectionFeatures=title\n@fmt:text-orig-full={norm} \n\n', encoding='utf-8')
    (path / 'norm.tf').write_text('@node\n@valueType=str\n\n1\tⲡⲉ\n2\tⲣⲱⲙⲉ\n', encoding='utf-8')
    (path / 'title.tf').write_text('@node\n@valueType=str\n\n3\tsample\n', encoding='utf-8')


class LocalImportFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = GitStore(self.root / 'cache', min_free_bytes=0)
        self.local = LocalImports(self.store)
        self.catalog = LocalCatalog(Catalog([]), self.local)
        self.resolver = ContextFabricResolver(self.catalog, self.store, local_imports=self.local)
        self.source = self.root / 'source'
        corpus(self.source)

    def install(self, **kwargs):
        return self.local.install(self.source, name='Coptic sample', **kwargs)


class LocalImportTests(LocalImportFixture, unittest.TestCase):
    def test_import_discover_prepare_restart_and_source_independence(self):
        record = self.install()
        rid = record['id']
        self.assertEqual(self.catalog.search('Coptic')[0].id, rid)
        prepared = self.resolver.prepare_with_modules(rid)
        self.assertEqual(prepared.source_revision, record['source_revision'])
        self.assertNotEqual(prepared.path, self.source)
        (self.source / 'norm.tf').write_text('changed')
        self.assertIn('ⲣⲱⲙⲉ', (prepared.path / 'norm.tf').read_text())
        restarted = LocalCatalog(Catalog([]), LocalImports(self.store))
        self.assertEqual(restarted.get(rid).acquisition_strategy, 'user-local')
        result = ContextFabricService(self.catalog, self.resolver, object()).remove_cached(rid)
        self.assertEqual(result['removed_entries'], 1)
        self.assertEqual(restarted.search(), [])

    def test_module_exact_parent_and_overlay(self):
        parent = self.install()
        module = self.root / 'module'
        module.mkdir()
        (module / 'lemma.tf').write_text('@node\n@valueType=str\n\n1\tⲡⲉ\n', encoding='utf-8')
        item = self.local.install(module, name='Local lemma', parent=parent['id'],
                                  parent_version='local', parent_revision=parent['source_revision'])
        prepared = self.resolver.prepare_with_modules(parent['id'], modules=[item['id']])
        self.assertTrue((prepared.path / 'lemma.tf').is_file())
        bad = self.local.install(module, name='Wrong base', parent=parent['id'],
                                 parent_version='local', parent_revision='a' * 64)
        with self.assertRaisesRegex(ValueError, 'requires parent'):
            self.resolver.prepare_with_modules(parent['id'], modules=[bad['id']])

    def test_reject_symlink_missing_warp_module_warp_and_byte_limit(self):
        (self.source / 'norm.tf').unlink()
        (self.source / 'norm.tf').symlink_to(self.source / 'otype.tf')
        with self.assertRaisesRegex(ValueError, 'regular|symlink'):
            self.install()
        (self.source / 'norm.tf').unlink()
        (self.source / 'oslots.tf').unlink()
        with self.assertRaisesRegex(ValueError, 'oslots'):
            self.install()
        with self.assertRaisesRegex(ValueError, 'replace|warp'):
            self.install(parent='bhsa', parent_version='2021', parent_revision='a' * 40)
        (self.source / 'oslots.tf').write_text('@edge\n\n3\t1-2\n')
        with self.assertRaisesRegex(ValueError, 'byte|size'):
            self.install(max_bytes=1)
        self.assertEqual(self.catalog.search(), [])

    def test_accepts_text_fabric_at_feature_names(self):
        (self.source / 'book@en.tf').write_text(
            '@node\n@valueType=str\n\n3\tSample\n', encoding='utf-8'
        )
        (self.source / 'omap@2017-2021.tf').write_text(
            '@edge\n\n1\t2\n', encoding='utf-8'
        )
        record = self.install()
        prepared = self.resolver.prepare_with_modules(record['id'])
        self.assertTrue((prepared.path / 'book@en.tf').is_file())
        self.assertTrue((prepared.path / 'omap@2017-2021.tf').is_file())

    def test_source_revision_is_stable_for_identical_payloads(self):
        first = self.local.install(self.source, name='First label', version='one')
        second = self.local.install(self.source, name='Different label', version='two')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['source_revision'], second['source_revision'])
        (self.source / 'norm.tf').write_text(
            '@node\n@valueType=str\n\n1\tchanged\n2\tⲣⲱⲙⲉ\n', encoding='utf-8'
        )
        changed = self.local.install(self.source, name='First label', version='one')
        self.assertNotEqual(first['source_revision'], changed['source_revision'])

    def test_ignore_compiled_and_code_and_detect_mutation(self):
        (self.source / '.tf').mkdir()
        (self.source / '.tf/unsafe.pickle').write_bytes(b'not data')
        (self.source / 'app.py').write_text('raise Exception()')
        record = self.install()
        prepared = self.resolver.prepare_with_modules(record['id'])
        self.assertFalse((prepared.path / '.tf').exists())
        self.assertFalse((prepared.path / 'app.py').exists())
        (prepared.path / 'norm.tf').write_text('@node\n\n1\tbad\n')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.resolver.prepare_with_modules(record['id'])


class LocalImportRecoveryTests(LocalImportFixture, unittest.TestCase):
    def test_corrupt_receipt_does_not_poison_catalog_and_can_be_removed(self):
        canonical = ResourceSpec(
            id='canonical-fixture',
            name='Canonical fixture',
            plugin='context-fabric',
            provider='fixture',
            kind='corpus',
            repository='example/canonical',
            languages=(),
            disciplines=(),
            tf_path='tf/1',
        )
        catalog = LocalCatalog(Catalog([canonical]), self.local)
        resolver = ContextFabricResolver(catalog, self.store, local_imports=self.local)
        service = ContextFabricService(catalog, resolver, object())
        record = self.install()
        receipt = (
            self.local._path(record['id'], record['source_revision'], 'corpus')
            / '.agora-local.json'
        )
        receipt.write_text('{broken', encoding='utf-8')

        with self.assertWarnsRegex(RuntimeWarning, 'invalid local import receipt'):
            self.assertEqual(catalog.get('canonical-fixture').id, 'canonical-fixture')
        with self.assertWarnsRegex(RuntimeWarning, 'invalid local import receipt'):
            result = service.remove_cached(record['id'])
        self.assertTrue(result['complete'])
        self.assertEqual(result['removed_entries'], 1)


    def test_hash_consistent_malformed_descriptor_is_quarantined_from_catalog(self):
        canonical = ResourceSpec(
            id='canonical-fixture',
            name='Canonical fixture',
            plugin='context-fabric',
            provider='fixture',
            kind='corpus',
            repository='example/canonical',
            languages=(),
            disciplines=(),
            tf_path='tf/1',
        )
        catalog = LocalCatalog(Catalog([canonical]), self.local)
        record = self.install()
        receipt = (
            self.local._path(record['id'], record['source_revision'], 'corpus')
            / '.agora-local.json'
        )
        document = json.loads(receipt.read_text(encoding='utf-8'))
        document['descriptor']['name'] = 42
        document['receipt_sha256'] = _digest(
            {key: value for key, value in document.items() if key != 'receipt_sha256'}
        )
        receipt.write_text(json.dumps(document, sort_keys=True), encoding='utf-8')

        with self.assertWarnsRegex(RuntimeWarning, 'invalid local import receipt'):
            self.assertEqual([item.id for item in catalog.search()], ['canonical-fixture'])

    def test_receipt_metadata_corruption_is_detected_separately_from_payload_identity(self):
        record = self.install()
        receipt = (
            self.local._path(record['id'], record['source_revision'], 'corpus')
            / '.agora-local.json'
        )
        document = json.loads(receipt.read_text(encoding='utf-8'))
        document['descriptor']['name'] = 'tampered label'
        receipt.write_text(json.dumps(document, sort_keys=True), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'receipt integrity'):
            self.local._read(receipt)

class LocalImportLifecycleTests(LocalImportFixture, unittest.TestCase):
    def test_mid_copy_cancellation_and_changed_source_clean_staging(self):
        from agora_context_fabric.operation import OperationControl, OperationCancelled
        from unittest.mock import patch

        class CancelDuringCopy(OperationControl):
            calls = 0
            def remaining_acquisition_seconds(self):
                self.calls += 1
                if self.calls == 4:
                    self.cancel()
                return super().remaining_acquisition_seconds()

        with self.assertRaises(OperationCancelled):
            self.install(operation=CancelDuringCopy())
        original = self.local._files
        calls = 0
        def changed_files(source, kind):
            nonlocal calls
            calls += 1
            if calls == 2:
                (source / 'norm.tf').write_text('@node\n\n1\tchanged\n')
            return original(source, kind)
        with patch.object(self.local, '_files', side_effect=changed_files):
            with self.assertRaisesRegex(ValueError, 'changed during import'):
                self.install()
        self.assertEqual(self.local.records(), [])
        self.assertEqual(list(self.store.tmp_dir.glob('local-import-*')), [])

    def test_cancellation_timeout_free_space_and_invalid_utf8_leave_no_import(self):
        from agora_context_fabric.operation import OperationControl, OperationCancelled, AcquisitionTimeout
        from unittest.mock import patch
        control = OperationControl()
        control.cancel()
        with self.assertRaises(OperationCancelled):
            self.install(operation=control)
        with patch('agora_context_fabric.operation.time.monotonic', return_value=1000):
            control = OperationControl(started_monotonic=0, acquisition_timeout_seconds=1)
            with self.assertRaises(AcquisitionTimeout):
                self.install(operation=control)
        self.store.min_free_bytes = 2**63
        with self.assertRaisesRegex(ValueError, 'free-space'):
            self.install()
        self.store.min_free_bytes = 0
        (self.source / 'norm.tf').write_bytes(b'@node\n\n1\t\xff')
        with self.assertRaises(UnicodeDecodeError):
            self.install()
        self.assertEqual(self.local.records(), [])
        self.assertEqual(list(self.store.tmp_dir.glob('local-import-*')), [])

    def test_cache_index_failure_rolls_back_published_snapshot(self):
        from unittest.mock import patch

        with patch.object(self.store, 'touch_cache_object', side_effect=OSError('index failed')):
            with self.assertRaisesRegex(OSError, 'index failed'):
                self.install()
        self.assertEqual(self.local.records(), [])
        self.assertEqual(list(self.store.snapshots_dir.glob('local-*')), [])

    def test_loaded_import_is_protected_from_removal(self):
        class Loader:
            def load(self, path, **kwargs):
                return {'name': kwargs['name']}
            def unload(self, name):
                pass
        record = self.install()
        service = ContextFabricService(self.catalog, self.resolver, Loader())
        loaded = service.load(record['id'], source_mode='offline')
        self.assertEqual(loaded['source_resolution'], 'user-local')
        self.assertFalse(service.remove_cached(record['id'])['complete'])
        service.unload(loaded['logical_name'])
        self.assertTrue(service.remove_cached(record['id'])['complete'])

    def test_explicit_selection_and_require_fresh_fail(self):
        record = self.install()
        service = ContextFabricService(self.catalog, self.resolver, object())
        for kwargs in ({'version': 'wrong'}, {'source_revision': 'a' * 64},
                       {'member_id': 'wrong'}, {'source_mode': 'require-fresh'}):
            with self.assertRaises(ValueError):
                service.prepare(record['id'], **kwargs)
        selected = service.prepare(record['id'], source_revision=record['source_revision'])
        self.assertEqual(selected['source_resolution'], 'user-local')
        self.assertTrue(selected['source_revision_verified'])

    def test_concurrent_imports_publish_complete_independent_snapshots(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            items = list(pool.map(lambda _: self.install(), range(2)))
        self.assertNotEqual(items[0]['id'], items[1]['id'])
        self.assertEqual(len(self.local.records()), 2)
        for item in items:
            self.resolver.prepare_with_modules(item['id'])


if __name__ == '__main__':
    unittest.main()
