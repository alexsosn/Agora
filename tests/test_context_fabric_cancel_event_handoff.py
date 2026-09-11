from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SRC = ROOT / "plugins" / "context-fabric" / "src"
if str(PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SRC))

from agora_context_fabric.operation import OperationControl, operation_scope
from agora_context_fabric.service_source_modes import (
    ContextFabricService,
    _BaseContextFabricService,
)


class CancellationEventHandoffTests(unittest.TestCase):
    def test_cancel_request_in_base_reservation_gap_is_not_lost(self):
        service = ContextFabricService.__new__(ContextFabricService)
        service._active_loads_lock = threading.RLock()
        service._active_loads = {}
        original_event = threading.Event()

        def fake_base_reserve(_self, prepared, **_kwargs):
            load_id = "fixture-load"
            # Simulate cancel_corpus_load winning immediately after the base
            # reservation becomes visible but before the subclass replaces the
            # record with the request-owned operation event.
            original_event.set()
            _self._active_loads[load_id] = {
                "cancel_event": original_event,
                "phase": "preflight",
            }
            return load_id, original_event

        operation = OperationControl(acquisition_timeout_seconds=5)
        prepared = SimpleNamespace(logical_name="bhsa")

        with (
            patch.object(
                _BaseContextFabricService,
                "_reserve_active_load",
                fake_base_reserve,
            ),
            operation_scope(operation),
        ):
            load_id, returned_event = service._reserve_active_load(prepared)

        self.assertEqual(load_id, "fixture-load")
        self.assertTrue(
            returned_event.is_set(),
            "a cancellation observed by the original active-load event must survive handoff",
        )
        self.assertIs(returned_event, operation.cancel_event)
        self.assertIs(
            service._active_loads[load_id]["cancel_event"],
            operation.cancel_event,
        )


if __name__ == "__main__":
    unittest.main()
