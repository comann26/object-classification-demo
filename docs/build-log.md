---
title: Build log
status: in progress
date: 2026-09-26
related:
  - superpowers/plans/2026-09-26-object-classification-demo.md
  - design.md
  - requirements.md
---

# Build log

The record of what has been built, task by task, against the [implementation plan](superpowers/plans/2026-09-26-object-classification-demo.md). This file is updated whenever a task passes its independent review.

**How tasks are built.** Each task is written test-first by a fresh AI implementer. An independent reviewer then checks it against the spec and for code quality. Minor findings are held for the final whole-branch review.

**Lanes.**
- The Python lane runs in order on branch `worktree-feat-demo`.
- The web UI lane (Tasks 17–19) runs in parallel on branch `web-lane`. It is merged back after Task 19.

## Status

| # | Task | Status | Commit | Tests (cumulative) |
|---|---|---|---|---|
| 1 | Project scaffold, data contracts, schema export | ✅ done | `7052f51` | 15 |
| 2 | Scoring config | ✅ done | `bb6f417` | 20 |
| 3 | Hash-chained event log, fan-out, `verify_log` | ✅ done | `f9c15f5` | 29 |
| 4 | Frame sources and image health | ✅ done | `f34e895` | 42 |
| 5 | Detector protocol, fake detector, threat NMS | ✅ done | `def5109` | 47 |
| 6 | Tracker (dual ByteTrack) and motion maths | 🔨 in progress | | |
| 7 | Object-to-person linker | ⏳ | | |
| 8 | Scorer, bands, confidence, templates | ⏳ | | |
| 9 | Session engine and emission rules | ⏳ | | |
| 10 | Step-down, idle stop, stills | ⏳ | | |
| 11 | Camera listing and permissions | ⏳ | | |
| 12 | Server routes | ⏳ | | |
| 13 | Local-server security | ⏳ | | |
| 14 | Launch entry point | ⏳ | | |
| 15 | Model manifest and YOLO-World detector | ⏳ | | |
| 16 | Torch variants, setup step, launchers | ⏳ | | |
| 17 | Web scaffold, theme, types, API client | 🔨 in progress (web lane) | | |
| 18 | Operator controls, video, zone, status | ⏳ (web lane) | | |
| 19 | Event feed, evidence, alert, settings, history | ⏳ (web lane) | | |
| 20 | Continuous integration | ⏳ | | |
| 21 | Clip pipeline tests | ⏳ (needs recorded clips) | | |
| 22 | Documentation | ⏳ | | |
| 23 | Acceptance run and release check | ⏳ (human-run) | | |

## Completed tasks

### Task 1: Project scaffold, data contracts, schema export (`7052f51`)
- **What exists now:**
  - `pyproject.toml` / `uv.lock` (Python 3.12), plus `.gitignore` and `.gitattributes` (test clips go through Git LFS and are excluded from the zip).
  - `demo/contracts.py`, which defines every data type:
    - internal frame, detection, track and link types;
    - request validation, including the threat-word rules and the "People are always tracked" rejection;
    - all six event types.
  - `scripts/export_schemas.py` generates `schemas/*.json` and has a drift check.
- **Review:** clean. The direction and camera-mode labels were confirmed against Task 6.

### Task 2: Scoring config (`bb6f417`)
- **What exists now:**
  - `demo/config.py` with `config/scoring.json` and `config/scoring.default.json`. Every tunable number from the spec is here, with bounds that the settings sliders will use.
  - `config_sha256`, which fingerprints the config for event provenance.
- **Review:** clean.
- **Held for final review:** there are no tests yet for the unknown-key and brightness-range checks.

### Task 3: Hash-chained event log, fan-out, `verify_log` (`f9c15f5`)
- **What exists now:**
  - The tamper-evident JSONL event log. Each line's hash covers the previous line's.
  - A non-blocking fan-out to browser tabs, where a stalled tab drops old events instead of freezing the demo.
  - `python -m demo.verify_log <file>`, which reports "OK", "broken at line N" or "truncated or crashed".
- **Review:** clean. The threaded fan-out path was verified manually.
- **Held for final review:** that threaded path has no automated test yet.

### Task 4: Frame sources and image health (`f34e895`)
- **What exists now:**
  - The `SyntheticSource`, `VideoFile` and `Webcam` frame sources. The first two use video time, so tests behave the same on fast and slow machines.
  - Image-quality scoring (brightness, sharpness).
  - Camera health signals: black, frozen, blurred, scene change, low fps. Each is reported once when it starts.
- **Review:** clean.
- **Held for final review:** small tidy-ups.

### Task 5: Detector protocol, fake detector, threat NMS (`def5109`)
- **What exists now:**
  - The `Detector` interface, which the real YOLO-World model plugs into later.
  - A `FakeDetector` for tests.
  - Threat-class de-duplication, so one prop matching both "knife" and "gun" counts once.
  - Per-class minimum likelihoods.
- **Review:** clean.
