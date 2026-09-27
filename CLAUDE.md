# Object Classification Demo

Webcam object detection + threat scoring. See `docs/requirements.md` (what) and `docs/design.md`
(how) for the spec. `demo/contracts.py` is the single source of truth for wire and internal data
shapes; every stage in `demo/` exchanges only those types.

## Environment

- Python is exactly 3.12, managed by uv. Use `bin/uv.exe` (downloaded into this worktree,
  git-ignored) — there is no global uv on this machine.
- Everything the app writes at runtime (`bin/`, `.uv/`, `.venv/`, `models/`, `logs/`, `run/`,
  caches) lives inside this folder, never in the user's home.
- Offline after first setup: `YOLO_OFFLINE=1`, `YOLO_AUTOINSTALL=False`, no telemetry. Server
  binds to `127.0.0.1` only.

## Commands

- `bin/uv.exe lock` — resolve dependencies
- `bin/uv.exe sync` — install dependencies into `.venv`
- `bin/uv.exe run pytest tests/unit -v` — run unit tests
- `bin/uv.exe run python scripts/export_schemas.py` — regenerate `schemas/*.json` from `demo/contracts.py`
- `bin/uv.exe run python scripts/export_schemas.py --check` — fail if the schemas have drifted
- `bin/uv.exe run ruff check .` — lint

## Conventions

- Internal types (`Frame`, `Detection`, `Track`, `Link`) are plain frozen dataclasses — `Frame`
  carries a numpy array, which Pydantic doesn't validate well. Wire types (requests, events) are
  Pydantic v2 models, matching `docs/design.md` §2 field-for-field.
- A field that is always the same value is dropped from the wire format.
- All rule durations are in seconds of `Frame.ts`, never frame counts or wall-clock time.
- Numbers marked *config* in the spec live in `config/scoring.json`, never hard-coded.
- TDD: write the failing test first, then implement.
