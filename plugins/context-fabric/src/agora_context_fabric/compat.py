from __future__ import annotations

from functools import wraps
from typing import Any


_PATCH_MARKER = "_agora_exact_count_compat"


def _argument(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    name: str,
    position: int,
    default: Any = None,
) -> Any:
    if name in kwargs:
        return kwargs[name]
    if len(args) > position:
        return args[position]
    return default


def _validation_error(
    search_api: Any,
    template: str,
    logger: Any,
) -> dict[str, Any] | None:
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


def _count_studied_results(search_api: Any) -> int:
    """Count the uncapped result source produced by ``Search.study()``.

    Context-Fabric 0.5.7's public ``Search.search()`` / ``SearchExe.fetch()`` path
    silently stops after ``SEARCH_FAIL_FACTOR * F.otype.maxNode`` tuples when no
    explicit limit is supplied.  The execution plan created by ``study()`` exposes
    the underlying ``SearchExe.results`` source before that safety wrapper is
    applied.  Counting that source is the compatibility boundary this shim relies
    on.
    """
    exe = search_api.exe
    if exe is None:
        raise RuntimeError("Context-Fabric search study produced no execution plan")

    result_source = getattr(exe, "results", None)
    if result_source is None:
        raise RuntimeError("Context-Fabric execution plan exposes no result source")

    results = result_source() if callable(result_source) else result_source
    if results is None:
        raise RuntimeError("Context-Fabric execution result source is unavailable")

    try:
        return len(results)
    except TypeError:
        return sum(1 for _ in results)


def _exact_count(tools: Any, template: str, corpus: str | None) -> dict[str, Any]:
    api = tools.corpus_manager.get_api(corpus)
    search_api = api.S

    validation_error = _validation_error(search_api, template, tools.logger)
    if validation_error is not None:
        return validation_error

    try:
        total_count = _count_studied_results(search_api)
    except Exception as exc:
        tools.logger.error("search: exact count failed: %s", exc)
        return {
            "error": f"Exact search count failed: {exc}",
            "template": template,
            "exact": False,
        }

    return {"total_count": total_count, "template": template}


def install_exact_count_compat(tools: Any) -> None:
    """Patch cfabric-mcp 0.1.7 so count-only searches are genuinely exact.

    cfabric-mcp materializes a search into a cache entry capped at 10,000 rows and
    derives ``total_count`` from those cached rows.  Calling Context-Fabric's public
    ``Search.search()`` directly is also insufficient because Context-Fabric 0.5.7
    applies a separate ``SearchExe.fetch()`` fail cutoff.  Agora therefore studies
    the template once and counts the execution plan's uncapped result source.

    Result/statistics/passages searches still use the upstream cache unchanged.
    Count-first workflows consequently execute the structural query again if the
    caller subsequently requests materialized results; this is an intentional
    temporary correctness-over-performance trade-off until upstream exposes an
    exact pre-truncation total in its shared cache.
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
