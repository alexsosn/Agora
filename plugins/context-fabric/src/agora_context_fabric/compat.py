from __future__ import annotations

from functools import wraps
from typing import Any


_PATCH_MARKER = "_agora_exact_count_compat"


def _argument(args: tuple[Any, ...], kwargs: dict[str, Any], name: str, position: int, default: Any = None) -> Any:
    if name in kwargs:
        return kwargs[name]
    if len(args) > position:
        return args[position]
    return default


def _validation_error(search_api: Any, template: str, logger: Any) -> dict[str, Any] | None:
    try:
        search_api.study(template)
    except Exception as exc:
        logger.error("search: template study failed: %s", exc)
        return {"error": f"Invalid search template: {exc}", "template": template}

    exe = search_api.exe
    if exe and not exe.good:
        errors: list[str] = []
        for line, message in getattr(exe, "badSyntax", []):
            errors.append(f"Line {line}: {message}" if line is not None else message)
        for line, message in getattr(exe, "badSemantics", []):
            errors.append(f"Line {line}: {message}" if line is not None else message)
        return {
            "error": "Invalid search template",
            "errors": errors,
            "template": template,
        }
    return None


def _exact_count(tools: Any, template: str, corpus: str | None) -> dict[str, Any]:
    api = tools.corpus_manager.get_api(corpus)
    search_api = api.S

    validation_error = _validation_error(search_api, template, tools.logger)
    if validation_error is not None:
        return validation_error

    try:
        results = search_api.search(template)
        if results is None:
            total_count = 0
        else:
            try:
                total_count = len(results)
            except TypeError:
                total_count = sum(1 for _ in results)
    except Exception as exc:
        tools.logger.error("search: exact count failed: %s", exc)
        return {
            "error": f"Exact search count failed: {exc}",
            "template": template,
            "exact": False,
        }

    return {"total_count": total_count, "template": template}


def install_exact_count_compat(tools: Any) -> None:
    """Patch cfabric-mcp 0.1.7 so count-only searches bypass its 10k cache cap.

    cfabric-mcp materializes a search into a cache entry capped at 10,000 rows and
    then derives ``total_count`` from the cached rows.  Agora keeps the upstream
    cache path unchanged for result/statistics/passages searches, but executes a
    dedicated search for ``return_type='count'`` so the reported total remains
    exact.  This compatibility shim can be removed after the upstream dependency
    exposes an exact pre-truncation count.
    """
    upstream_search = tools.search
    if getattr(upstream_search, _PATCH_MARKER, False):
        return

    @wraps(upstream_search)
    def patched_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return_type = _argument(args, kwargs, "return_type", 1, "results")
        if return_type != "count":
            return upstream_search(*args, **kwargs)

        template = _argument(args, kwargs, "template", 0)
        if template is None:
            return upstream_search(*args, **kwargs)
        corpus = _argument(args, kwargs, "corpus", 7)
        return _exact_count(tools, template, corpus)

    setattr(patched_search, _PATCH_MARKER, True)
    tools.search = patched_search
