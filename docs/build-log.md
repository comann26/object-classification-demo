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
| 6 | Tracker (dual ByteTrack) and motion maths | ✅ done | `6a4f504` | 69 |
| 7 | Object-to-person linker | 🔨 in progress | | |
| 8 | Scorer, bands, confidence, templates | ⏳ | | |
| 9 | Session engine and emission rules | ⏳ | | |
| 10 | Step-down, idle stop, stills | ⏳ | | |
| 11 | Camera listing and permissions | ⏳ | | |
| 12 | Server routes | ⏳ | | |
| 13 | Local-server security | ⏳ | | |
| 14 | Launch entry point | ⏳ | | |
| 15 | Model manifest and YOLO-World detector | ⏳ | | |
| 16 | Torch variants, setup step, launchers | ⏳ | | |
| 17 | Web scaffold, theme, types, API client | ✅ done (web lane) | `4890621` | 19 (web) |
| 18 | Operator controls, video, zone, status | 🔨 in progress (web lane) | | |
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

### Task 6: Tracker (dual ByteTrack) and motion maths (`13bf29a`, fixed in `6a4f504`)
- **What exists now:**
  - `demo/tracker.py`: separate trackers for people and threat objects, with our own stable track IDs, hit ratios measured in seconds, eligibility rules, restart detection and bounded history.
  - `demo/motion.py`: on-screen heading and direction label, speed in body heights per second, approach from box-width growth, cut-off-by-frame-edge detection, and fixed/moving camera detection from background optical flow.
- **Finding during the build:** ByteTrack could never track low-likelihood objects such as a knife seen at 0.18, because of its internal thresholds. The workaround passes detections at or above our threshold to ByteTrack at full confidence, while each `Track` keeps the real likelihood. The review verified that the tracker's two-stage matching still works.
- **Review, then fix round 1:**
  - Heading and speed were distorted on widescreen (16:9 / 4:3) cameras. A sideways runner was under-scored. They are now aspect-corrected, and the session must pass `frame.width / frame.height`.
  - The "track restarted" rule could wrongly link a newcomer to a person still in view. It now processes existing tracks first, with a regression test.
- **Held for final review:**
  - tracks start one frame late after the first frame;
  - an exact-threshold float comparison;
  - a zero smoothing window;
  - `supervision` is pinned below 0.31 (follow-up: move to the `trackers` package).

### Task 17: Web scaffold, theme, types, API client (`d8dfc43`, fixed in `4890621`, branch `web-lane`)
- **What exists now:**
  - The Vite + React + TypeScript app in `web/`: Tailwind v4 with Omega's exact dark theme tokens, shadcn/ui set up, and self-hosted fonts (no Google Fonts calls).
  - `npm run gen:types` generates TypeScript types from `schemas/`, and `check:types` catches drift.
  - The API client sends the launch token on every request.
  - Threat-word parsing mirrors the Python rules exactly.
  - Zone-click mapping works through letterboxing for 4:3 and portrait cameras.
- **Review, then fix round 1:** the type drift check would falsely fail on a fresh Windows clone because of CRLF line endings. It now normalizes them, and a test covers it.
- **Held for final review:**
  - the untested top/bottom letterbox branch;
  - an emoji length edge case;
  - the drift test temporarily rewrites the real `types.ts`.
