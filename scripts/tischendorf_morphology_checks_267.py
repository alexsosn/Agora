"""Shared, dependency-free node-ID bounds contract for Tischendorf TF 2.8.

Do not import the Context-Fabric MCP service here. Foundation's bounded
unittest suite deliberately tests this check without installing its runtime.
"""
from __future__ import annotations

from numbers import Integral


def valid_feature_node_id(node: object) -> bool:
    """Accept Python/NumPy integer node IDs, not bool, strings, or overflow."""
    return isinstance(node, Integral) and not isinstance(node, bool) and 1 <= int(node) <= 152_077
