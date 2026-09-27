"""Event log helpers. Extended by Task 3 (event writing, hash chain)."""

from __future__ import annotations

import json


def canonical_json(obj: dict) -> bytes:
    """Deterministic JSON bytes: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
