#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "context-fabric"
PLUGIN_SRC = PLUGIN_ROOT / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.catalog import Catalog
from agora_context_fabric.gitstore import GitStore
from agora_context_fabric.resolver import (
    dataset_version,
    select_dataset_root,
    select_dataset_version,
)


def _selected_root(resource, roots: list[str]) -> str:
    if resource.tf_path is None:
        return select_dataset_root(roots)
    normalized = resource.tf_path.replace("\\", "/").strip("/") or "."
    if normalized not in roots:
        raise ValueError(
            f"configured Text-Fabric path {resource.tf_path!r} was not found"
        )
    return normalized


def _child_path(root: str, filename: str) -> str:
    if root == ".":
        return filename
    return str(PurePosixPath(root) / filename)


def audit_catalog(catalog: Catalog, store: GitStore) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    failed = 0
    load_smoke_required: list[str] = []
    parent_states: dict[str, dict[str, Any]] = {}
    parent_version_states: dict[tuple[str, str], dict[str, Any]] = {}

    def parent_state(parent_id: str) -> dict[str, Any]:
        cached = parent_states.get(parent_id)
        if cached is not None:
            return cached
        parent = catalog.get(parent_id)
        if parent.kind != "corpus":
            raise ValueError(f"feature-module parent {parent_id!r} is not a corpus")
        kwargs = {"cache_key": parent.id}
        if parent.ref is not None:
            kwargs["ref"] = parent.ref
        repo = store.ensure_metadata(parent.repository, **kwargs)
        revision = store.selected_revision(repo)
        roots = store.dataset_roots(repo, revision)
        if not roots:
            raise ValueError(f"parent corpus {parent_id!r} has no Text-Fabric dataset roots")
        selected = _selected_root(parent, roots)
        state = {
            "repo": repo,
            "repository": parent.repository,
            "source_revision": revision,
            "roots": roots,
            "versions": sorted({dataset_version(root) for root in roots}),
            "default_root": selected,
            "default_version": dataset_version(selected),
        }
        parent_states[parent_id] = state
        return state

    def parent_version_state(parent_id: str, version: str) -> dict[str, Any]:
        key = (parent_id, version)
        cached = parent_version_states.get(key)
        if cached is not None:
            return cached
        base = parent_state(parent_id)
        root = select_dataset_version(base["roots"], version)
        summary = store.tf_feature_summary(
            base["repo"],
            _child_path(root, "otype.tf"),
            base["source_revision"],
        )
        metadata = summary["metadata"]
        parent_version = metadata.get("version")
        if parent_version is not None and str(parent_version) != version:
            raise ValueError(
                f"parent corpus {parent_id!r} root {root!r} declares @version={parent_version!r}, "
                f"not {version!r}"
            )
        state = {
            "root": root,
            "dataset": metadata.get("dataset"),
            "version": version,
            "max_node": int(summary["max_node"]),
            "warp_fingerprint": store.dataset_warp_fingerprint(
                base["repo"], root, base["source_revision"]
            ),
        }
        parent_version_states[key] = state
        return state

    for resource in catalog:
        item: dict[str, Any] = {
            "id": resource.id,
            "name": resource.name,
            "kind": resource.kind,
            "repository": resource.repository,
        }
        if resource.ref is not None:
            item["ref"] = resource.ref
        if resource.tf_path is not None:
            item["configured_tf_path"] = resource.tf_path
        if resource.parent is not None:
            item["parent"] = resource.parent
            item["compatible_parent_versions"] = list(resource.parent_versions)
        try:
            kwargs = {"cache_key": resource.id}
            if resource.ref is not None:
                kwargs["ref"] = resource.ref
            repo = store.ensure_metadata(resource.repository, **kwargs)
            revision = store.selected_revision(repo)
            item["source_revision"] = revision

            if resource.kind == "feature-module":
                if not resource.tf_path:
                    raise ValueError("feature module has no configured TF path")
                feature_files = store.feature_files(repo, resource.tf_path, revision)
                if not feature_files:
                    raise ValueError(
                        f"no direct .tf feature files found under {resource.tf_path!r}"
                    )
                if not resource.parent_versions:
                    raise ValueError("feature module declares no compatible parent versions")
                state = parent_state(resource.parent or "")
                missing_versions = sorted(set(resource.parent_versions) - set(state["versions"]))
                if missing_versions:
                    raise ValueError(
                        f"parent corpus {resource.parent!r} does not expose declared compatible version(s): "
                        f"{', '.join(missing_versions)}"
                    )

                core_data: set[str] = set()
                core_versions: set[str] = set()
                fallback_versions: set[str] = set()
                max_referenced_node = 0
                for filename in feature_files:
                    summary = store.tf_feature_summary(
                        repo,
                        _child_path(resource.tf_path, filename),
                        revision,
                    )
                    metadata = summary["metadata"]
                    if metadata.get("coreData"):
                        core_data.add(str(metadata["coreData"]))
                        if metadata.get("version"):
                            fallback_versions.add(str(metadata["version"]))
                    if metadata.get("coreVersion"):
                        core_versions.add(str(metadata["coreVersion"]))
                    max_referenced_node = max(
                        max_referenced_node,
                        int(summary["max_node"]),
                    )

                if len(core_data) > 1:
                    raise ValueError(
                        f"feature module supplies conflicting @coreData values: {', '.join(sorted(core_data))}"
                    )

                version_evidence = core_versions or fallback_versions
                undeclared = sorted(version_evidence - set(resource.parent_versions))
                if undeclared:
                    raise ValueError(
                        "feature module core-version metadata conflicts with declared parent compatibility: "
                        f"{', '.join(undeclared)}"
                    )

                parent_evidence: dict[str, dict[str, Any]] = {}
                for version in resource.parent_versions:
                    version_state = parent_version_state(resource.parent or "", version)
                    parent_dataset = version_state["dataset"]
                    if core_data:
                        if parent_dataset is None:
                            raise ValueError(
                                f"parent corpus {resource.parent!r} version {version!r} has no @dataset metadata"
                            )
                        module_core = next(iter(core_data))
                        if module_core != str(parent_dataset):
                            raise ValueError(
                                f"feature module @coreData={module_core!r} does not match parent "
                                f"@dataset={parent_dataset!r} for {resource.parent!r}@{version}"
                            )
                    parent_max = int(version_state["max_node"])
                    if max_referenced_node > parent_max:
                        raise ValueError(
                            f"feature module references node {max_referenced_node}, beyond parent "
                            f"{resource.parent!r}@{version} maximum node {parent_max}"
                        )
                    parent_evidence[version] = {
                        "dataset": parent_dataset,
                        "dataset_root": version_state["root"],
                        "max_node": parent_max,
                        "warp_fingerprint": version_state["warp_fingerprint"],
                    }

                same_parent_commit = (
                    resource.repository == state["repository"]
                    and revision == state["source_revision"]
                )
                metadata_covers_versions = (
                    bool(core_data)
                    and bool(version_evidence)
                    and set(resource.parent_versions).issubset(version_evidence)
                )

                item["status"] = "ok"
                item["module"] = resource.module_path
                item["feature_file_count"] = len(feature_files)
                item["feature_files"] = feature_files
                item["sample_features"] = feature_files[:10]
                item["parent_source_revision"] = state["source_revision"]
                item["parent_available_versions"] = state["versions"]
                item["parent_default_version"] = state["default_version"]
                item["compatible_with_default"] = state["default_version"] in resource.parent_versions
                item["core_data"] = next(iter(core_data)) if core_data else None
                item["core_version_evidence"] = sorted(version_evidence)
                item["max_referenced_node"] = max_referenced_node
                item["parent_compatibility_evidence"] = parent_evidence

                if metadata_covers_versions:
                    item["compatibility_evidence"] = "core-metadata+node-bounds"
                    item["verified_parent_versions"] = list(resource.parent_versions)
                elif same_parent_commit:
                    item["compatibility_evidence"] = "co-located-parent-commit+node-bounds"
                    item["verified_parent_versions"] = list(resource.parent_versions)
                else:
                    item["compatibility_evidence"] = "load-smoke-required"
                    item["verified_parent_versions"] = []
                    item["structurally_compatible_parent_versions"] = list(resource.parent_versions)
                    item["load_smoke_required"] = True
                    load_smoke_required.append(resource.id)
            else:
                roots = store.dataset_roots(repo, revision)
                if not roots:
                    raise ValueError("no Text-Fabric dataset roots were discovered")
                item["status"] = "ok"
                item["dataset_root_count"] = len(roots)
                if resource.kind == "collection":
                    item["sample_roots"] = roots[:10]
                else:
                    selected = _selected_root(resource, roots)
                    item["selected_root"] = selected
                    parent_states[resource.id] = {
                        "repo": repo,
                        "repository": resource.repository,
                        "source_revision": revision,
                        "roots": roots,
                        "versions": sorted({dataset_version(root) for root in roots}),
                        "default_root": selected,
                        "default_version": dataset_version(selected),
                    }
        except Exception as exc:  # audit must report all upstream failures
            failed += 1
            item["status"] = "error"
            item["error"] = str(exc)
        resources.append(item)

    checked = len(resources)
    return {
        "ok": failed == 0,
        "checked": checked,
        "passed": checked - failed,
        "failed": failed,
        "load_smoke_required": sorted(load_smoke_required),
        "resources": resources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit registered Context-Fabric corpora, collections, and feature modules. "
            "The audit resolves Git metadata and streams TF feature content needed for core/version "
            "and node-bound compatibility checks; full parent corpora are not materialized. "
            "Standalone modules without core metadata are marked for a real load smoke."
        )
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("~/.cache/agora/context-fabric-audit").expanduser(),
        help="Metadata clone cache directory",
    )
    parser.add_argument(
        "--resource",
        action="append",
        dest="resource_ids",
        help="Audit only this resource ID; may be repeated",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path",
    )
    args = parser.parse_args()

    catalog = Catalog.from_plugin_root(PLUGIN_ROOT)
    if args.resource_ids:
        selected = [catalog.get(resource_id) for resource_id in args.resource_ids]
        parents = [
            catalog.get(resource.parent)
            for resource in selected
            if resource.kind == "feature-module" and resource.parent
        ]
        by_id = {resource.id: resource for resource in [*parents, *selected]}
        catalog = Catalog(by_id.values())

    report = audit_catalog(catalog, GitStore(args.cache_dir))
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
