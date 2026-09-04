#!/usr/bin/env python3
from __future__ import annotations

import json
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

ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_RANK = {"experimental": 0, "community": 1, "verified": 2}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def schema_errors(instance: Any, schema_path: Path, label: str) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
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
    scope_doc = load_yaml(registry / "v0.1.yaml")

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
    errors += schema_errors(scope_doc, schema / "release-scope.schema.json", "v0.1.yaml")

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
        ensure_vocab(resource["licenses"]["redistribution"], redistribution, f"{prefix}.licenses.redistribution", errors)
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
        elif resource["acquisition"]["strategy"] == "collection":
            errors.append(f"{prefix}: non-collection resource cannot use acquisition.strategy='collection'")

    required_plugins = set(scope_doc["required_plugins"])
    required_resources = set(scope_doc["required_resources"])
    missing_plugins = sorted(required_plugins - set(plugin_by_id))
    missing_resources = sorted(required_resources - set(resource_by_id))
    if missing_plugins:
        errors.append(f"v0.1.yaml: missing required plugin records: {', '.join(missing_plugins)}")
    if missing_resources:
        errors.append(f"v0.1.yaml: missing required resource records: {', '.join(missing_resources)}")

    if len(required_plugins) != 4:
        errors.append(f"v0.1.yaml: expected 4 required plugins, found {len(required_plugins)}")
    if len(required_resources) != 37:
        errors.append(f"v0.1.yaml: expected 37 required Context-Fabric resources, found {len(required_resources)}")

    for resource_id in required_resources:
        resource = resource_by_id.get(resource_id)
        if resource is not None and resource["plugin"] != "context-fabric":
            errors.append(f"v0.1.yaml: required resource {resource_id!r} is not owned by context-fabric")

    errors += validate_candidate_research(root, vocab)
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
