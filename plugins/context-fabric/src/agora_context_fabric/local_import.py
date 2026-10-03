"""Data-only local TF acquisition; querying remains owned by cfabric-mcp."""
from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
import warnings
from pathlib import Path

from .catalog import Catalog, ResourceSpec
from .operation import OperationControl, current_operation
from .resolver import PreparedCorpus, PreparedFeatureModule

_ID = re.compile(r'local-[0-9a-f]{32}\Z')
_REVISION = re.compile(r'[0-9a-f]{40}|[0-9a-f]{64}')
_FEATURE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*\.tf\Z')
_RECEIPT = '.agora-local.json'
_REQUIRED = {'otype.tf', 'oslots.tf', 'otext.tf'}
_MAX_FILES = 2048
_DEFAULT_MAX_BYTES = 2 * 1024**3
_RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                   *(f'LPT{i}' for i in range(1, 10))}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':')).encode()).hexdigest()


class LocalImports:
    def __init__(self, store):
        self.store = store

    def _path(self, resource_id, revision, kind):
        if not _ID.fullmatch(resource_id) or not re.fullmatch(r'[0-9a-f]{64}', revision):
            raise ValueError('invalid local resource identity')
        namespace = 'corpora' if kind == 'corpus' else 'feature-modules'
        if kind not in {'corpus', 'feature-module'}:
            raise ValueError('invalid local resource kind')
        path = self.store.snapshots_dir / resource_id / revision / namespace / '__root__'
        # Local receipts never get to choose a filesystem path.
        if path.resolve() != path.absolute():
            raise ValueError('local import path contains a symlink')
        return path

    @staticmethod
    def _files(source, kind):
        files = []
        for path in source.iterdir():
            if path.name == '.tf' and path.is_dir() and not path.is_symlink():
                continue
            if not path.name.endswith('.tf'):
                continue
            if (not _FEATURE.fullmatch(path.name)
                    or path.name.split('.')[0].upper() in _RESERVED_NAMES
                    or not stat.S_ISREG(path.lstat().st_mode)):
                raise ValueError('TF features must be regular non-symlink files with portable names')
            files.append(path)
            if len(files) > _MAX_FILES:
                raise ValueError('local import exceeds feature file count limit')
        names = {path.name for path in files}
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError('TF feature names collide on case-insensitive filesystems')
        if kind == 'corpus' and not _REQUIRED.issubset(names):
            raise ValueError('incomplete TF corpus; missing ' + ', '.join(sorted(_REQUIRED - names)))
        if kind == 'feature-module' and names & _REQUIRED:
            raise ValueError('feature module cannot replace parent warp/config files')
        if not files:
            raise ValueError('local TF directory contains no feature files')
        return sorted(files)

    def install(self, source, *, name, version='local', parent=None,
                parent_version=None, parent_revision=None, max_bytes=_DEFAULT_MAX_BYTES,
                operation=None):
        operation = operation or OperationControl()
        operation.stage('acquiring/materializing')
        operation.remaining_acquisition_seconds()
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ValueError('max_bytes must be a positive integer')
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError('name must be non-empty and at most 200 characters')
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}', version):
            raise ValueError('version must be a portable non-empty label')
        kind = 'feature-module' if parent is not None else 'corpus'
        if parent is not None:
            if not isinstance(parent, str) or not parent:
                raise ValueError('parent resource ID is required')
            if not parent_version or not parent_revision or not _REVISION.fullmatch(parent_revision):
                raise ValueError('modules require parent_version and exact parent_revision')
        elif parent_version is not None or parent_revision is not None:
            raise ValueError('parent_version/revision require a parent resource ID')
        source = Path(source).expanduser().absolute()
        if source.is_symlink() or not source.is_dir():
            raise ValueError('source must be a non-symlink TF directory')
        files = self._files(source, kind)
        if sum(path.stat().st_size for path in files) > max_bytes:
            raise ValueError('local import exceeds byte size limit')
        descriptor = dict(id='local-' + uuid.uuid4().hex, name=name.strip(), kind=kind,
                          version=version, parent=parent, parent_version=parent_version,
                          parent_revision=parent_revision)
        temporary = None
        with self.store.cache_transition():
            if kind == 'feature-module' and self.is_local_id(parent):
                matching_parent = [
                    record
                    for record in self.records(transition_held=True)
                    if record['descriptor']['id'] == parent
                ]
                if len(matching_parent) != 1:
                    raise ValueError('local parent is no longer resident; import or select it again')
                parent_record = matching_parent[0]
                parent_descriptor = parent_record['descriptor']
                if (
                    parent_descriptor['kind'] != 'corpus'
                    or parent_descriptor['version'] != parent_version
                    or parent_record['source_revision'].casefold() != parent_revision.casefold()
                ):
                    raise ValueError(
                        'local parent version/revision no longer matches the requested module binding'
                    )
            try:
                temporary = Path(tempfile.mkdtemp(prefix='local-import-', dir=self.store.tmp_dir))
                manifest = {}
                observed = {}
                total = 0
                for path in files:
                    operation.remaining_acquisition_seconds()
                    before = path.lstat()
                    # O_NOFOLLOW closes the common source-file symlink race on POSIX;
                    # fstat/lstat identity checks also cover platforms without it.
                    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                                 | getattr(os, 'O_NONBLOCK', 0))
                    with os.fdopen(fd, 'rb') as reader, (temporary / path.name).open('xb') as writer:
                        opened = os.fstat(reader.fileno())
                        if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                            raise ValueError('source TF feature changed or is not a regular file')
                        digest = hashlib.sha256()
                        decoder = codecs.getincrementaldecoder('utf-8')()
                        size = 0
                        first = True
                        while chunk := reader.read(1024 * 1024):
                            operation.remaining_acquisition_seconds()
                            size += len(chunk)
                            total += len(chunk)
                            if total > max_bytes:
                                raise ValueError('local import exceeds byte size limit')
                            if shutil.disk_usage(temporary).free - len(chunk) < self.store.min_free_bytes:
                                raise ValueError('local import would violate free-space reserve')
                            if first and not chunk.startswith((b'@node\n', b'@edge\n', b'@config\n',
                                                              b'@node\r\n', b'@edge\r\n', b'@config\r\n')):
                                raise ValueError('TF feature lacks a native TF header')
                            first = False
                            decoder.decode(chunk)
                            digest.update(chunk)
                            writer.write(chunk)
                        decoder.decode(b'', final=True)
                        after = os.fstat(reader.fileno())
                        if first or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != after.st_size:
                            raise ValueError('source TF feature is empty or changed during import')
                        manifest[path.name] = dict(bytes=size, sha256=digest.hexdigest())
                        observed[path.name] = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                current = self._files(source, kind)
                if {p.name for p in current} != set(observed):
                    raise ValueError('source TF file set changed during import')
                for path in current:
                    metadata = path.lstat()
                    if (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns) != observed[path.name]:
                        raise ValueError('source TF feature changed during import')
                revision = _digest(manifest)
                receipt = dict(schema_version=1, descriptor=descriptor, files=manifest,
                               source_revision=revision)
                receipt['receipt_sha256'] = _digest(receipt)
                (temporary / _RECEIPT).write_text(json.dumps(receipt, sort_keys=True), encoding='utf-8')
                destination = self._path(descriptor['id'], revision, kind)
                destination.parent.mkdir(parents=True, exist_ok=True)
                operation.remaining_acquisition_seconds()
                temporary.rename(destination)
                temporary = None
                try:
                    self.store.touch_cache_object(destination)
                except Exception:
                    # Publication is only complete once the store has indexed
                    # the managed object. A failure after rename must not leave
                    # a receipt-discoverable but unevictable local resource.
                    for sidecar in (
                        self.store._access_path(destination),
                        self.store._meta_path(destination),
                    ):
                        try:
                            sidecar.unlink()
                        except FileNotFoundError:
                            pass
                    shutil.rmtree(destination, ignore_errors=True)
                    self.store._cleanup_empty_parents(destination)
                    raise
                operation.stage('ready')
                return {**descriptor, 'source_revision': revision, 'source_bytes': total,
                        'cache_residency': 'evictable'}
            finally:
                if temporary is not None:
                    shutil.rmtree(temporary)

    @staticmethod
    def _validate_descriptor(descriptor):
        if not isinstance(descriptor, dict):
            raise ValueError('invalid local import descriptor')
        required = {
            'id', 'name', 'kind', 'version', 'parent',
            'parent_version', 'parent_revision',
        }
        if set(descriptor) != required:
            raise ValueError('invalid local import descriptor fields')
        resource_id = descriptor['id']
        if not isinstance(resource_id, str) or not _ID.fullmatch(resource_id):
            raise ValueError('invalid local import descriptor id')
        if (not isinstance(descriptor['name'], str)
                or not descriptor['name'].strip()
                or len(descriptor['name']) > 200):
            raise ValueError('invalid local import descriptor name')
        if (not isinstance(descriptor['version'], str)
                or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}', descriptor['version'])):
            raise ValueError('invalid local import descriptor version')
        kind = descriptor['kind']
        if kind == 'corpus':
            if any(descriptor[key] is not None
                   for key in ('parent', 'parent_version', 'parent_revision')):
                raise ValueError('corpus local import descriptor cannot declare a parent')
        elif kind == 'feature-module':
            if (not isinstance(descriptor['parent'], str)
                    or not descriptor['parent']
                    or not isinstance(descriptor['parent_version'], str)
                    or not descriptor['parent_version']
                    or not isinstance(descriptor['parent_revision'], str)
                    or not _REVISION.fullmatch(descriptor['parent_revision'])):
                raise ValueError('invalid feature-module parent descriptor')
        else:
            raise ValueError('invalid local import descriptor kind')

    def _read(self, path):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError('invalid local import receipt')
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if receipt.get('schema_version') != 1:
            raise ValueError('unsupported local import receipt version')
        descriptor = receipt['descriptor']
        self._validate_descriptor(descriptor)
        revision = receipt['source_revision']
        files = receipt['files']
        if not isinstance(files, dict) or _digest(files) != revision:
            raise ValueError('local import payload identity mismatch')
        receipt_sha256 = receipt.get('receipt_sha256')
        if not isinstance(receipt_sha256, str) or _digest(
                {k: v for k, v in receipt.items() if k != 'receipt_sha256'}
        ) != receipt_sha256:
            raise ValueError('local import receipt integrity mismatch')
        expected = self._path(descriptor['id'], revision, descriptor['kind']) / _RECEIPT
        if path != expected:
            raise ValueError('local import receipt identity mismatch')
        return receipt

    @staticmethod
    def is_local_id(resource_id):
        return isinstance(resource_id, str) and _ID.fullmatch(resource_id) is not None

    def _records_locked(self):
        result = []
        for path in sorted(self.store.snapshots_dir.glob('local-*/*/*/__root__/' + _RECEIPT)):
            try:
                result.append(self._read(path))
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError,
                    TypeError, ValueError, AttributeError) as exc:
                warnings.warn(
                    f'invalid local import receipt ignored at {path}: {exc}',
                    RuntimeWarning,
                    stacklevel=3,
                )
        return result

    def records(self, *, transition_held=False):
        if transition_held:
            return self._records_locked()
        with self.store.cache_transition():
            return self._records_locked()

    def spec(self, record):
        d = record['descriptor']
        return ResourceSpec(
            id=d['id'], name=d['name'], plugin='context-fabric', provider='user-local',
            kind=d['kind'], repository='user-supplied', languages=(), disciplines=(),
            tf_path='tf/' + d['version'], acquisition_strategy='user-local',
            ref=record['source_revision'], parent=d['parent'],
            parent_versions=(d['parent_version'],) if d['parent'] else (),
            module_path=d['id'] if d['parent'] else None,
            dependencies=({'role': 'parent-base', 'ref': d['parent_revision']},) if d['parent'] else (),
            verification_status='community',
            verification_notes=('User-supplied TF data; import is not scholarly validation.',),
            source_snapshot={'revision': record['source_revision'], 'identity': 'sha256'},
        )

    def prepared(self, resource):
        path = self._path(resource.id, resource.ref, resource.kind)
        if not path.is_dir():
            raise FileNotFoundError('local TF import was removed; import the source again')
        record = self._read(path / _RECEIPT)
        if self.spec(record) != resource:
            raise ValueError('local import resource integrity mismatch')
        files = self._files(path, resource.kind)
        if {p.name for p in files} != set(record['files']):
            raise ValueError('local TF payload integrity mismatch')
        operation = current_operation() or OperationControl()
        for feature in files:
            digest = hashlib.sha256()
            size = 0
            with feature.open('rb') as handle:
                while chunk := handle.read(1024 * 1024):
                    operation.remaining_acquisition_seconds()
                    digest.update(chunk)
                    size += len(chunk)
            if dict(bytes=size, sha256=digest.hexdigest()) != record['files'][feature.name]:
                raise ValueError('local TF payload integrity mismatch')
        self.store.touch_cache_object(path)
        return PreparedCorpus(resource_id=resource.id, member_id=None, logical_name=resource.id,
                              relative_path=resource.tf_path, path=path,
                              version=record['descriptor']['version'], source_revision=resource.ref)

    def module(self, resource):
        prepared = self.prepared(resource)
        return PreparedFeatureModule(resource_id=resource.id, parent_resource_id=resource.parent,
                                     module_path=resource.module_path, relative_path=resource.tf_path,
                                     path=prepared.path, source_revision=resource.ref)


class LocalCatalog(Catalog):
    """Merge user imports at read time without mutating the canonical catalog."""
    def __init__(self, canonical, local):
        self.canonical = canonical
        self.local = local

    def _view(self):
        return Catalog([*self.canonical.resources(), *(self.local.spec(r) for r in self.local.records())])

    def resources(self):
        return self._view().resources()

    def ids(self):
        return self._view().ids()

    def get(self, resource_id):
        return self._view().get(resource_id)

    def search(self, *args, **kwargs):
        return self._view().search(*args, **kwargs)

    def modules_for(self, parent_id):
        return self._view().modules_for(parent_id)

    def __iter__(self):
        return iter(self.resources())
