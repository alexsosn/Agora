#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "registry/schema/resources.schema.json"


def main() -> None:
    schema = json.loads(PATH.read_text(encoding="utf-8"))
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        raise RuntimeError("load-cost applicator did not create schema $defs")
    expected = {
        "oneOf": [
            {"$ref": "#/$defs/resourceLoadCost"},
            {"$ref": "#/$defs/collectionMemberLoadCost"},
        ]
    }
    if defs.get("loadCost") != expected:
        raise RuntimeError("loadCost schema shape drifted before diagnostics refinement")
    defs["loadCost"] = {
        "if": {
            "properties": {"scope": {"const": "resource"}},
            "required": ["scope"],
        },
        "then": {"$ref": "#/$defs/resourceLoadCost"},
        "else": {"$ref": "#/$defs/collectionMemberLoadCost"},
    }
    PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Refined load-cost schema dispatch without weakening either scope contract.")


if __name__ == "__main__":
    main()
