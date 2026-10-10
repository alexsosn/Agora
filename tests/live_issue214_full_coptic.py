"""Live acceptance: complete registered pinned Coptic source → TF → Context-Fabric.

This module is run only after successful production registered materialization.
It is not a fixture, scholarly content certification, or a download tool.
"""
from __future__ import annotations

import asyncio
import gc
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

from tf.fabric import Fabric

from scripts.agora_install_materializer import (
    installation_path,
    load_registry,
    select_plugin,
)
from scripts.context_fabric_mcp_result import decode_mcp_result

COPTIC_COMMIT = "3cde20ec41efb1cacf1710643f01f924f11cbf0b"
UPSTREAM_COMMIT = "3ac067f1709a0012daf39ea8da2fac79980176a5"
UPSTREAM_URL = "https://github.com/CopticScriptorium/corpora.git"
SPARSE = ["/*/*_TT/**", "/*/*_TT.zip"]
EXPECTED_RECORDS = 2_628
EXPECTED_SLOTS = 2_394_354
EXPECTED_MIN_TF_FILES = 120  # previously observed 130 native TF features


def validate_registered_output(root: Path, install_root: Path) -> Path:
    plugin = select_plugin(load_registry(), "copticscriptorium-tf")
    assert plugin["ref"] == COPTIC_COMMIT
    installed = installation_path(plugin, install_root)
    receipt = json.loads(
        (installed / "agora-installation.json").read_text(encoding="utf-8")
    )
    assert receipt["plugin"]["commit"] == COPTIC_COMMIT
    assert receipt["environment"]["install_trust"] == "explicit-code-execution"
    assert len(receipt["execution_identity_sha256"]) == 64

    provenance = json.loads(
        (root / "agora-materialization.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (root / "conversion-summary.json").read_text(encoding="utf-8")
    )
    assert provenance["plugin"]["id"] == "copticscriptorium-tf"
    assert provenance["materializer"] == "copticscriptorium-text-fabric"
    assert provenance["sandbox"] == "bubblewrap"
    source = provenance["source"]
    # This is the critical composed-path gate: no local-source override,
    # test-only sparse selection, moving Git reference or unverifiable SHA.
    assert source["type"] == "git", source
    assert source["url"] == UPSTREAM_URL
    assert source["requested_ref"] == UPSTREAM_COMMIT
    assert source["resolved_commit"] == UPSTREAM_COMMIT
    assert source["sparse_patterns"] == SPARSE
    assert summary["upstream_commit"] == UPSTREAM_COMMIT
    assert summary["upstream_repository"] == "CopticScriptorium/corpora"
    assert summary["output_path"] == "tf"
    assert summary["source_records"] == EXPECTED_RECORDS, summary["source_records"]
    assert summary["slots"] == EXPECTED_SLOTS, summary["slots"]

    tf_dir = root / "tf"
    required_native_files = ("otype.tf", "oslots.tf", "otext.tf")
    missing_native_files = [
        name for name in required_native_files if not (tf_dir / name).is_file()
    ]
    assert not missing_native_files, (
        f"required native Text-Fabric files absent: {missing_native_files}"
    )
    tf_files = sorted(tf_dir.glob("*.tf"))
    assert len(tf_files) >= EXPECTED_MIN_TF_FILES, len(tf_files)
    assert summary["tf_files"] == len(tf_files)
    names = {path.stem for path in tf_files}
    assert {"otype", "oslots", "otext", "source_record_id", "norm", "lemma"} <= names
    forbidden = {name for name in names if name.endswith(("_json", "_xml"))}
    assert not forbidden, f"unexpected structural blob features: {sorted(forbidden)}"
    print(
        json.dumps(
            {
                "stage": "provenance-and-files",
                "source_records": summary["source_records"],
                "slots": summary["slots"],
                "tf_features": len(tf_files),
                "tf_bytes": summary["tf_bytes"],
                "parse_seconds": summary["parse_seconds"],
                "graph_seconds": summary["graph_seconds"],
                "write_seconds": summary["write_seconds"],
                "peak_rss_mb": summary["peak_rss_mb"],
                "missing_license_metadata_records": len(
                    summary["missing_license_metadata_source_records"]
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )

    api = Fabric(locations=[str(tf_dir)], silent="deep").load(
        "source_record_id norm lemma pos dependency_head", silent="deep"
    )
    assert api, "fresh Text-Fabric reload failed"
    assert api.F.otype.maxSlot == EXPECTED_SLOTS
    assert len(api.F.otype.s("document")) == EXPECTED_RECORDS
    assert any(api.F.lemma.v(w) for w in range(1, min(1001, EXPECTED_SLOTS + 1)))
    # Native edges, not JSON/XML serialized structures.
    assert api.E.dependency_head is not None
    print(
        json.dumps(
            {"stage": "native-tf-reload", "slots": api.F.otype.maxSlot,
             "documents": EXPECTED_RECORDS},
            sort_keys=True,
        ),
        flush=True,
    )
    del api
    gc.collect()
    return tf_dir


async def verify_context_fabric(source: Path) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root = Path.cwd()
    cache = Path(os.environ["RUNNER_TEMP"]) / "coptic-full-consumer-cache"
    env = dict(
        os.environ,
        PYTHONPATH=str(root / "plugins/context-fabric/src"),
        AGORA_CORPUS_MIN_FREE_GB="0",
    )
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m", "agora_context_fabric.server",
            "--plugin-root", str(root / "plugins/context-fabric"),
            "--cache-dir", str(cache),
        ],
        env=env,
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            async def call(tool_name: str, **arguments):
                # Full-corpus cold CFM compilation of 2.4m slots can exceed the
                # ordinary five-minute MCP round-trip; bound the server worker
                # more tightly than the client so timeout errors remain useful.
                deadline = (
                    timedelta(minutes=20) if tool_name == "load_corpus"
                    else timedelta(seconds=300)
                )
                print(json.dumps({"stage": "mcp-call", "tool": tool_name}),
                      flush=True)
                response = await session.call_tool(
                    tool_name, arguments, read_timeout_seconds=deadline
                )
                return decode_mcp_result(response, tool_name=tool_name)

            installed = await call(
                "install_local_corpus",
                source=str(source),
                name="Full registered Coptic pinned TT acceptance",
            )
            rid = installed["id"]
            listing = await call(
                "list_available_corpora",
                query="Full registered Coptic pinned TT acceptance",
            )
            assert any(item.get("id") == rid for item in listing)
            prepared = await call(
                "prepare_corpus", resource_id=rid, source_mode="offline"
            )
            assert prepared.get("source_revision") == installed.get("source_revision")
            print(
                json.dumps(
                    {"stage": "context-fabric-preflight",
                     "load_preflight": prepared.get("load_preflight")},
                    sort_keys=True, default=str,
                ),
                flush=True,
            )
            loaded = await call(
                "load_corpus", resource_id=rid, source_mode="offline",
                features=["norm", "lemma", "pos", "source_record_id"],
                max_compile_minutes=18,
            )
            logical_name = loaded["logical_name"]
            description = await call("describe_corpus", corpus=logical_name)
            assert description, "Context-Fabric could not describe full native TF"
            count = await call(
                "search", corpus=logical_name, template="word",
                return_type="count",
            )
            assert count is not None, "Context-Fabric did not return a query result"
            await call("unload_corpus", logical_name=logical_name)
            removed = await call("remove_cached_corpus", resource_id=rid)
            assert removed.get("complete"), removed
            print(
                json.dumps(
                    {"stage": "context-fabric", "loaded": True, "queried": True,
                     "unloaded": True, "removed": True,
                     "resource_id": rid},
                    sort_keys=True,
                ),
                flush=True,
            )


def main() -> None:
    output = Path(os.environ["COPTIC_FULL_OUTPUT"])
    install_root = Path(os.environ["COPTIC_INSTALL_ROOT"])
    tf_dir = validate_registered_output(output, install_root)
    asyncio.run(verify_context_fabric(tf_dir))
    print("PASS full registered pinned Coptic Git → native TF → Context-Fabric", flush=True)


if __name__ == "__main__":
    main()
