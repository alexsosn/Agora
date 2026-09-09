from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agora_install_materializer as installer
from test_materializer_execution_identity_research import (
    _plugin,
    _populate,
    _registry,
    _tree_inventory,
)


def _json_differences(left, right, path: str = "$") -> list[dict]:
    if type(left) is not type(right):
        return [{"path": path, "left": left, "right": right}]
    if isinstance(left, dict):
        rows: list[dict] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left:
                rows.append({"path": child, "left": "<missing>", "right": right[key]})
            elif key not in right:
                rows.append({"path": child, "left": left[key], "right": "<missing>"})
            else:
                rows.extend(_json_differences(left[key], right[key], child))
        return rows
    if isinstance(left, list):
        if len(left) != len(right):
            return [{"path": path + ".length", "left": len(left), "right": len(right)}]
        rows: list[dict] = []
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            rows.extend(_json_differences(left_item, right_item, f"{path}[{index}]"))
        return rows
    if left != right:
        return [{"path": path, "left": left, "right": right}]
    return []


def _printable_strings(data: bytes) -> set[str]:
    values = {
        match.decode("ascii", errors="replace")
        for match in re.findall(rb"[\x20-\x7e]{6,}", data)
    }
    for match in re.findall(rb"(?:[\x20-\x7e]\x00){6,}", data):
        try:
            values.add(match.decode("utf-16le"))
        except UnicodeDecodeError:
            pass
    return values


def _byte_diff_summary(left: bytes, right: bytes) -> dict:
    common = min(len(left), len(right))
    differing_indices = [index for index in range(common) if left[index] != right[index]]
    if len(left) != len(right):
        differing_indices.extend(range(common, max(len(left), len(right))))

    ranges: list[tuple[int, int]] = []
    for index in differing_indices:
        if ranges and index == ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], index + 1)
        else:
            ranges.append((index, index + 1))

    samples = []
    for start, end in ranges[:32]:
        sample_end = min(end, start + 48)
        samples.append(
            {
                "start": start,
                "end": end,
                "left_hex": left[start:sample_end].hex(),
                "right_hex": right[start:sample_end].hex(),
            }
        )

    left_strings = _printable_strings(left)
    right_strings = _printable_strings(right)
    return {
        "left_size": len(left),
        "right_size": len(right),
        "differing_byte_count": len(differing_indices),
        "differing_range_count": len(ranges),
        "first_ranges": samples,
        "left_only_strings": sorted(left_strings - right_strings)[:50],
        "right_only_strings": sorted(right_strings - left_strings)[:50],
    }


class MaterializerExecutionIdentityResearchDetailProbe(unittest.TestCase):
    def test_inventory_pip_report_and_binary_launcher_drift(self):
        """Classify every remaining path-sensitive current-install difference."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = _registry(root / "materializers.yaml")
            targets: list[Path] = []

            with mock.patch.object(installer, "_checkout", side_effect=_populate):
                for name in ("install-detail-a", "install-detail-b"):
                    target = installer.install_materializer(
                        "research-probe",
                        install_root=root / name,
                        registry_path=registry,
                        approve_code_execution=True,
                    )
                    self.assertTrue(installer._environment_current(_plugin(), target))
                    targets.append(target)

            left_target, right_target = targets
            left_runtime = left_target / "runtime"
            right_runtime = right_target / "runtime"
            left_inventory = _tree_inventory(left_runtime)
            right_inventory = _tree_inventory(right_runtime)
            all_paths = sorted(set(left_inventory) | set(right_inventory))
            differing_paths = [
                rel
                for rel in all_paths
                if left_inventory.get(rel) != right_inventory.get(rel)
            ]

            binary_details = {}
            for rel in differing_paths:
                left_path = left_runtime / rel
                right_path = right_runtime / rel
                if not left_path.is_file() or not right_path.is_file():
                    continue
                left_bytes = left_path.read_bytes()
                right_bytes = right_path.read_bytes()
                try:
                    left_bytes.decode("utf-8")
                    right_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    binary_details[rel] = _byte_diff_summary(left_bytes, right_bytes)

            left_report = json.loads((left_target / installer.PIP_REPORT).read_text(encoding="utf-8"))
            right_report = json.loads((right_target / installer.PIP_REPORT).read_text(encoding="utf-8"))
            pip_differences = _json_differences(left_report, right_report)

            diagnostic = {
                "differing_runtime_paths": differing_paths,
                "pip_report_differences": pip_differences,
                "binary_runtime_differences": binary_details,
            }
            print("EXECUTION_IDENTITY_RESEARCH_DETAIL=" + json.dumps(diagnostic, sort_keys=True))

            self.assertTrue(pip_differences, diagnostic)
            self.assertTrue(
                any("agora-materializer-build-" in json.dumps(row) for row in pip_differences),
                diagnostic,
            )
            for rel in differing_paths:
                if rel.lower().endswith(".exe"):
                    self.assertIn(rel, binary_details, diagnostic)
                    self.assertGreater(binary_details[rel]["differing_byte_count"], 0)


if __name__ == "__main__":
    unittest.main()
