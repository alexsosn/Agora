from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

VERIFICATION_RANK = {"experimental": 0, "community": 1, "verified": 2}


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _schema_errors(instance: Any, schema_path: Path, label: str) -> list[str]:
    validator = Draft202012Validator(
        _load_json(schema_path),
        format_checker=FormatChecker(),
    )
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path)
        where = f"{label}:{path}" if path else label
        errors.append(f"{where}: {error.message}")
    return errors


def validate_verification_checks(root: Path, plugins_doc: dict[str, Any]) -> list[str]:
    root = Path(root)
    registry = root / "registry"
    checks_path = registry / "verification-checks.yaml"
    schema_path = registry / "schema" / "verification-checks.schema.json"
    errors: list[str] = []

    if not checks_path.is_file():
        return ["verification checks: missing registry/verification-checks.yaml"]
    if not schema_path.is_file():
        return ["verification checks: missing registry/schema/verification-checks.schema.json"]

    checks_doc = _load_yaml(checks_path)
    errors += _schema_errors(
        checks_doc,
        schema_path,
        "verification-checks.yaml",
    )
    checks = checks_doc.get("checks", []) if isinstance(checks_doc, dict) else []

    check_by_id: dict[str, dict[str, Any]] = {}
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str):
            continue
        check_id = check["id"]
        if check_id in check_by_id:
            errors.append(f"verification-checks.yaml: duplicate id {check_id!r}")
        check_by_id[check_id] = check

    for plugin in plugins_doc.get("plugins", []):
        plugin_id = plugin.get("id")
        clients = (plugin.get("verification") or {}).get("clients", {})
        for client_id, evidence in clients.items():
            if not isinstance(evidence, dict):
                continue
            transport = evidence.get("transport")
            strongest_rank = -1
            strongest_level: str | None = None
            for reference in evidence.get("checks", []):
                if not isinstance(reference, dict):
                    continue
                check_id = reference.get("check_id")
                check = check_by_id.get(check_id)
                prefix = f"plugin {plugin_id}.verification.clients.{client_id}"
                if check is None:
                    errors.append(f"{prefix}: references missing verification check {check_id!r}")
                    continue
                contract = (check.get("plugin"), check.get("client"), check.get("transport"))
                actual = (plugin_id, client_id, transport)
                if contract != actual:
                    errors.append(
                        f"{prefix}: verification check {check_id!r} does not match evidence contract; "
                        f"check={contract!r}, evidence={actual!r}"
                    )
                    continue
                level = check.get("evidence_level")
                rank = VERIFICATION_RANK.get(level, -1)
                if rank > strongest_rank:
                    strongest_rank = rank
                    strongest_level = level

            status = evidence.get("status")
            status_rank = VERIFICATION_RANK.get(status)
            if status_rank is not None and status_rank > strongest_rank:
                errors.append(
                    f"plugin {plugin_id}.verification.clients.{client_id}: status {status!r} "
                    f"exceeds strongest executable evidence {strongest_level!r}"
                )

    return errors
