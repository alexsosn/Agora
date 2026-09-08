#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one guarded anchor, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def edit_schema() -> None:
    path = ROOT / "registry/schema/resources.schema.json"
    text = path.read_text(encoding="utf-8")
    if '"$defs"' in text:
        raise RuntimeError("resources schema unexpectedly already has $defs")

    measurement = {
        "type": "object",
        "additionalProperties": False,
        "required": ["checked_at", "agora_revision", "environment", "evidence"],
        "properties": {
            "checked_at": {"type": "string", "format": "date"},
            "agora_revision": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "environment": {"type": "string", "minLength": 1},
            "evidence": {
                "type": "string",
                "format": "uri",
                "pattern": r"^https?://\S+$",
            },
        },
    }
    nonnegative_range = {
        "type": "object",
        "additionalProperties": False,
        "required": ["min", "max"],
        "properties": {
            "min": {"type": "number", "minimum": 0},
            "max": {"type": "number", "minimum": 0},
        },
    }
    resource_fields = [
        "source_size_mb",
        "compiled_size_mb",
        "total_cache_mb",
        "peak_rss_mb",
        "first_load_seconds",
        "warm_load_seconds",
    ]
    resource_cost = {
        "type": "object",
        "additionalProperties": False,
        "required": ["scope", "measurement"],
        "properties": {
            "scope": {"const": "resource"},
            **{name: {"type": "number", "minimum": 0} for name in resource_fields},
            "measurement": {"$ref": "#/$defs/loadCostMeasurement"},
            "notes": {"type": "string", "minLength": 1},
        },
        "anyOf": [{"required": [name]} for name in resource_fields],
    }
    member_fields = [
        "typical_member_cache_mb",
        "typical_member_first_load_seconds",
        "discovery_seconds",
        "discovery_cache_mb",
    ]
    member_cost = {
        "type": "object",
        "additionalProperties": False,
        "required": ["scope", "measurement"],
        "properties": {
            "scope": {"const": "collection-member"},
            "typical_member_cache_mb": {"type": "number", "minimum": 0},
            "typical_member_first_load_seconds": {"$ref": "#/$defs/nonNegativeRange"},
            "discovery_seconds": {"type": "number", "minimum": 0},
            "discovery_cache_mb": {"type": "number", "minimum": 0},
            "measurement": {"$ref": "#/$defs/loadCostMeasurement"},
            "notes": {"type": "string", "minLength": 1},
        },
        "anyOf": [{"required": [name]} for name in member_fields],
    }
    defs = {
        "loadCostMeasurement": measurement,
        "nonNegativeRange": nonnegative_range,
        "resourceLoadCost": resource_cost,
        "collectionMemberLoadCost": member_cost,
        "loadCost": {
            "oneOf": [
                {"$ref": "#/$defs/resourceLoadCost"},
                {"$ref": "#/$defs/collectionMemberLoadCost"},
            ]
        },
    }
    rendered_defs = json.dumps(defs, indent=2, ensure_ascii=False)
    defs_block = '  "$defs": ' + rendered_defs.replace("\n", "\n  ") + ",\n"
    anchor = '  "$id": "https://github.com/alexsosn/Agora/registry/schema/resources.schema.json",\n'
    if text.count(anchor) != 1:
        raise RuntimeError("resources schema $id anchor drifted")
    text = text.replace(anchor, anchor + defs_block, 1)

    property_anchor = '          "description": {"type": "string", "minLength": 1},\n'
    if text.count(property_anchor) != 1:
        raise RuntimeError("resources schema description anchor drifted")
    text = text.replace(
        property_anchor,
        property_anchor + '          "load_cost": {"$ref": "#/$defs/loadCost"},\n',
        1,
    )

    feature_then = '            "then": {"required": ["parent", "compatibility", "module"]},\n'
    replacement = (
        '            "then": {\n'
        '              "allOf": [\n'
        '                {"required": ["parent", "compatibility", "module"]},\n'
        '                {"not": {"required": ["load_cost"]}}\n'
        '              ]\n'
        '            },\n'
    )
    if text.count(feature_then) != 1:
        raise RuntimeError("feature-module schema anchor drifted")
    text = text.replace(feature_then, replacement, 1)

    json.loads(text)
    path.write_text(text, encoding="utf-8")


def edit_validator() -> None:
    path = ROOT / "scripts/validate_registry.py"
    insertion_anchor = "\n\ndef validate_registry(root: Path = ROOT) -> list[str]:\n"
    helper = '''\n\ndef validate_load_cost(resource: dict[str, Any], errors: list[str]) -> None:\n    cost = resource.get("load_cost")\n    if not isinstance(cost, dict):\n        return\n\n    prefix = f"resource {resource['id']}.load_cost"\n    kind = resource.get("kind")\n    scope = cost.get("scope")\n    expected_scope = {\n        "corpus": "resource",\n        "collection": "collection-member",\n    }.get(kind)\n    if expected_scope is not None and scope != expected_scope:\n        errors.append(\n            f"{prefix}.scope: {kind} resources must be {expected_scope!r}, got {scope!r}"\n        )\n    if kind == "feature-module":\n        errors.append(f"{prefix}: feature modules cannot declare standalone load cost")\n\n    observed_range = cost.get("typical_member_first_load_seconds")\n    if isinstance(observed_range, dict):\n        minimum = observed_range.get("min")\n        maximum = observed_range.get("max")\n        numeric = (int, float)\n        if (\n            isinstance(minimum, numeric)\n            and not isinstance(minimum, bool)\n            and isinstance(maximum, numeric)\n            and not isinstance(maximum, bool)\n            and minimum > maximum\n        ):\n            errors.append(\n                f"{prefix}.typical_member_first_load_seconds: min must be <= max"\n            )\n'''
    replace_once(path, insertion_anchor, helper + insertion_anchor)

    call_anchor = (
        "        validate_license_evidence(resource, license_evidence_statuses, errors)\n"
        "        ensure_vocab(resource[\"verification\"][\"status\"], verification, f\"{prefix}.verification.status\", errors)\n"
    )
    replacement = (
        "        validate_license_evidence(resource, license_evidence_statuses, errors)\n"
        "        validate_load_cost(resource, errors)\n"
        "        ensure_vocab(resource[\"verification\"][\"status\"], verification, f\"{prefix}.verification.status\", errors)\n"
    )
    replace_once(path, call_anchor, replacement)


def edit_catalog() -> None:
    path = ROOT / "plugins/context-fabric/src/agora_context_fabric/catalog.py"
    replace_once(
        path,
        "from __future__ import annotations\n\nfrom dataclasses import dataclass, field\n",
        "from __future__ import annotations\n\nimport copy\nfrom dataclasses import dataclass, field\n",
    )
    replace_once(
        path,
        "    licenses: dict[str, Any] = field(default_factory=dict)\n    integration_issues: tuple[str, ...] = ()\n",
        "    licenses: dict[str, Any] = field(default_factory=dict)\n    load_cost: dict[str, Any] = field(default_factory=dict)\n    integration_issues: tuple[str, ...] = ()\n",
    )
    replace_once(
        path,
        "                    licenses=dict(item.get(\"licenses\") or {}),\n                    integration_issues=tuple(item.get(\"integration_issues\") or ()),\n",
        "                    licenses=dict(item.get(\"licenses\") or {}),\n                    load_cost=copy.deepcopy(item.get(\"load_cost\") or {}),\n                    integration_issues=tuple(item.get(\"integration_issues\") or ()),\n",
    )


def edit_service() -> None:
    path = ROOT / "plugins/context-fabric/src/agora_context_fabric/service.py"
    replace_once(
        path,
        "from __future__ import annotations\n\nimport shutil\n",
        "from __future__ import annotations\n\nimport copy\nimport shutil\n",
    )
    replace_once(
        path,
        '            "licenses": dict(resource.licenses),\n            "integration_issues": list(resource.integration_issues),\n',
        '            "licenses": dict(resource.licenses),\n            "load_cost": copy.deepcopy(resource.load_cost) if resource.load_cost else None,\n            "integration_issues": list(resource.integration_issues),\n',
    )


def insert_load_cost(resource_id: str, snippet: str) -> None:
    path = ROOT / "registry/resources.yaml"
    text = path.read_text(encoding="utf-8")
    marker = f"- id: {resource_id}\n"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"resource {resource_id!r} not found")
    next_start = text.find("\n- id: ", start + len(marker))
    end = len(text) if next_start < 0 else next_start + 1
    block = text[start:end]
    if "  load_cost:\n" in block:
        raise RuntimeError(f"resource {resource_id!r} already has load_cost")
    anchor = "  source_snapshot:"
    anchor_at = block.find(anchor)
    if anchor_at < 0:
        raise RuntimeError(f"resource {resource_id!r} has no source_snapshot anchor")
    block = block[:anchor_at] + snippet + block[anchor_at:]
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def seed_registry() -> None:
    measurement = '''    measurement:\n      checked_at: '2026-09-04'\n      agora_revision: bf5fb918d513fcf859bc925a10922e841b777b98\n      environment: "macOS 24.6.0 x86_64; Python 3.13; cfabric-mcp 0.1.7; context-fabric 0.5.7"\n      evidence: "https://github.com/alexsosn/Agora/issues/38#issuecomment-5536924435"\n'''
    insert_load_cost(
        "bhsa",
        '''  load_cost:\n    scope: resource\n    source_size_mb: 165\n    compiled_size_mb: 866\n    total_cache_mb: 1100\n    peak_rss_mb: 2580\n    first_load_seconds: 630\n    warm_load_seconds: 7.7\n'''
        + measurement
        + '    notes: "Historical parent-only measurement; module combinations are excluded and may trigger separate overlay compilation tracked in #46."\n',
    )
    insert_load_cost(
        "cuc",
        '''  load_cost:\n    scope: resource\n    source_size_mb: 3.1\n    compiled_size_mb: 20\n    total_cache_mb: 24\n    peak_rss_mb: 288\n    first_load_seconds: 30\n    warm_load_seconds: 1.5\n'''
        + measurement,
    )
    insert_load_cost(
        "TLHdig-TF",
        '''  load_cost:\n    scope: resource\n    source_size_mb: 388\n    compiled_size_mb: 4600\n    total_cache_mb: 5100\n    peak_rss_mb: 2100\n    first_load_seconds: 1740\n'''
        + measurement
        + '    notes: "Historical observation; peak RSS came from the related earlier run rather than the final converged compile measurement."\n',
    )
    insert_load_cost(
        "greek_literature",
        '''  load_cost:\n    scope: collection-member\n    typical_member_cache_mb: 10\n    typical_member_first_load_seconds: {min: 20, max: 33}\n    discovery_seconds: 5.2\n    discovery_cache_mb: 1.7\n'''
        + measurement,
    )


def main() -> None:
    edit_schema()
    edit_validator()
    edit_catalog()
    edit_service()
    seed_registry()
    print("Applied guarded load-cost GREEN transformations.")


if __name__ == "__main__":
    main()
