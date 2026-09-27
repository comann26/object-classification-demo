---
title: AGENTS.md — build guide for AI assistants
status: living
date: 2026-09-27
related:
  - docs/design.md
  - docs/requirements.md
  - README.md
---

# Object Classification Demo — for AI assistants

Webcam object detection + threat scoring. This is mostly built and maintained by AI, with the
team reviewing (see `docs/requirements.md` "Who builds it"). This file is the primary build
guide; `CLAUDE.md` is a one-line pointer to it (`@AGENTS.md`).

Read `docs/requirements.md` (what) and `docs/design.md` (how) before changing behavior.
`demo/contracts.py` is the single source of truth for wire and internal data shapes — every
stage in `demo/` exchanges only those types and never imports another stage directly.

## Environment

- Python is exactly 3.12, managed by `uv` (`UV_PYTHON_PREFERENCE=only-managed`).
- Everything the app writes at runtime (`bin/`, `.uv/`, `.venv/`, `models/`, `logs/`, `run/`,
  caches) lives inside this folder, never in the user's home.
- Offline after first setup: `YOLO_OFFLINE=1`, `YOLO_AUTOINSTALL=False`, no telemetry. Server
  binds to `127.0.0.1` only.
- Platforms are Windows and macOS only. Minimum macOS is 14 on Apple Silicon, 12 on Intel.

## Commands

There is no global `uv` assumed. If your shell has no `uv` on PATH, fetch one (see
`Start Demo.bat` / `Start Demo.command` for how the launchers pin and fetch their own) or use
a local copy such as `bin/uv.exe`, and substitute it for `uv` below. End users never run any of
these commands themselves — the launchers do the equivalent of "install" and "run" for them
with their own pinned `uv`, fetched fresh into `bin/` and never touching a `uv` already on PATH.

Install / update dependencies:
```
uv lock
uv sync --extra cpu        # or --extra cu12x on Windows with a usable NVIDIA GPU
```

Run the demo:
```
uv run python -m demo
```

Regenerate or check the generated files:
```
uv run python scripts/export_schemas.py            # schemas/*.json from demo/contracts.py
uv run python scripts/export_schemas.py --check     # fail if they've drifted
uv run ruff check .
```

Tamper-check a session log:
```
uv run python -m demo.verify_log logs/<session_id>.jsonl
```

Fetch/verify the pinned model files (what the launchers run before the app starts):
```
uv run python -m demo.setup --variant cpu|cu12x|mac
```

### Tests, by layer (docs/design.md §5)

| Layer | Command | Needs |
|---|---|---|
| 1. Unit (pure logic) | `uv run pytest tests/unit -v` | nothing |
| 2. Server/session integration | `uv run pytest tests/integration -v` | nothing (`FakeDetector` + `SyntheticSource` via `demo/testing.py`) |
| 3. Offline guarantee (real model, no network) | `uv run pytest tests/offline -v` | model files present — run `uv run python -m demo.setup --variant cpu` first |
| 4. Clip pipeline (real model, real clips) | **`tests/pipeline` — TODO, not built yet.** Design.md §5 layer 4 describes real-clip assertions (knife links, empty room is silent, apple scores unattended, handheld reports `camera_moving`, two threat words yield one link), but there is no test harness for it in this repo yet. Do not run or claim `tests/pipeline`; it does not exist. | — |
| 5. Web | `cd web && npm test -- --run` and `npm run check:types` | `npm install` in `web/` once |

Run the full unit suite before committing any change to `demo/`; run the layer(s) that cover
what you touched while iterating.

**Continuous integration:** design.md §5 specifies a GitHub Actions workflow (Windows + macOS,
layers 1/2/3/5, both drift checks, `uv lock --check`, `uv sync --frozen`, and a check that
`Start Demo.command` keeps git mode 100755). **This has not been built yet — TODO.** There is
no `.github/workflows/` in this repo. Do not claim CI runs until that task lands; run the
commands above locally instead.

## Confirm the demo is running

1. Read `run/demo.lock` — JSON: `{"pid": <int>, "port": <int>, "token": "<string>"}`.
2. `curl -H "X-Demo-Token: <token>" http://127.0.0.1:<port>/health`

A 200 with `{status, session_id, fps, camera, model, input_size, device}` means it's up and
what it's doing. A connection error means it isn't running (or the port in the lock is stale);
a 403 means the token is wrong, missing, or the lock file is stale from a previous run.

## Stage map

A single Python process, stages that exchange only `demo/contracts.py` types and never import
each other directly, plus a prebuilt static React UI.

| File | Purpose |
|---|---|
| `demo/__main__.py` | pick a port, write `run/demo.lock`, start the server, open the browser (the only place that opens it) |
| `demo/contracts.py` | Pydantic/dataclass models: `SessionConfig`, `Frame`, `Detection`, `Track`, `Link`, every `Event` type |
| `demo/config.py` | versioned scoring config — every tunable number, loaded from `config/scoring.json`, reset from `config/scoring.default.json` |
| `demo/source.py` | `Webcam` \| `VideoFile` \| `SyntheticSource` → `Frame` (with `ts`) |
| `demo/cameras.py` | list cameras by OS device name without opening one (AVFoundation on macOS, DirectShow on Windows); the camera permission flow and error messages |
| `demo/models.py` | pinned model manifest, checksum verify, one-time download, `select_model` (auto/small/large) |
| `demo/setup.py` | `python -m demo.setup --variant cpu\|cu12x\|mac`, run by the launchers before the app starts |
| `demo/detector.py` | `YoloWorldDetector` \| `FakeDetector` (tests) → `[Detection]` |
| `demo/tracker.py` | two ByteTrack instances (people, threat objects) + motion → `[Track]` |
| `demo/motion.py` | heading/speed/approach math over a track's box history, plus camera-mode (moving/fixed) detection |
| `demo/stepdown.py` | automatic model/size step-down when measured fps stays below the floor |
| `demo/health.py` | per-frame image-quality score, and `HealthMonitor` (black/frozen/blurred frame, scene change, low fps) |
| `demo/linker.py` | threat object ↔ person linking → `[Link]` |
| `demo/scorer.py` | rules + templates → `threat`, `confidence`, `evidence`, `summary`, `unknowns` |
| `demo/stills.py` | per-session still capture: write an annotated JPEG under `logs/<session_id>/` and hash it |
| `demo/events.py` | envelope, hash chain, JSONL log, WebSocket fan-out |
| `demo/verify_log.py` | `python -m demo.verify_log <file>` — the tamper check |
| `demo/session.py` | wires the stages; one `Session` per Go / Apply zone |
| `demo/session_parts.py` | pure helpers for `session.py`: zone dwell, unknowns, wire payloads, preview drawing |
| `demo/server.py` | FastAPI routes, host allowlist, Origin check, launch-token check |
| `demo/testing.py` | `make_session(source=..., detector=...)` — the sanctioned way to inject fakes, for tests only |
| `web/` | React + Vite + TypeScript UI (developers only); `src/api/types.ts` is generated from `schemas/`, never hand-written |
| `config/scoring.json` / `config/scoring.default.json` | weights, thresholds, tracker and model settings (edited by the sliders / factory reset) |
| `models/` | pinned model files + checksum manifest (git-ignored) |
| `schemas/` | JSON Schema generated from `demo/contracts.py` |
| `tests/` | pytest layers 1–3 today (`tests/unit`, `tests/integration`, `tests/offline`); `tests/pipeline` is TODO; `web/` has Vitest |
| `docs/` | this file's companions — requirements, design, setup guide, release checklist, knowledge notes |

## Conventions

- Internal pipeline types (`Frame`, `Detection`, `Track`, `Link`) are plain frozen dataclasses
  — `Frame` carries a numpy array, which Pydantic doesn't validate well. Wire/event types
  (requests, events) are Pydantic v2 models, matching `docs/design.md` §2 field-for-field and
  exported to `schemas/`.

## Rules

- **Contracts first.** `demo/contracts.py` is the source of truth. Change it, regenerate
  `schemas/` and `web/src/api/types.ts`, then change the stages that use the new shape.
- **Product decisions go in `../scrye-docs`**, not here. If a change would alter what counts as
  a threat, what data Guardian Intelligence expects, or anything civil-liberty-adjacent, write
  that decision in `scrye-docs` first, then change this repo's code to match. This repo's docs
  link to those decisions; they don't restate them.
- **A field that is always the same value is dropped** from the wire format (docs/design.md §2).
- **All rule durations are in seconds of `Frame.ts`**, never frame counts or wall-clock time.
- **Every number marked *config* in the spec lives in `config/scoring.json`**, never hard-coded.
- **`summary` and `evidence[].text` come from fixed templates** in `scorer.py`. No LLM.
- **TDD:** write the failing test first, then implement. Code, tests, and affected docs go in
  the same commit.
- **Definition of done for any change:**
  - Code, tests, and affected docs are in the same commit.
  - A new learning gets a `docs/knowledge/` note (see `docs/knowledge/README.md` for the
    template — *observed*, *evidence*, *implication*).
  - A product-level change goes to `scrye-docs` first.
  - `docs/build-log.md` is updated when a task finishes.

## Where each kind of change goes

| Kind of change | Where |
|---|---|
| A new wire field or event type | `demo/contracts.py` → regenerate `schemas/` and `types.ts` → the stage(s) that produce/consume it |
| A scoring rule or weight | `demo/scorer.py` (logic) + `config/scoring.json` / `config/scoring.default.json` (the numbers) — never hard-code a *config* number |
| A new detector/source/scorer implementation | one new file behind the existing protocol; stages never import each other directly |
| A camera or setup error message | `demo/cameras.py` `MESSAGES` or `demo/models.py` / `demo/setup.py` — and update `docs/setup-guide.md`'s troubleshooting table in the same commit (a test checks every message string appears there) |
| A UI component or interaction | `web/src/components/` (Tailwind v4, shadcn/ui, lucide-react, vaul; neutral branding — "Object Classification Demo") |
| A measured fact (fps, checksum quirk, camera index ordering, offline gotcha) | `docs/knowledge/<YYYY-MM-DD>-<topic>.md` |
| What counts as a threat, Guardian integration, civil-liberty limits | `../scrye-docs` first, this repo second |
| A finished task | `docs/build-log.md` |
