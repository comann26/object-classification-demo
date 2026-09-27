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
| 7 | Object-to-person linker | ✅ done | `4a9e885` | 85 |
| 8 | Scorer, bands, confidence, templates | ✅ done | `fb05d97` | 101 |
| 9 | Session engine and emission rules | ✅ done | `d7e51fb` | 114 |
| 10 | Step-down, idle stop, stills | ✅ done | `770cb87` | 120 |
| 11 | Camera listing and permissions | ✅ done | `c025bfe` | 122 (unit) |
| 12 | Server routes | ✅ done | `a7efd6e` | 159 |
| 13 | Local-server security | ✅ done | `9f739f1` | 185 |
| 14 | Launch entry point | ✅ done | `fcac433` | 200 |
| 15 | Model manifest and YOLO-World detector | ✅ done | `af0ff19` | 211 |
| 16 | Torch variants, setup step, launchers | 🔨 in progress | | |
| 17 | Web scaffold, theme, types, API client | ✅ done (web lane) | `4890621` | 19 (web) |
| 18 | Operator controls, video, zone, status | ✅ done (web lane) | `cd83d57` | 33 (web) |
| 19 | Event feed, evidence, alert, settings, history | ✅ done (web lane, merged `5c7b104`) | `908812b` | 53 (web) |
| 20 | Continuous integration | 📝 TODO (skipped this session at the user's request; spec in design.md §5) | | |
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

### Task 7: Object-to-person linker (`4524325`, fixed in `4a9e885`)
- **What exists now:** `demo/linker.py` decides which person is holding which threat object.
  - Overlap is measured against the object's own area, with the person's box widened slightly to reach raised hands.
  - A link forms after 0.5 s of overlap, and the largest overlap wins.
  - A link transfers to another person only after they hold the object for the full 0.5 s.
  - A link breaks after 1 s apart while the object is visible.
  - While the object is out of view, the link is held and fades over 3 s. Strength is overlap × duration × fade.
  - "Unattended" time is tracked for objects with no holder.
- **Review, then fix round 1:**
  - When an object reappeared away from its holder, the link sometimes broke instantly and sometimes lingered, depending on leftover timing. It now follows the spec: it resumes only if the object reappears overlapping the same person, and otherwise breaks immediately.
  - When a person's or object's track restarts (a tracker ID switch), the link now carries over instead of being lost.
- **Held for final review:** minor bookkeeping cleanups.

### Task 18: Operator controls, video, zone, status (`d391fa3`, fixed in `cd83d57`, branch `web-lane`)
- **What exists now:**
  - Threat-word input with inline validation, a camera dropdown, a per-session Save stills switch with a "Recording stills" badge, and Go / Stop / Quit.
  - Inputs reset after each Go.
  - Live video with click-to-draw zone, plus Apply zone and Clear zone.
  - A status bar that polls `/health` every second.
  - Server error messages are shown word for word. Quit shows "Demo closed — you can close this tab".
- **Review, then fix round 1:**
  - Stop, Quit and Apply zone failed silently. They now show errors and don't pretend to succeed.
  - The buttons, switch and badge had been hand-built. They are now real shadcn/ui components, which keeps the same libraries as Omega.
- **Held for final review:** there is no test for Clear zone's error path.

### Task 8: Scorer, bands, confidence, templates (`fb05d97`)
- **What exists now:** `demo/scorer.py` turns what the pipeline saw into a threat score with an itemised receipt.
  - +55 per held object; +30 for an unattended object; +25 inside the zone; +15 for loitering; up to +20 combined for approaching and running; −5 each for moving away or leaving the zone.
  - Each line is rounded to a whole number, and the lines always add up exactly to the score. A "Capped at …" line explains any clamp at 0 or 100.
  - Bands (low, medium, high, critical) use 5-point hysteresis so they don't flicker.
  - Confidence is the mean of detector certainty, track stability and image quality, and it never changes the threat score.
  - Plain-English summaries such as "Person 7 is holding a knife and moving closer." come from fixed templates.
  - The spec's worked example (58, high, confidence 0.80) is reproduced exactly by a test.
- **Review:** clean.
- **Held for final review:** two extra edge-case tests.

### Task 9: Session engine and emission rules (`b6f8310`, fixed in `d7e51fb`)
- **What exists now:** `demo/session.py` (with helpers in `demo/session_parts.py`) and `demo/testing.py`. This is the first end-to-end pipeline:
  - frames go through detect → track → motion → link → score → events;
  - each event is written to the hash-chained log and pushed to browsers;
  - the video preview is annotated.
- **Behaviour:**
  - Events are emitted when a track becomes eligible, when its band changes, when a link forms or breaks, as heartbeats every 2 s while above low, and when a track ends.
  - Stop is thread-safe. `session.ended` is always the last line, and the log verifies.
- **Review, then fix round 1:**
  - The knife-timing test now measures from the knife's first appearance, so it would catch a late link.
  - "Poor image" now also covers low fps and sudden scene changes.
- **Rulings made:**
  - The zone and loitering rules apply to people only (an unattended knife keeps its +30).
  - Stopping a session closes out its live tracks.
  - A second Stop waits for the first to finish, which avoids a camera race on Windows.
  - Harmless OpenCV fault messages are silenced in test output.
- **Held for final review:** join-timeout edge cases and extra coverage.

### Task 19: Event feed, evidence, alert, settings, history (`046f2a4`, fixed in `908812b`, branch `web-lane`)
- **What exists now:**
  - A live event feed and an evidence panel. The panel shows the summary, a signed contribution per rule, supporting and contradictory tags, confidence dimensions, unknowns, and each band's name as text as well as colour.
  - A critical alert: a red banner plus an 880 Hz tone, played once each time a track enters critical, with a remembered mute.
  - A settings drawer with sliders generated from the config schema (`schemas/ScoringConfig.json`), plus Save and Reset to defaults.
  - A history drawer that replays past sessions.
  - The production build is committed in `web/dist/`, so users never need Node.
- **Review, then fix round 1:**
  - The history list's field name now matches the planned server API (`ended_normally`).
  - The alarm no longer sounds when replaying a past session.

### Web lane merged (`5c7b104`)
- Tasks 17–19 were merged into the feature branch cleanly. After the merge, all 120 Python tests and 53 web tests pass, and the generated types are in sync.

### Task 10: Step-down, idle stop, stills (`8f8dc3e`, fixed in `770cb87`)
- **What exists now:**
  - **Step-down (`demo/stepdown.py`):** on slow machines, the model and input size step down (large → small, then 640 → 480 → 320) when the frame rate stays under 10 fps for 5 s. Each change is logged as a `pipeline.changed` event.
  - **Idle stop:** the session stops itself after 30 s with no page watching, so the camera isn't left on.
  - **Stills (`demo/stills.py`):** when Save stills is on, a still is saved as a track enters high or critical, and its SHA-256 goes into that event.
- **Review, then fix round 1:**
  - The idle check now uses the session's own clock, so a mismatched clock from the server can't disable it.
  - Two tests that could flake on slow machines are fixed.

### Task 11: Camera listing and permissions (`c025bfe`)
- **What exists now:** `demo/cameras.py`.
  - Cameras are listed by name without opening them, so there's no camera light and no permission prompt. It uses AVFoundation on macOS and DirectShow on Windows. It found this machine's real webcam.
  - The macOS permission status is checked, and access is requested when needed.
  - Camera failures map to the exact on-screen messages from the spec: denied, Windows privacy switch, busy, missing.
- **Review:** clean. The message text was compared character for character against the spec.
- **Still to verify on real machines:** that the listed order matches OpenCV's camera numbering (Task 23).

### Task 12: Server routes (`09f41d6`, fixed in `a7efd6e`)
- **What exists now:** `demo/server.py`, a FastAPI app that serves the built React page and these routes:
  - Go, Apply zone, Stop and Quit;
  - the MJPEG `/video` stream and the `/events` WebSocket;
  - `/health`, `/cameras` and `/config` (with validation);
  - `/sessions` and the per-session event history.
- **How it behaves:**
  - Only one Go runs at a time.
  - Blocking work runs off the event loop.
  - Camera errors return the exact on-screen message.
  - An open browser tab keeps the session from idling out.
- **Review, then fix round 1.** Cross-checking against the already-built page found:
  - The Quit button would always show "Could not quit", because the server replied with an empty body. Fixed.
  - The video froze after Apply zone. The stream now follows the new session.
  - The history list showed "low" for every past session. `session.ended` now records the session's peak band (event format 1.1, an additive change), and the live peak tracker was deleted.
  - Smaller fixes: frame encoding moved off the event loop, clean WebSocket disconnects, Quit/Go race closed, and test-output noise removed.

### Task 13: Local-server security (`4347f4b`, fixed in `9f739f1`)
- **What exists now:** three layers protect the local server from other websites open in the same browser.
  - A **Host allowlist** (127.0.0.1 / localhost) blocks DNS rebinding.
  - An **Origin check** blocks cross-site POSTs and WebSockets.
  - A **random launch token** is required on every route except the page itself, its static files and the favicon.
- **Tests:** the missing-token test builds its list from the app's own routes, so any route added later is covered automatically.
- **Adversarial review:** no bypass found. The attempts included path traversal and encoding tricks, look-alike and `null` origins, preflight requests, query-key tricks, and a WebSocket from a foreign host. No token leaks were found in the server or the page.
- **Fix round 1:**
  - A token with non-English characters crashed the check (500 error). The check now compares bytes and returns a clean 403.
  - The favicon no longer needs the token.

### Task 14: Launch entry point (`fcac433`)
- **What exists now:** `python -m demo` (`demo/__main__.py`) does the following:
  - pins every library cache and setting inside the demo folder before any heavy library loads;
  - picks port 8000 or the next free one;
  - creates a random launch token;
  - writes `run/demo.lock`, so a second launch reopens the running demo instead of starting another;
  - starts the server on 127.0.0.1 only, with no access log so tokens never reach the logs;
  - opens the browser once the server is ready.
- **Camera first:** the production session factory opens the camera **before** creating a session. A camera error then leaves no stray "error" session in the history.
- **Review:** clean. The first reviewer stalled and was replaced; the stall was not caused by this task's tests.
- **Held for final review:** a few untested fallback branches and edge cases in the lock handling.

### Task 15: Model manifest and YOLO-World detector (`e8bd235`, fixed in `af0ff19`)
- **What exists now:**
  - `demo/models.py`: a pinned manifest (URL, SHA-256 and size for the small and large YOLO-World models and the CLIP text model), verification, and a download-to-`.part`-then-verify step.
  - `YoloWorldDetector` in `demo/detector.py`, with a real large→small model swap when the session steps down.
  - The launcher now builds the real detector.
- **Fully offline after setup:**
  - CLIP is pinned by a hashed archive URL and loads from `models/`.
  - Ultralytics is pinned to an exact version (8.4.163).
  - A test runs the real model with the network blocked and fails on any download, pip install or stray file. Removing the CLIP fix makes it fail on a real DNS lookup, so the test is genuine.
- **Bug found:** Ultralytics wrote a settings folder into the current directory. Fixed.
- **Measured on this laptop's CPU** (i7-13620H, detector only): 11.6 fps at 640 px, 18.0 at 480, 30.5 at 320. See `docs/knowledge/`.
- **Review, then fix round 1:**
  - All model files, including the small step-down model, are now verified before a session starts. Previously a missing file could have triggered a download mid-session.
  - Missing or damaged model errors now show a plain message instead of "500" and a stack trace.
  - CLIP loading was simplified to Ultralytics' own constructor.
