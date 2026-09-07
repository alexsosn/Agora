from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

_MAX_DIAGNOSTIC_CHARS = 16_384


def run_payload(payload: dict[str, Any]) -> Any:
    """Invoke the pinned upstream loader unchanged inside the worker process."""

    from cfabric_mcp import corpus_manager

    return corpus_manager.load(
        payload["path"],
        name=payload["name"],
        features=payload.get("features"),
    )


def _write_diagnostic(path: Path, exc: BaseException) -> None:
    diagnostic = {
        "type": type(exc).__name__,
        "message": str(exc)[:_MAX_DIAGNOSTIC_CHARS],
        "traceback": traceback.format_exc(limit=20)[-_MAX_DIAGNOSTIC_CHARS:],
    }
    try:
        path.write_text(json.dumps(diagnostic, ensure_ascii=False), encoding="utf-8")
    except OSError:
        # Diagnostics must never obscure the worker's real non-zero outcome.
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise TypeError("compile worker payload must be a JSON object")
        run_payload(payload)
    except BaseException as exc:
        _write_diagnostic(args.diagnostic, exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the supervisor
    raise SystemExit(main())
