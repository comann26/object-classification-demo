"""Tamper check: recompute the event-log hash chain and report the result.

CLI: `python -m demo.verify_log <file>` — prints the message, exits 0 if OK
else 1. See docs/design.md §4 "Tamper check".
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from demo.events import GENESIS, event_hash


@dataclass(frozen=True, slots=True)
class VerifyResult:
    ok: bool
    first_broken_line: int | None
    truncated: bool
    message: str


def verify(path: Path) -> VerifyResult:
    lines = Path(path).read_bytes().split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()  # trailing newline

    prev_hash = GENESIS
    last_type: str | None = None
    for line_no, raw in enumerate(lines, start=1):
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if line_no == len(lines):
                return VerifyResult(False, None, True, "truncated or crashed")
            return VerifyResult(False, line_no, False, f"broken at line {line_no}")

        provenance = event.get("provenance", {})
        if provenance.get("prev_hash") != prev_hash or provenance.get("hash") != event_hash(
            event
        ):
            return VerifyResult(False, line_no, False, f"broken at line {line_no}")

        prev_hash = provenance["hash"]
        last_type = event.get("type")

    if last_type != "session.ended":
        return VerifyResult(False, None, True, "truncated or crashed")
    return VerifyResult(True, None, False, "OK")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    result = verify(Path(argv[0]))
    print(result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
