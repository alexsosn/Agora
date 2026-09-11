from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, Callable

from .gitstore import GIB
from .operation import OperationControl
from .service import ContextFabricService

try:  # Foundation unit tests intentionally do not install the MCP runtime.
    from mcp.server.fastmcp import Context as MCPContext
except ImportError:  # pragma: no cover - exercised by the lightweight unit environment
    MCPContext = Any  # type: ignore[misc,assignment]

try:  # Runtime MCP depends on AnyIO; lightweight Foundation tests do not.
    import anyio
except ImportError:  # pragma: no cover - fallback is exercised in Foundation
    anyio = None  # type: ignore[assignment]


_STAGE_PROGRESS = {
    "resolving": 1.0,
    "acquiring/materializing": 2.0,
    "loading/compiling": 3.0,
    "ready": 4.0,
}


async def _drain_operation_stages(ctx: Any, stages: queue.SimpleQueue[str]) -> None:
    while True:
        try:
            stage = stages.get_nowait()
        except queue.Empty:
            return
        if ctx is not None:
            await ctx.report_progress(
                progress=_STAGE_PROGRESS.get(stage, 0.0),
                total=4.0,
                message=stage,
            )


async def _join_cancelled_worker(done: threading.Event) -> None:
    """Wait through repeated task cancellation until owned worker mutation stops."""

    if anyio is not None:
        # AnyIO cancellation is level-triggered. A shielded scope prevents a
        # cancelled MCP request from repeatedly cancelling the cleanup wait and
        # turning it into a hot loop while the owned worker is still stopping.
        with anyio.CancelScope(shield=True):
            while not done.is_set():
                await anyio.sleep(0.02)
        return

    while not done.is_set():
        try:
            await asyncio.shield(asyncio.sleep(0.02))
        except asyncio.CancelledError:
            # Lightweight asyncio-only tests can still deliver repeated
            # cancellation; keep ownership until the worker is actually done.
            continue


async def _run_long_operation(
    call: Callable[[OperationControl], dict[str, Any]],
    ctx: Any,
) -> dict[str, Any]:
    """Run blocking Context-Fabric orchestration without blocking the MCP loop.

    A dedicated short-lived thread keeps the implementation transport-neutral.
    On handler cancellation the same operation token is signalled, and the async
    handler waits for that worker to stop before allowing cancellation to unwind.
    """

    stages: queue.SimpleQueue[str] = queue.SimpleQueue()
    operation = OperationControl(on_stage=stages.put)
    done = threading.Event()
    outcome: dict[str, Any] = {}

    def worker() -> None:
        try:
            outcome["result"] = call(operation)
        except BaseException as exc:
            outcome["error"] = exc
        finally:
            done.set()

    thread = threading.Thread(
        target=worker,
        name="agora-cfabric-long-operation",
        daemon=True,
    )
    thread.start()

    try:
        while not done.is_set():
            await _drain_operation_stages(ctx, stages)
            await asyncio.sleep(0.02)
        await _drain_operation_stages(ctx, stages)
    except BaseException:
        operation.cancel()
        await _join_cancelled_worker(done)
        thread.join()
        raise

    thread.join()
    error = outcome.get("error")
    if error is not None:
        raise error
    result = outcome.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Context-Fabric long operation returned no result")
    return result


def register_tools(mcp: Any, service: ContextFabricService) -> None:
    """Register Agora resource-management tools on a FastMCP-compatible server."""

    @mcp.tool()
    def list_available_corpora(
        query: str = "",
        language: str | None = None,
        discipline: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        """List Agora's directly loadable Context-Fabric corpora and collections.

        By default feature modules are excluded so every returned item can be
        passed to prepare_corpus/load_corpus. Use kind='feature-module' to
        discover optional modules explicitly. Parent corpus descriptions expose
        modules compatible with the default selected version and all registered
        modules with their compatible parent versions.
        """
        return service.list_resources(
            query,
            language=language,
            discipline=discipline,
            kind=kind,
        )

    @mcp.tool()
    def describe_available_corpus(resource_id: str) -> dict[str, Any]:
        """Describe one available Agora corpus, collection, or feature module."""
        return service.describe_resource(resource_id)

    @mcp.tool()
    def list_collection_members(
        resource_id: str,
        query: str = "",
        source_revision: str | None = None,
        source_mode: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Discover separately loadable corpora inside one collection snapshot.

        The response contains the immutable `source_revision` used for discovery.
        Pass it back for later pages and then to prepare_corpus/load_corpus to
        keep the workflow on the same upstream collection revision.

        `source_mode` may be `prefer-fresh`, `offline`, or `require-fresh`.
        Omit it for the default prefer-fresh behavior. `offline` performs no
        network acquisition and requires the relevant revision/index to be
        resident. `require-fresh` refuses cached fallback.
        """
        kwargs: dict[str, Any] = {
            "query": query,
            "offset": offset,
            "limit": limit,
        }
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        if source_mode is not None:
            kwargs["source_mode"] = source_mode
        return service.list_members(resource_id, **kwargs)

    @mcp.tool()
    async def prepare_corpus(
        resource_id: str,
        ctx: MCPContext,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        source_mode: str | None = None,
        modules: list[str] | None = None,
    ) -> dict[str, Any]:
        """Acquire/cache a corpus version and optional registered feature modules.

        Long preparation yields the MCP event loop and reports coarse stages when
        the client requests progress: `resolving`, `acquiring/materializing`, and
        `ready`. Acquisition/materialization has an independent bounded wall-clock
        deadline; cancellation waits for Agora-owned Git/materialization work to
        stop rather than abandoning a mutating worker thread.

        For collection members, pass the `source_revision` returned by
        list_collection_members to resolve the member at exactly that upstream
        commit. `source_mode='offline'` guarantees no acquisition network path
        and succeeds only when the exact source snapshots/index are resident.
        `source_mode='require-fresh'` requires a successful remote refresh and is
        incompatible with an explicit immutable `source_revision`.

        When modules are selected, the response includes `load_preflight` for
        the exact derived overlay: warm/cold state, whether a full compile is
        currently required, direct source bytes, default compile byte/time
        guardrails, host free-space reserve, ordered module precedence, and the
        parent's historical load-cost reference when one exists. Module order is
        `ordered-last-wins`: if two modules expose the same feature filename, the
        later module wins, so reversing module order can intentionally produce a
        different overlay. A new cold overlay can require a parent-scale compile
        even when the module files themselves are small. Treat warm/cold state as
        a point-in-time preflight observation; load_corpus rechecks it under the
        exact-object compile lock.

        Prepared paths are cache-resident but evictable after this call returns;
        use load_corpus when a corpus must stay protected for active use.
        """
        kwargs: dict[str, Any] = {"member_id": member_id, "modules": modules}
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        if source_mode is not None:
            kwargs["source_mode"] = source_mode
        return await _run_long_operation(
            lambda operation: service.prepare(
                resource_id,
                **kwargs,
                operation=operation,
            ),
            ctx,
        )

    @mcp.tool()
    async def load_corpus(
        resource_id: str,
        ctx: MCPContext,
        member_id: str | None = None,
        version: str | None = None,
        source_revision: str | None = None,
        source_mode: str | None = None,
        features: str | list[str] | None = None,
        modules: list[str] | None = None,
        max_compile_gb: float | None = None,
        max_compile_minutes: float | None = None,
    ) -> dict[str, Any]:
        """Acquire and load a corpus; its final cache path is leased until unload.

        Long loads report coarse MCP progress when supported by the client:
        `resolving`, `acquiring/materializing`, `loading/compiling`, then `ready`.
        Acquisition and cold compilation have separate wall-clock budgets. Client
        cancellation is bridged to the same cooperative token used by the cold
        compiler, and the MCP handler does not unwind while owned worker mutation
        is still active.

        For a collection member, reuse the discovery `source_revision` to load
        exactly that collection snapshot. `source_mode='offline'` guarantees no
        acquisition network path; `source_mode='require-fresh'` refuses cached
        fallback. Responses report the immutable revision plus source-resolution
        freshness provenance. The response also includes `logical_name`; pass
        that value to unload_corpus.

        For an unfamiliar or potentially expensive feature-module combination,
        call prepare_corpus first and inspect its `load_preflight` plus
        corpus_cache_status before loading. A genuinely warm current-format cache
        follows the normal upstream loader path. Cold compilation runs in a
        contained worker with Agora-owned observed disk/time guardrails.
        `max_compile_gb` and `max_compile_minutes` are optional positive per-load
        overrides and may be used to set stricter limits than the defaults shown
        by prepare_corpus; neither disables the server's configured
        minimum-free-space reserve. Use corpus_cache_status to inspect active cold
        loads and cancel_corpus_load with the reported load_id when cancellation
        is needed.
        """
        kwargs: dict[str, Any] = {
            "member_id": member_id,
            "features": features,
            "modules": modules,
        }
        if version is not None:
            kwargs["version"] = version
        if source_revision is not None:
            kwargs["source_revision"] = source_revision
        if source_mode is not None:
            kwargs["source_mode"] = source_mode
        if max_compile_gb is not None:
            kwargs["max_compile_gb"] = max_compile_gb
        if max_compile_minutes is not None:
            kwargs["max_compile_minutes"] = max_compile_minutes
        return await _run_long_operation(
            lambda operation: service.load(
                resource_id,
                **kwargs,
                operation=operation,
            ),
            ctx,
        )

    @mcp.tool()
    def cancel_corpus_load(load_id: str) -> dict[str, Any]:
        """Request cancellation of an active cold compile owned by this server.

        Active load IDs are reported by corpus_cache_status. Cancellation is
        idempotent while a worker is active. A different Agora server process can
        suppress duplicate compilation through the shared compile lock, but its
        worker cannot be cancelled through this process-local tool.
        """
        return service.cancel_load(load_id)

    @mcp.tool()
    def unload_corpus(logical_name: str) -> dict[str, Any]:
        """Unload an Agora-loaded corpus and release its cache lease.

        Use the exact `logical_name` returned by load_corpus. Repeating unload is
        safe and reports `was_loaded=false` when nothing remains loaded.
        """
        return service.unload(logical_name)

    @mcp.tool()
    def corpus_cache_status() -> dict[str, Any]:
        """Report cache usage, limits, active leases, and active cold loads."""
        return service.cache_status()

    @mcp.tool()
    def prune_corpus_cache(target_gb: float | None = None) -> dict[str, Any]:
        """LRU-prune unused Context-Fabric cache objects.

        `target_gb` is a soft logical cache-size target. Active objects are never
        forced out; the result explicitly reports whether the requested target
        and free-space guardrail were achieved.
        """
        if target_gb is not None and target_gb < 0:
            raise ValueError("target_gb must be >= 0")
        target_bytes = None if target_gb is None else int(target_gb * GIB)
        return service.prune_cache(target_bytes=target_bytes)

    @mcp.tool()
    def remove_cached_corpus(
        resource_id: str,
        member_id: str | None = None,
        source_revision: str | None = None,
    ) -> dict[str, Any]:
        """Remove matching unused cache objects for a registered resource.

        For corpus resources this includes unused derived overlays. Active
        matches are skipped and reported. `source_revision` filters source
        snapshots and overlays by the parent corpus revision.
        """
        return service.remove_cached(
            resource_id,
            member_id=member_id,
            source_revision=source_revision,
        )
