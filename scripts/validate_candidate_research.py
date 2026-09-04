from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> Any:
    import json

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


def _duplicate_ids(items: list[dict[str, Any]], label: str) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        item_id = item.get("id")
        if item_id in seen:
            errors.append(f"{label}: duplicate id {item_id!r}")
        if isinstance(item_id, str):
            seen.add(item_id)
    return errors


def _ensure_vocab(
    values: list[str],
    allowed: set[str],
    where: str,
    errors: list[str],
) -> None:
    for value in values:
        if value not in allowed:
            errors.append(f"{where}: unknown controlled-vocabulary value {value!r}")


def validate_candidate_research(root: Path, vocab: dict[str, Any]) -> list[str]:
    """Validate optional candidate-research metadata under ``root/research``.

    Temporary registry-only fixtures used by older tests may omit ``research``;
    the repository itself contains the research tree and Foundation validates it.
    """

    root = Path(root)
    research = root / "research"
    candidates_path = research / "candidates.yaml"
    if not candidates_path.is_file():
        return []

    schema_path = research / "schema" / "candidates.schema.json"
    if not schema_path.is_file():
        return ["candidate research: missing schema research/schema/candidates.schema.json"]

    doc = _load_yaml(candidates_path)
    errors = _schema_errors(doc, schema_path, "research/candidates.yaml")
    source_documents = doc.get("source_documents", []) if isinstance(doc, dict) else []
    candidates = doc.get("candidates", []) if isinstance(doc, dict) else []

    if all(isinstance(item, dict) and "id" in item for item in source_documents):
        errors += _duplicate_ids(source_documents, "candidate source documents")
    if all(isinstance(item, dict) and "id" in item for item in candidates):
        errors += _duplicate_ids(candidates, "candidate research")

    declared_sources: set[str] = set()
    for source in source_documents:
        if not isinstance(source, dict):
            continue
        path = source.get("path")
        if not isinstance(path, str):
            continue
        declared_sources.add(path)
        if not (root / path).is_file():
            errors.append(f"candidate source document {source.get('id')!r}: missing narrative source {path!r}")

    capabilities = set(vocab.get("capabilities", []))
    disciplines = set(vocab.get("disciplines", []))
    resource_kinds = set(vocab.get("resource_kinds", []))

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("id", "<unknown>")
        prefix = f"candidate {candidate_id}"
        taxonomy = candidate.get("taxonomy") or {}
        _ensure_vocab(
            list(taxonomy.get("capabilities") or []),
            capabilities,
            f"{prefix}.taxonomy.capabilities",
            errors,
        )
        _ensure_vocab(
            list(taxonomy.get("disciplines") or []),
            disciplines,
            f"{prefix}.taxonomy.disciplines",
            errors,
        )
        _ensure_vocab(
            list(taxonomy.get("resource_kinds") or []),
            resource_kinds,
            f"{prefix}.taxonomy.resource_kinds",
            errors,
        )

        for source in candidate.get("sources") or []:
            if not isinstance(source, dict):
                continue
            notes_path = source.get("notes")
            if not isinstance(notes_path, str):
                continue
            if not (root / notes_path).is_file():
                errors.append(f"{prefix}: missing narrative source {notes_path!r}")
            if declared_sources and notes_path not in declared_sources:
                errors.append(
                    f"{prefix}: narrative source {notes_path!r} is not declared in source_documents"
                )

        evidence = candidate.get("evidence") or []
        dates = [item.get("checked_at") for item in evidence if isinstance(item, dict)]
        seen_dates: set[str] = set()
        for checked_at in dates:
            if not isinstance(checked_at, str):
                continue
            if checked_at in seen_dates:
                errors.append(f"{prefix}: duplicate evidence checked_at {checked_at!r}")
            seen_dates.add(checked_at)
        string_dates = [value for value in dates if isinstance(value, str)]
        if string_dates != sorted(string_dates):
            errors.append(f"{prefix}: evidence snapshots must be ordered oldest to newest")

        promotion = candidate.get("promotion") or {}
        if promotion.get("status") == "promoted" and not promotion.get("targets"):
            errors.append(f"{prefix}: promoted candidate requires at least one target")

    return errors
