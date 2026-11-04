#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator, FormatChecker

try:
    from scripts.validate_candidate_research import validate_candidate_research
except ModuleNotFoundError:
    from validate_candidate_research import validate_candidate_research

try:
    from scripts.validate_verification_checks import validate_verification_checks
except ModuleNotFoundError:
    from validate_verification_checks import validate_verification_checks

try:
    from scripts.validate_runtime_environments import validate_runtime_environments
except ModuleNotFoundError:
    from validate_runtime_environments import validate_runtime_environments

ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_RANK = {"experimental": 0, "community": 1, "verified": 2}

# The frozen first release: exactly these plugins, in this order, with its 37
# Context-Fabric resources. Later scopes may only extend it.
FROZEN_SCOPE = "v0.1.yaml"
_SCOPE_NAME = re.compile(r"\Av(\d+(?:\.\d+)*)\.yaml\Z")


def _scope_version(path: Path) -> tuple[int, ...]:
    match = _SCOPE_NAME.match(path.name)
    if match is None:
        raise ValueError(f"not a release-scope file name: {path.name!r}")
    return tuple(int(part) for part in match.group(1).split("."))


def release_scope_paths(registry: Path) -> list[Path]:
    """Every registry/v*.yaml release scope, oldest version first."""
    paths = [path for path in registry.glob("v*.yaml") if _SCOPE_NAME.match(path.name)]
    return sorted(paths, key=_scope_version)


def latest_release_scope(registry: Path) -> Path:
    """The highest-versioned release scope — the one generation targets."""
    paths = release_scope_paths(registry)
    if not paths:
        raise ValueError(f"no release-scope file (v*.yaml) under {registry}")
    return paths[-1]


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _non_finite_json_number_errors(value: Any, label: str, path: tuple[Any, ...] = ()) -> list[str]:
    errors: list[str] = []
    if isinstance(value, float) and not math.isfinite(value):
        rendered_path = ".".join(str(part) for part in path)
        where = f"{label}:{rendered_path}" if rendered_path else label
        errors.append(f"{where}: non-finite number {value!r} is not valid JSON")
        return errors
    if isinstance(value, dict):
        for key, child in value.items():
            errors.extend(_non_finite_json_number_errors(child, label, (*path, key)))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            errors.extend(_non_finite_json_number_errors(child, label, (*path, index)))
    return errors


def schema_errors(instance: Any, schema_path: Path, label: str) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = _non_finite_json_number_errors(instance, label)
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path)
        where = f"{label}:{path}" if path else label
        errors.append(f"{where}: {error.message}")
    return errors


def duplicate_errors(items: Iterable[dict[str, Any]], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        item_id = item["id"]
        if item_id in seen:
            errors.append(f"{label}: duplicate id {item_id!r}")
        seen.add(item_id)
    return errors


def ensure_vocab(value: str, allowed: set[str], where: str, errors: list[str]) -> None:
    if value not in allowed:
        errors.append(f"{where}: unknown controlled-vocabulary value {value!r}")


def ensure_vocab_list(values: Iterable[str], allowed: set[str], where: str, errors: list[str]) -> None:
    for value in values:
        ensure_vocab(value, allowed, where, errors)


def validate_license_evidence(
    resource: dict[str, Any],
    allowed_statuses: set[str],
    errors: list[str],
) -> None:
    """Validate semantic combinations that are awkward to express clearly in JSON Schema."""
    prefix = f"resource {resource['id']}.licenses"
    licenses = resource.get("licenses") or {}
    evidence = licenses.get("evidence")
    if not isinstance(evidence, dict):
        # Presence/shape is enforced by JSON Schema for corpus/collection records.
        return

    status = evidence.get("status")
    if not isinstance(status, str):
        return
    ensure_vocab(status, allowed_statuses, f"{prefix}.evidence.status", errors)

    data = licenses.get("data")
    redistribution = licenses.get("redistribution")
    notes = licenses.get("notes")
    has_notes = isinstance(notes, str) and bool(notes.strip())

    if status == "resolved" and (
        data in {None, "unknown"} or redistribution in {None, "unknown"}
    ):
        errors.append(
            f"{prefix}: resolved evidence requires known data and redistribution"
        )

    if status == "unresolved" and (
        data not in {None, "unknown"} and redistribution not in {None, "unknown"}
    ):
        errors.append(
            f"{prefix}: unresolved evidence requires an unknown licensing dimension"
        )

    if status == "component-specific" and data in {None, "unknown"}:
        errors.append(
            f"{prefix}.data: component-specific evidence requires known or component-specific data"
        )

    if data == "component-specific" and status != "component-specific":
        errors.append(
            f"{prefix}.data: component-specific requires evidence.status='component-specific'"
        )

    if data == "member-specific" and status != "member-specific":
        errors.append(
            f"{prefix}.data: member-specific requires evidence.status='member-specific'"
        )

    if status == "member-specific" and data != "member-specific":
        errors.append(
            f"{prefix}: member-specific evidence requires data='member-specific'"
        )

    if (data == "member-specific" or status == "member-specific") and resource.get("kind") != "collection":
        errors.append(
            f"{prefix}: member-specific licensing is only valid for collections"
        )

    if status in {"component-specific", "member-specific", "unresolved"} and not has_notes:
        errors.append(
            f"{prefix}.notes: {status} evidence requires explanatory notes"
        )


def validate_load_cost(resource: dict[str, Any], errors: list[str]) -> None:
    cost = resource.get("load_cost")
    if not isinstance(cost, dict):
        return

    prefix = f"resource {resource['id']}.load_cost"
    kind = resource.get("kind")
    scope = cost.get("scope")
    expected_scope = {
        "corpus": "resource",
        "collection": "collection-member",
    }.get(kind)
    if expected_scope is not None and scope != expected_scope:
        errors.append(
            f"{prefix}.scope: {kind} resources must be {expected_scope!r}, got {scope!r}"
        )
    if kind == "feature-module":
        errors.append(f"{prefix}: feature modules cannot declare standalone load cost")

    observed_range = cost.get("typical_member_first_load_seconds")
    if isinstance(observed_range, dict):
        minimum = observed_range.get("min")
        maximum = observed_range.get("max")
        numeric = (int, float)
        if (
            isinstance(minimum, numeric)
            and not isinstance(minimum, bool)
            and isinstance(maximum, numeric)
            and not isinstance(maximum, bool)
            and minimum > maximum
        ):
            errors.append(
                f"{prefix}.typical_member_first_load_seconds: min must be <= max"
            )


def validate_registry(root: Path = ROOT) -> list[str]:
    root = Path(root)
    registry = root / "registry"
    schema = registry / "schema"
    errors: list[str] = []

    marketplace_doc = load_yaml(registry / "marketplace.yaml")
    plugins_doc = load_yaml(registry / "plugins.yaml")
    providers_doc = load_yaml(registry / "providers.yaml")
    resources_doc = load_yaml(registry / "resources.yaml")
    materializers_doc = load_yaml(registry / "materializers.yaml")
    verification_checks_doc = load_yaml(registry / "verification-checks.yaml")
    feature_modules_path = registry / "feature-modules.yaml"
    feature_modules_doc = (
        load_yaml(feature_modules_path)
        if feature_modules_path.is_file()
        else {"schema_version": resources_doc["schema_version"], "resources": []}
    )
    vocab = load_yaml(registry / "vocabularies.yaml")
    scope_paths = release_scope_paths(registry)
    scope_docs = {path.name: load_yaml(path) for path in scope_paths}
    scope_doc = scope_docs[FROZEN_SCOPE]

    errors += schema_errors(marketplace_doc, schema / "marketplace.schema.json", "marketplace.yaml")
    errors += schema_errors(plugins_doc, schema / "plugins.schema.json", "plugins.yaml")
    errors += schema_errors(providers_doc, schema / "providers.schema.json", "providers.yaml")
    errors += schema_errors(resources_doc, schema / "resources.schema.json", "resources.yaml")
    errors += schema_errors(
        materializers_doc,
        schema / "materializers.schema.json",
        "materializers.yaml",
    )
    if feature_modules_path.is_file():
        errors += schema_errors(
            feature_modules_doc,
            schema / "resources.schema.json",
            "feature-modules.yaml",
        )
    for name, doc in scope_docs.items():
        errors += schema_errors(doc, schema / "release-scope.schema.json", name)

    plugins = plugins_doc.get("plugins", [])
    providers = providers_doc.get("providers", [])
    materializer_plugins = materializers_doc.get("plugins", [])
    verification_checks = verification_checks_doc.get("checks", [])
    resources = [
        *resources_doc.get("resources", []),
        *feature_modules_doc.get("resources", []),
    ]

    errors += duplicate_errors(plugins, "plugins.yaml")
    errors += duplicate_errors(providers, "providers.yaml")
    errors += duplicate_errors(materializer_plugins, "materializers.yaml")
    errors += duplicate_errors(resources, "resource registry")

    plugin_by_id = {item["id"]: item for item in plugins}
    provider_by_id = {item["id"]: item for item in providers}
    resource_by_id = {item["id"]: item for item in resources}
    verification_check_by_id = {
        item["id"]: item
        for item in verification_checks
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    verification = set(vocab["verification_statuses"])
    provider_health = set(vocab["provider_health_statuses"])
    runtime_modes = set(vocab["runtime_modes"])
    data_modes = set(vocab["data_modes"])
    resource_kinds = set(vocab["resource_kinds"])
    feature_module_statuses = set(vocab.get("feature_module_statuses", []))
    acquisition = set(vocab["acquisition_strategies"])
    collection_discovery = set(vocab["collection_discovery_modes"])
    collection_index_status = set(vocab["collection_index_statuses"])
    redistribution = set(vocab["redistribution_statuses"])
    license_evidence_statuses = set(vocab.get("license_evidence_statuses", []))
    languages = set(vocab["languages"])
    disciplines = set(vocab["disciplines"])
    capabilities = set(vocab["capabilities"])

    for plugin in plugins:
        prefix = f"plugin {plugin['id']}"
        ensure_vocab_list(plugin["disciplines"], disciplines, f"{prefix}.disciplines", errors)
        ensure_vocab(plugin["runtime"]["mode"], runtime_modes, f"{prefix}.runtime.mode", errors)
        if "data_mode" in plugin:
            ensure_vocab(plugin["data_mode"], data_modes, f"{prefix}.data_mode", errors)
        ensure_vocab_list(plugin["capabilities"], capabilities, f"{prefix}.capabilities", errors)
        status = plugin["verification"]["status"]
        ensure_vocab(status, verification, f"{prefix}.verification.status", errors)
        clients = plugin["verification"].get("clients", {})
        client_statuses: list[str] = []
        for client_id, evidence in clients.items():
            client_status = evidence["status"]
            ensure_vocab(
                client_status,
                verification,
                f"{prefix}.verification.clients.{client_id}.status",
                errors,
            )
            client_statuses.append(client_status)
        if status in VERIFICATION_RANK and client_statuses:
            weakest = min(client_statuses, key=VERIFICATION_RANK.__getitem__)
            if status != weakest:
                errors.append(
                    f"{prefix}.verification.status: aggregate status {status!r} must equal weakest client status {weakest!r}"
                )

    errors += validate_verification_checks(root, plugins_doc)

    for plugin in materializer_plugins:
        prefix = f"materializer plugin {plugin['id']}"
        ensure_vocab_list(plugin["disciplines"], disciplines, f"{prefix}.disciplines", errors)
        ensure_vocab(plugin["verification"]["status"], verification, f"{prefix}.verification.status", errors)

    for provider in providers:
        prefix = f"provider {provider['id']}"
        plugin = plugin_by_id.get(provider["plugin"])
        if plugin is None:
            errors.append(f"{prefix}: references missing plugin {provider['plugin']!r}")
        ensure_vocab(provider["access"]["runtime_mode"], runtime_modes, f"{prefix}.access.runtime_mode", errors)
        ensure_vocab(provider["access"]["data_mode"], data_modes, f"{prefix}.access.data_mode", errors)
        health = provider["health"]
        health_status = health["status"]
        ensure_vocab(
            health_status,
            provider_health,
            f"{prefix}.health.status",
            errors,
        )
        evidence = health.get("evidence") or []
        if health_status in provider_health and health_status != "unknown" and not evidence:
            errors.append(
                f"{prefix}.health: {health_status} requires at least one live evidence check"
            )
        for reference in evidence:
            check_id = reference.get("check_id")
            check = verification_check_by_id.get(check_id)
            evidence_prefix = f"{prefix}.health.evidence[{check_id}]"
            if check is None:
                errors.append(f"{evidence_prefix}: references missing verification check {check_id!r}")
                continue
            if check.get("kind") != "live":
                errors.append(f"{evidence_prefix}: provider health evidence must reference a live check")
            check_plugin = check.get("plugin")
            if check_plugin != provider["plugin"]:
                errors.append(
                    f"{evidence_prefix}: verification check belongs to plugin {check_plugin!r}, "
                    f"not provider plugin {provider['plugin']!r}"
                )
            check_provider = check.get("provider")
            if check_provider != provider["id"]:
                errors.append(
                    f"{evidence_prefix}: verification check belongs to provider {check_provider!r}, "
                    f"not {provider['id']!r}"
                )

    for resource in resources:
        prefix = f"resource {resource['id']}"
        if resource["plugin"] not in plugin_by_id:
            errors.append(f"{prefix}: references missing plugin {resource['plugin']!r}")
        provider = provider_by_id.get(resource["provider"])
        if provider is None:
            errors.append(f"{prefix}: references missing provider {resource['provider']!r}")
        elif provider["plugin"] != resource["plugin"]:
            errors.append(
                f"{prefix}: provider {provider['id']!r} belongs to plugin {provider['plugin']!r}, "
                f"not {resource['plugin']!r}"
            )

        ensure_vocab(resource["kind"], resource_kinds, f"{prefix}.kind", errors)
        ensure_vocab_list(resource["languages"], languages, f"{prefix}.languages", errors)
        ensure_vocab_list(resource["disciplines"], disciplines, f"{prefix}.disciplines", errors)
        ensure_vocab(resource["acquisition"]["strategy"], acquisition, f"{prefix}.acquisition.strategy", errors)
        redistribution_value = resource["licenses"].get("redistribution")
        if redistribution_value is not None:
            ensure_vocab(
                redistribution_value,
                redistribution,
                f"{prefix}.licenses.redistribution",
                errors,
            )
        validate_license_evidence(resource, license_evidence_statuses, errors)
        validate_load_cost(resource, errors)
        ensure_vocab(resource["verification"]["status"], verification, f"{prefix}.verification.status", errors)

        if resource["kind"] == "feature-module":
            parent = resource_by_id.get(resource["parent"])
            if parent is None:
                errors.append(f"{prefix}: references missing parent resource {resource['parent']!r}")
            elif parent["kind"] != "corpus":
                errors.append(f"{prefix}: parent {resource['parent']!r} must be a corpus resource")
            elif parent["plugin"] != resource["plugin"] or parent["provider"] != resource["provider"]:
                errors.append(f"{prefix}: parent must use the same plugin and provider")
            ensure_vocab(
                resource["module"]["status"],
                feature_module_statuses,
                f"{prefix}.module.status",
                errors,
            )

            for dependency in (resource.get("upstream") or {}).get("dependencies", []):
                if dependency.get("role") != "parent-base":
                    continue
                dependency_ref = dependency.get("ref")
                if not isinstance(dependency_ref, str) or re.fullmatch(
                    r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", dependency_ref
                ) is None:
                    errors.append(
                        f"{prefix}.upstream.dependencies: parent-base ref must be an immutable "
                        "40- or 64-hex commit id"
                    )
                if parent is not None:
                    parent_repository = (parent.get("upstream") or {}).get("repository")
                    if dependency.get("repository") != parent_repository:
                        errors.append(
                            f"{prefix}.upstream.dependencies: parent-base repository "
                            f"{dependency.get('repository')!r} must match parent repository "
                            f"{parent_repository!r}"
                        )
                    parent_ref = (parent.get("upstream") or {}).get("ref")
                    if not isinstance(parent_ref, str) or not parent_ref:
                        errors.append(
                            f"{prefix}.upstream.dependencies: parent-base ref requires "
                            f"parent {resource['parent']!r} to declare an immutable "
                            "upstream.ref, because the resolver compares the declared "
                            "ref against the prepared parent revision for equality"
                        )
                    elif isinstance(dependency_ref, str) and (
                        dependency_ref.casefold() != parent_ref.casefold()
                    ):
                        errors.append(
                            f"{prefix}.upstream.dependencies: parent-base ref "
                            f"{dependency_ref!r} must equal parent "
                            f"{resource['parent']!r} upstream.ref {parent_ref!r}; "
                            "promote the parent pin and the module together"
                        )

        if resource["kind"] == "collection":
            if resource["acquisition"]["strategy"] != "collection":
                errors.append(f"{prefix}: collection resources must use acquisition.strategy='collection'")
            collection = resource["collection"]
            ensure_vocab(collection["discovery"], collection_discovery, f"{prefix}.collection.discovery", errors)
            member_index = root / collection["member_index"]
            if not member_index.is_file():
                errors.append(f"{prefix}: missing collection member index {collection['member_index']!r}")
                continue
            index_doc = load_yaml(member_index)
            errors += schema_errors(
                index_doc,
                schema / "collection-index.schema.json",
                str(member_index.relative_to(root)),
            )
            if index_doc.get("collection_id") != resource["id"]:
                errors.append(
                    f"{prefix}: member index collection_id {index_doc.get('collection_id')!r} does not match resource id"
                )
            ensure_vocab(
                index_doc.get("index_status"),
                collection_index_status,
                f"{prefix}.collection.index_status",
                errors,
            )
            if collection["discovery"] == "git-tree":
                if index_doc.get("index_status") != "dynamic":
                    errors.append(
                        f"{prefix}: git-tree discovery requires collection index_status='dynamic'"
                    )
                if index_doc.get("members"):
                    errors.append(
                        f"{prefix}: git-tree discovery must not carry a stale committed member list"
                    )
            if collection["discovery"] == "indexed" and index_doc.get("index_status") != "complete":
                errors.append(
                    f"{prefix}: indexed discovery requires collection index_status='complete'"
                )
            member_ids: set[str] = set()
            for member in index_doc.get("members", []):
                member_id = member["id"]
                if member_id in member_ids:
                    errors.append(f"{prefix}: duplicate collection member id {member_id!r}")
                member_ids.add(member_id)
                ensure_vocab_list(
                    member["languages"],
                    languages,
                    f"{prefix}.member[{member_id}].languages",
                    errors,
                )
                ensure_vocab(
                    member["verification"]["status"],
                    verification,
                    f"{prefix}.member[{member_id}].verification.status",
                    errors,
                )
                for reference in member["verification"].get("evidence", []):
                    check_id = reference.get("check_id")
                    if check_id not in verification_check_by_id:
                        errors.append(
                            f"{prefix}.member[{member_id}].verification.evidence[{check_id}]: "
                            f"references missing verification check {check_id!r}"
                        )
        elif resource["acquisition"]["strategy"] == "collection":
            errors.append(f"{prefix}: non-collection resource cannot use acquisition.strategy='collection'")

    # Every scope's membership must exist; the frozen v0.1 additionally keeps
    # its exact shape, and a later (prospective) scope may only EXTEND the
    # frozen plugin list — nothing is removed from a shipped release.
    for name, doc in scope_docs.items():
        scope_plugins = set(doc.get("required_plugins", []))
        scope_resources = set(doc.get("required_resources", []))
        missing_plugins = sorted(scope_plugins - set(plugin_by_id))
        missing_resources = sorted(scope_resources - set(resource_by_id))
        if missing_plugins:
            errors.append(f"{name}: missing required plugin records: {', '.join(missing_plugins)}")
        if missing_resources:
            errors.append(f"{name}: missing required resource records: {', '.join(missing_resources)}")
        for resource_id in scope_resources:
            resource = resource_by_id.get(resource_id)
            if resource is not None and resource["plugin"] != "context-fabric":
                errors.append(f"{name}: required resource {resource_id!r} is not owned by context-fabric")

    required_plugins = set(scope_doc["required_plugins"])
    required_resources = set(scope_doc["required_resources"])
    if len(required_plugins) != 4:
        errors.append(f"v0.1.yaml: expected 4 required plugins, found {len(required_plugins)}")
    if len(required_resources) != 37:
        errors.append(f"v0.1.yaml: expected 37 required Context-Fabric resources, found {len(required_resources)}")

    frozen_order = scope_doc["required_plugins"]
    for name, doc in scope_docs.items():
        if name == FROZEN_SCOPE:
            continue
        later_plugins = doc.get("required_plugins", [])
        if later_plugins[: len(frozen_order)] != frozen_order:
            errors.append(
                f"{name}: a prospective scope must keep the frozen {FROZEN_SCOPE} plugins "
                f"first and in order ({', '.join(frozen_order)}); prospective plugins append"
            )
        missing_frozen = sorted(set(scope_doc["required_resources"]) - set(doc.get("required_resources", [])))
        if missing_frozen:
            errors.append(
                f"{name}: a prospective scope must keep every frozen resource; missing: "
                f"{', '.join(missing_frozen)}"
            )

    # The CAL registration's one-candidate checks ("add only cal") are
    # subsumed by the generic prospective-scope rules above, which keep every
    # frozen plugin and resource while letting further prospective plugins
    # (cal, nabu, …) append to the same scope instead of each hardcoding the
    # other out. The release-name and membership checks they carried live on
    # in the generic loop.

    errors += validate_candidate_research(root, vocab)
    errors += validate_runtime_environments(root)
    return errors


def main() -> int:
    errors = validate_registry()
    if errors:
        print("Registry validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "Registry validation passed: marketplace, verification-check, materializer, resource, "
        "feature-module, and candidate-research metadata."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
