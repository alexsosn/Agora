"""Repair one known Context-Fabric 0.5.x compiler omission in derived CFM data.

The upstream CFM compiler registers valid zero-row TF node features in
meta.json but omits their .npy arrays. Never modify authenticated .tf inputs:
only recreate provably all-missing *derived* CFM feature arrays, after the
release snapshot receipt and every original source feature has been verified.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

# Text-Fabric/Context-Fabric supports language-qualified feature names such
# as book@en in sectionFeatures. Keep basenames bounded, relative and safe.
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,127}(?:@[A-Za-z][A-Za-z0-9_-]{0,30})?\Z")
_MAX_META_BYTES = 2 * 1024 * 1024
_MAX_NODES = 20_000_000


def complete_empty_compiled_features(snapshot: Path, *, min_free_bytes: int = 0) -> int:
    """Return repaired feature count; reject corrupt nonempty/mixed cache state.

    It is the caller's responsibility to verify the immutable TF feature
    receipt first and coordinate writes with the snapshot's cache lock.
    """
    root = snapshot / ".cfm"
    if not root.exists() and not root.is_symlink():
        return 0
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe CFM compiled-cache root")
    # The native source verifier accepts a derived .cfm directory containing
    # unrelated future compiler files. Importing the optional CF/NumPy runtime
    # just to inspect that directory breaks data-only snapshot-cache clients.
    # Only a versioned CFM manifest requires feature repair.
    children = list(root.iterdir())
    if any(child.is_symlink() for child in children):
        raise ValueError("unsafe CFM compiled-cache version symlink")
    manifests = [
        child / "meta.json" for child in children
        if child.is_dir() and (child / "meta.json").exists()
    ]
    if not manifests:
        return 0
    from cfabric.core.config import CFM_VERSION
    from cfabric.io.loader import Data
    from cfabric.storage.string_pool import IntFeatureArray, StringPool

    cfm = root / str(CFM_VERSION)
    if not cfm.exists() and not cfm.is_symlink():
        return 0
    features_dir = cfm / "features"
    metadata_file = cfm / "meta.json"
    for path in (cfm, features_dir):
        if path.is_symlink() or not path.is_dir():
            raise ValueError("unsafe CFM compiled-cache feature directory")
    if metadata_file.is_symlink() or not metadata_file.is_file() or metadata_file.stat().st_size > _MAX_META_BYTES:
        raise ValueError("unsafe CFM compiled-cache metadata")
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("invalid CFM compiled-cache metadata") from exc
    max_node = metadata.get("max_node") if isinstance(metadata, dict) else None
    feature_manifest = metadata.get("features") if isinstance(metadata, dict) else None
    node_features = feature_manifest.get("node") if isinstance(feature_manifest, dict) else None
    if (not isinstance(max_node, int) or isinstance(max_node, bool)
            or not 0 < max_node <= _MAX_NODES
            or not isinstance(node_features, list) or len(node_features) > 10_000
            or any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in node_features)
            or len(set(node_features)) != len(node_features)):
        raise ValueError("invalid CFM compiled-cache feature manifest")

    repaired = 0
    for name in node_features:
        native = snapshot / (name + ".tf")
        str_files = (features_dir / (name + "_strings.npy"), features_dir / (name + "_idx.npy"))
        int_file = features_dir / (name + ".npy")
        compiled = (*str_files, int_file)
        if any(path.is_symlink() or (path.exists() and not path.is_file())
               for path in compiled):
            raise ValueError(f"unsafe CFM compiled-cache array for {name}")
        str_present = tuple(path.is_file() for path in str_files)
        int_present = int_file.is_file()
        if int_present and any(str_present):
            raise ValueError(f"mixed CFM compiled-cache representation for {name}")
        if str_present[0] != str_present[1]:
            raise ValueError(f"partial CFM compiled-cache feature {name}")
        if int_present or all(str_present):
            continue
        # Exactly absent compiled arrays must be explained by an actually
        # empty immutable TF node feature; nonempty missing data fails closed.
        if native.is_symlink() or not native.is_file():
            raise ValueError(f"missing authenticated TF feature for CFM {name}")
        parsed = Data(str(native))
        if not parsed.load(silent="deep") or parsed.isEdge or parsed.isConfig:
            raise ValueError(f"invalid native TF node feature for CFM {name}")
        if parsed.data:
            raise ValueError(f"nonempty TF feature {name} is absent from CFM cache")
        dtype = parsed.dataType
        if dtype not in ("str", "int"):
            raise ValueError(f"unsupported empty CFM feature type {dtype!r}")
        disk_needed = max_node * 4 + (64 * 1024)
        if shutil.disk_usage(features_dir).free - disk_needed < min_free_bytes:
            raise ValueError("empty CFM feature repair would violate disk free-space reserve")

        # Serialize into private temporary location and rename into the
        # derived-cache features directory, never through a source TF path.
        with tempfile.TemporaryDirectory(prefix="cfm-empty-", dir=features_dir) as directory:
            tmp = Path(directory)
            if dtype == "str":
                StringPool.from_dict({}, max_node).save(str(tmp / name))
                outputs = (name + "_strings.npy", name + "_idx.npy")
            else:
                IntFeatureArray.from_dict({}, max_node).save(str(tmp / (name + ".npy")))
                outputs = (name + ".npy",)
            original_meta = dict(parsed.metaData)
            original_meta.pop("valueType", None)
            (tmp / (name + "_meta.json")).write_text(
                json.dumps({"name": name, "kind": "node", "value_type": dtype,
                            **original_meta}, ensure_ascii=False),
                encoding="utf-8",
            )
            for filename in (*outputs, name + "_meta.json"):
                destination = features_dir / filename
                if destination.is_symlink() or destination.exists():
                    raise ValueError(f"CFM compiled-cache array appeared concurrently for {name}")
                os.replace(tmp / filename, destination)
        repaired += 1
    return repaired



def restore_compiled_section_index(loader: object, logical_name: str) -> bool:
    """Restore C.sections omitted by Context-Fabric 0.5.x's CFM fast loader.

    The upstream CFM path sets sectionTypes/sectionFeats and loads feature
    objects but does not call sectionsFromApi(), unlike loadAll(). A corpus
    manager's selective load() must preserve T.nodeFromSection after restart.
    This function does not modify source data or persist index artifacts.
    """
    get = getattr(loader, "get", None)
    if not callable(get):
        return False
    loaded = get(logical_name)
    if not isinstance(loaded, tuple) or len(loaded) != 2:
        return False
    fabric, api = loaded
    if not getattr(fabric, "_loaded_from_cfm", False):
        return False
    if hasattr(api.C, "sections"):
        return False

    section_types = getattr(fabric, "sectionTypes", ())
    section_feats = getattr(fabric, "sectionFeats", ())
    # TF corpora may legitimately offer no section Text API. Do not make
    # otherwise valid CFM loads fail just because there is no index to build.
    if not section_types and not section_feats:
        return False
    if not section_types or len(section_types) != len(section_feats) or len(section_types) > 3:
        raise ValueError("incomplete CFM section schema; cannot restore text navigation")

    from cfabric.features.computed import Computed
    from cfabric.precompute.prepare import sectionsFromApi

    if len(section_types) == 1:
        data = {"sec1": {}, "sec2": {}, "seqFromNode": {}, "nodeFromSeq": {}}
    else:
        data = sectionsFromApi(api, list(section_types), list(section_feats))
        if data is None:
            raise ValueError("cannot restore compiled CFM section index")

    # sectionsFromApi intentionally leaves the sequence maps empty. Cold
    # compilation includes those maps for three-level corpora; reconstruct
    # them with Text-Fabric's normal locality and otype API in node order.
    if len(section_types) == 3:
        seq_from_node = data["seqFromNode"]
        node_from_seq = data["nodeFromSeq"]
        for b_index, book in enumerate(api.F.otype.s(section_types[0]), start=1):
            b_seq = (b_index,)
            seq_from_node[book] = b_seq
            node_from_seq[b_seq] = book
            for c_index, chapter in enumerate(
                api.L.d(book, otype=section_types[1]), start=1
            ):
                c_seq = (b_index, c_index)
                seq_from_node[chapter] = c_seq
                node_from_seq[c_seq] = chapter
                for v_index, verse in enumerate(
                    api.L.d(chapter, otype=section_types[2]), start=1
                ):
                    v_seq = (b_index, c_index, v_index)
                    seq_from_node[verse] = v_seq
                    node_from_seq[v_seq] = verse
    api.C.sections = Computed(api, data)
    return True
