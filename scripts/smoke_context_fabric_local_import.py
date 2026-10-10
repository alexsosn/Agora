"""Real stdio MCP smoke for user-local TF import and module composition.

Run with the locked Context-Fabric runtime's Python. All artifacts are temporary.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Support both `python scripts/smoke_context_fabric_local_import.py` and
# `python -m scripts.smoke_context_fabric_local_import`.
if __package__:
    from .context_fabric_mcp_result import decode_mcp_result
else:
    from context_fabric_mcp_result import decode_mcp_result

ROOT = Path(__file__).resolve().parents[1]


async def smoke():
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        source = base / 'source'
        source.mkdir()
        files = {
            'otype.tf': '@node\n@valueType=str\n\n1-2\tword\n3\tdocument\n',
            'oslots.tf': '@edge\n\n3\t1-2\n',
            'otext.tf': '@config\n@sectionTypes=document\n@sectionFeatures=title\n@fmt:text-orig-full={norm} \n\n',
            'norm.tf': '@node\n@valueType=str\n\n1\tⲡⲉ\n2\tⲣⲱⲙⲉ\n',
            'title.tf': '@node\n@valueType=str\n\n3\tsample\n',
        }
        for name, text in files.items():
            (source / name).write_text(text, encoding='utf-8')
        module = base / 'module'
        module.mkdir()
        (module / 'lemma.tf').write_text('@node\n@valueType=str\n\n1\tⲡⲉ\n', encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'plugins/context-fabric/src'),
                   AGORA_CORPUS_MIN_FREE_GB='0')
        parameters = StdioServerParameters(command=sys.executable, args=[
            '-m', 'agora_context_fabric.server', '--cache-dir', str(base / 'cache')], env=env)
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()

                async def call(tool_name, **arguments):
                    result = await session.call_tool(tool_name, arguments, read_timeout_seconds=timedelta(seconds=120))
                    return decode_mcp_result(result, tool_name=tool_name)

                installed = await call('install_local_corpus', source=str(source), name='Local Coptic smoke')
                rid = installed['id']
                prepared = await call('prepare_corpus', resource_id=rid, source_mode='offline')
                annotation = await call('install_local_corpus', source=str(module), name='Local annotation',
                                        parent=rid, parent_version=prepared['version'],
                                        parent_revision=prepared['source_revision'])
                loaded = await call('load_corpus', resource_id=rid, modules=[annotation['id']],
                                    source_mode='offline', features=['norm', 'title', 'lemma'])
                name = loaded['logical_name']
                overview = await call('describe_corpus', corpus=name)
                result = await call('search', corpus=name, template='word', return_type='count')
                await call('unload_corpus', logical_name=name)
                removed = await call('remove_cached_corpus', resource_id=rid)
                if not removed['complete']:
                    raise RuntimeError('unloaded local import could not be removed')
                if removed.get('dependent_resource_ids') != [annotation['id']]:
                    raise RuntimeError('local parent removal did not cascade to its module')
                remaining = await call('list_available_corpora', kind='feature-module')
                if any(item.get('id') == annotation['id'] for item in remaining):
                    raise RuntimeError('removed local module remains discoverable')
                print(json.dumps({'loaded': True, 'overview': overview, 'search': result,
                                  'removed': removed['complete']}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(smoke())
