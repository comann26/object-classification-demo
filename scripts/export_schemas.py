"""Export JSON Schemas for the wire request and event models.

Usage:
    python scripts/export_schemas.py            # write schemas/*.json
    python scripts/export_schemas.py --check     # exit 1 if any file would change
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import TypeAdapter  # noqa: E402

from demo.contracts import Event, SessionRequest, ZoneRequest  # noqa: E402

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

_MODELS = {
    "SessionRequest": SessionRequest.model_json_schema,
    "ZoneRequest": ZoneRequest.model_json_schema,
    "Event": lambda: TypeAdapter(Event).json_schema(),
}


def _render(schema: dict) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    check = "--check" in args
    drift = False
    for name, get_schema in _MODELS.items():
        content = _render(get_schema())
        path = SCHEMAS_DIR / f"{name}.json"
        if check:
            existing = path.read_text(encoding="utf-8") if path.exists() else None
            if existing != content:
                print(f"schema drift: {path}")
                drift = True
        else:
            SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
