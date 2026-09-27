---
title: Demo design
status: in review
date: 2026-09-26
related:
  - requirements.md
  - ../../scrye-docs/decisions/2026-09-26-camera-threat-scoring.md
  - ../../scrye-docs/research/2026-09-26-sensor-data-standards.md
---

# Demo design

How the demo meets [requirements.md](requirements.md). All sections were approved. This revision includes the fixes from the adversarial review of 2026-09-26 (19 findings); see [Review log](#review-log). All numbers marked *config* live in `config/scoring.json`.

| # | Section | Status |
|---|---|---|
| 1 | Architecture and components | approved, revised after review |
| 2 | Data format | approved, revised after review |
| 3 | Pipeline logic | approved, revised after review |
| 4 | Error handling, security, privacy, offline | approved, revised after review |
| 5 | Testing | approved, revised after review |
| 6 | Documentation and setup guides | approved, revised after review |

## 1. Architecture and components

A single Python process built as independent stages, with a React UI served as prebuilt static files.

```
Start Demo.bat / Start Demo.command   → bootstrap pinned uv into ./bin, then `uv run --frozen --extra <variant> python -m demo`
demo/
  __main__.py   pick port, write lock file, start server, open the browser (the ONLY place that opens it)
  contracts.py  Pydantic models: SessionConfig, Frame, Detection, Track, Link, every Event type
  source.py     Webcam | VideoFile | SyntheticSource   → Frame (with ts)
  cameras.py    list cameras by name without opening them (AVFoundation on macOS, DirectShow on Windows)
  detector.py   YoloWorldDetector | FakeDetector (tests) → [Detection]
  tracker.py    two ByteTrack instances (people, threat objects) + motion → [Track]
  linker.py     threat object ↔ person                → [Link]
  scorer.py     rules + templates                     → threat, confidence, evidence, summary, unknowns
  events.py     envelope, hash chain, JSONL log, WebSocket fan-out
  verify_log.py `python -m demo.verify_log <file>`
  session.py    wires the stages; one Session per Go / Apply zone
  server.py     FastAPI (routes below)
  testing.py    make_session(source=..., detector=...) for tests only
web/                          React + Vite + TypeScript (developers only)
  src/api/types.ts            generated from schemas/, never hand-written
  src/components/             VideoView, ThreatControl, EventFeed, EvidencePanel, StatusBar,
                              SettingsDrawer, HistoryDrawer, CriticalAlert
  dist/                       built output, committed; served by FastAPI at /
config/scoring.json           weights, thresholds, tracker and model settings (edited by the sliders)
config/scoring.default.json   factory defaults ("Reset to defaults")
models/                       pinned model files + checksum manifest
bin/ .uv/ .venv/ logs/ run/   created at runtime inside the demo folder (git-ignored)
schemas/                      JSON Schema generated from contracts.py
tests/                        pytest (layers 1–4), clips in tests/clips/ (Git LFS); Vitest in web/
docs/
```

**Routes.** Every route except `GET /` and static assets requires the launch token (see §4):

| Route | Purpose |
|---|---|
| `GET /` | the page |
| `POST /session` | Go: start a session |
| `POST /session/zone` | Apply zone: body is only the polygon; starts a new session with the current words and camera |
| `DELETE /session` | Stop |
| `POST /quit` | Quit |
| `GET /video` | MJPEG stream |
| `WS /events` | live events |
| `GET /health` | `{status, session_id, fps, camera, model, input_size, device}` |
| `GET /cameras` | `[{id, name}]` |
| `GET` / `PUT /config` | read or save the scoring config |
| `GET /sessions` | past sessions |
| `GET /sessions/{session_id}/events` | one session's events |

**Behaviour:**
- **Loop:** frame → detect → track → link → score → emit. The annotated frame goes to `/video`.
- **Go** stops any current session, releases the camera, and starts a new session with a new `session_id`. Nothing carries over.
- **Boundaries:** stages exchange only `contracts.py` types and never import each other. A new source, detector, or scorer is a one-file change. `testing.py` is the sanctioned way to inject `VideoFile`, `SyntheticSource`, or `FakeDetector`. The public `POST /session` accepts only cameras from `GET /cameras`.
- **Overlays** (boxes, trails, direction, scores) are drawn server-side with `supervision`. The browser draws only the zone-editing canvas.
- **Zone:** one optional polygon, drawn on the live video after Go.
  - **Apply zone** sends only the polygon. The server starts a new session with the active session's words and camera plus the zone, recorded in `session.started`.
  - The drawn zone stays visible until the next Go or Stop.
  - Applying with no polygon clears the zone.
  - With no zone, the zone and loiter rules are off.
- **Stop** ends the session with `session.ended {reason: "stopped"}` and releases the camera, so its light goes off.
- **Quit** stops any session and exits the process. The page then shows "Demo closed — you can close this tab". Closing the launcher window also quits.
- **Tab closed:** if no page is connected to `/events` for 30 s *(config)*, the session stops on its own so the camera is not left on.
- **Controls:** threat words, camera dropdown, and a per-session **Save stills** switch sit next to Go / Stop / Quit.
  - Save stills defaults to off and resets to off on every Go.
  - When it is on, a "Recording stills" badge is shown.
  - It is not in `scoring.json`, so it doesn't change `config_sha256`.
- **No remembered inputs:** threat words, camera, and zone start blank on each page load and after each Go. Apply zone keeps the words and camera on the server; the page shows them as the active session.
- **Settings drawer:** sliders for every weight and threshold in `scoring.json`. They are validated by `PUT /config` and saved to the file, and apply on the next Go. "Reset to defaults" copies `scoring.default.json`.
- **History drawer:** lists past sessions from `logs/` (start time, threat words, peak band, and "ended normally / truncated"). Opening one replays its events into the panels.
- **Critical alert:** a red highlight on the track, a banner, and a short Web Audio tone.
  - The tone plays once each time a track *enters* critical.
  - A mute toggle is remembered in the browser.
  - Every band also shows its name as text, not colour alone.
- **UI styling:** Omega's libraries (Tailwind v4, shadcn/ui, lucide-react, vaul), with its theme tokens and self-hosted fonts. **Neutral branding:** "Object Classification Demo".
- **Format pipeline:** `contracts.py` → `schemas/*.json` → `web/src/api/types.ts`, both scripted and drift-checked.
- **Developer workflow:** `npm run dev` (Vite, proxying to Python) → `npm run build` → commit `web/dist/`.

## 2. Data format

Our own JSON Schema, with field meanings aligned to ONVIF Profile M (`class`, `likelihood`, bounding box) and SAPIENT. See [the standards research](../../scrye-docs/research/2026-09-26-sensor-data-standards.md). Rule: **a field that is always the same value is dropped.**

**`POST /session`** (Go):
```json
{ "threat_objects": ["knife", "gun"], "source": "cam-1", "save_stills": false }
```
- `threat_objects`: 1–5 words. Each is trimmed, non-empty, ≤ 50 characters, and de-duplicated case-insensitively.
- Words naming people are rejected against a fixed list (person, people, human, man, men, woman, women, child, children, kid, boy, girl, and their plurals) with the message: "People are always tracked — type an object instead."
- `source` must be an `id` from `GET /cameras`.

**`POST /session/zone`:**
```json
{ "zone": [[0.1,0.6],[0.5,0.6],[0.5,0.95],[0.1,0.95]] }
```
- The zone is a polygon of 3–20 points in normalized 0–1 coordinates, with no self-intersection.
- `null` clears the zone.

**Envelope.** Every event has these fields:
```json
{ "schema_version": "1.1", "event_id": "<uuid>", "session_id": "<uuid>", "source_id": "cam-1",
  "ts": "2026-09-26T18:04:11.231Z", "type": "track.updated",
  "provenance": { "scorer_id": "rules-v1", "config_sha256": "…", "model_sha256": "…",
                  "input_size": 640, "prev_hash": "…", "hash": "…" } }
```

**Payload by event type:**

| `type` | Payload fields (besides the envelope) |
|---|---|
| `session.started` | `threat_objects`, `zone`, `source`, `camera_name`, `device` (cpu/cuda/mps), `model`, `model_sha256`, `input_size`, `save_stills`, `config` (full scoring config), `app_version`. Always the first line of a log. |
| `pipeline.changed` | `model`, `model_sha256`, `input_size`, `reason` (`fps_below_floor`) |
| `track.updated` | `track`, `links`, `summary`, `threat`, `confidence`, `unknowns`, `raw`, optional `snapshot {path, sha256}` |
| `track.ended` | `track_id`, `class`, `duration_s`, `peak_score`, `peak_band` |
| `source.health` | `code` (`fps_low` · `frozen_frame` · `black_frame` · `blur` · `scene_change`), `value`, `detail` |
| `session.ended` | `reason` (`stopped` · `quit` · `error` · `camera_lost` · `idle`), optional `detail`, `peak_band` (the highest band any track reached; `low` if none — added in 1.1, so the history list reads it from the last line). Always the last line of a log that ended normally. |

**`track.updated` example.** A person walking toward the camera holding a knife, with no zone:
```json
{ "…envelope…": "…", "type": "track.updated",
  "track": { "track_id": 7, "class": "person", "bbox": [0.31, 0.22, 0.48, 0.91],
             "likelihood": 0.91, "heading_deg": 180, "direction": "down",
             "speed_body_heights_per_s": 0.4, "camera_mode": "fixed" },
  "links": [ { "object_track_id": 12, "object_class": "knife", "object_likelihood": 0.55,
               "linked_s": 1.8, "strength": 0.62 } ],
  "summary": "Person 7 is holding a knife and moving closer.",
  "threat": { "score": 58, "band": "high",
              "evidence": [
                { "rule_id": "threat_object_link", "rule_version": 1, "type": "supporting",
                  "observed": 1.8, "threshold": 0.5, "contribution": 55,
                  "text": "Holding a knife for 1.8 s (needs 0.5 s): +55" },
                { "rule_id": "approach", "rule_version": 1, "type": "supporting",
                  "observed": 0.08, "threshold": 0.05, "contribution": 3,
                  "text": "Moving closer: box grew 8% wider in 2 s (needs 5%): +3" } ] },
  "confidence": { "score": 0.80,
                  "dimensions": { "detector": 0.91, "track_stability": 0.8, "image_quality": 0.7 } },
  "unknowns": [],
  "raw": { "in_zone": false, "dwell_s": 0, "approach": 0.08, "truncated": false } }
```

**Field meanings:**
- `bbox`: normalized `[x1, y1, x2, y2]`.
- `heading_deg`: direction **on screen**, with 0° = toward the top of the frame, measured clockwise. It is not a compass bearing (see the camera-pose note in the requirements). `direction` is the 8-way label.
- `speed_body_heights_per_s`: distance per second in multiples of the object's own box height.
- `likelihood` / `object_likelihood`: the detector's probability for that class.
- `links[]`: every threat object currently linked to this person. It is empty if none.
  - `strength` is 0–1 and describes the link.
  - `object_likelihood` describes the detection.
- `summary`: one plain-English sentence (like Guardian's `hypothesis`).
- `evidence[].text`: one sentence per item.
- `summary` and `evidence[].text` both come from fixed templates in `scorer.py` (no LLM).
- `threat.evidence`: an itemised receipt.
  - Contributions are integers and **sum exactly to `threat.score`**.
  - If clamping to 0–100 changes the total, a synthetic `{rule_id: "clamp", type: "contradictory" or "supporting", contribution: clamped − raw}` item is added.
- `confidence.score`: the mean of the three dimensions, rounded to 2 decimals. It never changes the threat score.
  - `detector`: the track's likelihood, smoothed over the last 1 s.
  - `track_stability`: the hit ratio over the last 2 s.
  - `image_quality`: the mean of a brightness term and a sharpness term.
    - **Brightness:** 1 when mean luma is 60–200, falling linearly to 0 at 0 and at 255.
    - **Sharpness:** variance of the Laplacian ÷ `sharp_ref` *(config)*, clamped to 0–1.
- `unknowns[]`: `{code, detail}`, where `code` is one of `object_out_of_view`, `track_restarted`, `poor_image`, `camera_moving`, `truncated`.
- `raw.dwell_s`: continuous seconds inside the zone, tolerating gaps up to 1 s *(config)*, carried across `track_restarted`.
- `provenance`: which scorer, config, model and input size produced the event, plus the hash chain.

**Hash chain:**
- `hash` = SHA-256 of the event serialized as canonical JSON (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8) **with `provenance.hash` removed**.
- The first event's `prev_hash` is 64 zeros.
- Snapshot images are covered through `snapshot.sha256` in the event that saved them.
- **Limits:** the chain detects any edited, reordered, or deleted line, and a missing `session.ended` (reported as "truncated or crashed"). It cannot detect a whole log rewritten from scratch, because there is no external anchor.

**Mapping to Guardian** (Guardian's own audit-chain format is unknown, so no compatibility is claimed):

| Our field | Guardian field |
|---|---|
| `summary` | `hypothesis` |
| `threat.score` / `threat.band` | `risk_score` / `severity` |
| `evidence[].type` | supporting / contradictory evidence |
| `confidence.dimensions` | `confidenceDimensions` |
| `unknowns` | `unknowns` |
| `source.health` events | `sourceHealth` |

**Versioning:** `schema_version` uses semver. Adding a field is a minor bump; renaming or removing one is a major bump.

## 3. Pipeline logic

### Clock
- Every `Frame` carries `ts` in seconds.
  - `Webcam` uses the monotonic capture time.
  - `VideoFile` uses video time (frame index ÷ clip fps).
- **All durations in the rules are in seconds of `Frame.ts`**, never frame counts or wall-clock time. Clip tests are therefore identical on fast and slow machines.
- `VideoFile` and `SyntheticSource` disable the automatic model and size step-down.

### Model, device, input size
- **Device:** CUDA if `torch.cuda.is_available()`, otherwise MPS on Apple Silicon, otherwise CPU.
- **Model** (`model: auto | small | large` *(config)*):
  - `auto` means `yolov8l-worldv2` on CUDA/MPS and `yolov8s-worldv2` on CPU.
  - The launcher downloads the small model everywhere, and the large model on GPU machines as well, so fallback always works.
- **Step-down:** start at the configured model with 640 px input. If measured fps stays below 10 for 5 s, step down in this order, one step at a time:
  1. large → small;
  2. 640 → 480;
  3. 480 → 320.

  Each step emits `pipeline.changed`. The model and size in use are always in `/health` and `provenance`.
- **Acceptance counts only at 640 px** (see §5).
- Measured fps per machine is recorded in `docs/knowledge/`.

### Detect
- YOLO-World prompts: `["person", *threat_objects]`.
- **Class-agnostic NMS among threat classes** (IoU ≥ 0.5 *(config)*): when one prop matches several threat words, only the highest-likelihood class is kept. One object therefore produces one track.
- Minimum likelihood *(config)*: person 0.35, threat objects 0.15.

### Track
- **Two ByteTrack instances.**
  - **People:** activation 0.35.
  - **Threat objects:** activation 0.15, so low-likelihood knives do become tracks.
  - Both are *(config)*, along with `lost_track_buffer` and `minimum_matching_threshold`.
  - `frame_rate` is set to the fps measured over the first second of the session.
- **Person eligibility** (for scoring): track age ≥ 1.0 s with a hit ratio ≥ 0.6 over the last 1 s *(config)*.
- **Object eligibility** (for linking) is looser: ≥ 3 detections. The link timer can start as soon as the object track exists.
- **`track_restarted`:** a new track of the same class that starts within 1 s near where a track was just lost. It takes over the lost track's dwell and link state and adds the unknown.

### Motion (fixed camera only)
- Smoothed over ~1 s.
- **Truncation:** if a person box touches the top or bottom edge of the frame (within 1%), heading, speed and approach are **suspended** for that track, and a `truncated` unknown is added.
- **Heading** comes from the velocity of the box's bottom-centre point.
- **Speed** is in box heights per second.
- **Approach** is the relative growth of box **width** over ~2 s. Width is used because raising an arm overhead changes height far more than width.
- **Camera mode** comes from sparse optical flow on the background (outside all boxes). If the median flow is above a threshold *(config)* for 1 s, the mode is `moving`, the motion rules are suspended, and a `camera_moving` unknown is added.

### Link
- **Overlap** = area(object box ∩ expanded person box) ÷ area(object box).
  - The person box is expanded by 15% of its width on each side, and by 15% of its height at the top only (to reach raised hands).
- **Forms:** overlap ≥ 0.30 continuously for ≥ 0.5 s *(config)*. The object may link to only one person; the largest overlap wins.
- **Transfer:** another person must hold ≥ 0.30 overlap for the full 0.5 s to take the object over.
- **Breaks while visible:** if overlap stays below 0.30 for ≥ 1.0 s *(config)* while the object is still tracked (for example, put down and walked away), the link breaks. The object then becomes a candidate for the unattended rule.
- **Object out of view:**
  - The link and its points are **held**.
  - `linked_s` freezes, and `strength` decays linearly to 0 over `fade_s` = 3 s *(config)*.
  - `object_out_of_view` is added.
  - If the object reappears overlapping the same person before the fade ends, the link resumes. Otherwise it breaks.
- **Strength** = mean overlap over the last 1 s × min(1, `linked_s` ÷ 2 s) × fade factor.
- While linked, the object's own track scores 0; the threat is carried by the person.

### Score *(all weights config)*

| Rule | Points |
|---|---|
| Person linked to a threat object | **+55 per linked object** |
| Threat object unattended: not linked for ≥ 2 s (scored on its own track) | +30 |
| Inside the zone (bottom-centre point in polygon) | +25 |
| Loitering: `dwell_s` ≥ 10 s | +15 |
| Approach + running, combined cap 20 | approach = 20 × clamp((growth − 0.05) ÷ (0.25 − 0.05)), running = 20 × clamp((speed − 1) ÷ (2 − 1)) |
| Moving away (width shrinking ≥ 5% over 2 s) / leaving the zone | −5 each (contradictory) |

- Each contribution is rounded to an integer (half up) **before** summing.
- The total is clamped to 0–100 with a `clamp` evidence item (see §2).
- Holding one threat object alone scores 55, which is **high**, matching the success bar.

**Bands** are low 0–24 · medium 25–49 · high 50–74 · critical 75–100.
- **Hysteresis:** move up when score ≥ the higher band's lower bound + 5; move down when score ≤ the lower band's upper bound − 5.
- A new track starts in its raw band.
- The band may briefly lag the score by design.
- Example: 49 (medium) → 55 (high) → 52 (still high) → 44 (medium).

### Emit
An event is emitted when:
- a track becomes eligible;
- its band changes;
- a link forms or breaks;
- a track ends;
- every 2 s while a track is above low (heartbeat).

**Relation to the product decision:** these demo weights make the threat object dominant. That is demo tuning; the proposed product decision in `scrye-docs` is unchanged.

## 4. Error handling, security, privacy, offline

### Camera
- **Listing (`GET /cameras`)** never opens a device, so no camera light and no permission prompt.
  - **macOS:** AVFoundation device list via `pyobjc`.
  - **Windows:** DirectShow device list (`pygrabber`).
  - Each is mapped to the OpenCV index of the same backend (`CAP_AVFOUNDATION` / `CAP_DSHOW`). The ordering assumption is verified on real machines and recorded in `docs/knowledge/`.
- **macOS permission:** Go checks `AVCaptureDevice.authorizationStatus` first.
  - **Not yet asked:** request access. The prompt names **Terminal**. The session start waits for the answer and then retries the open once.
  - **Denied:** "Camera access is off for Terminal: System Settings → Privacy & Security → Camera → turn on Terminal, then quit and relaunch the demo."
- **Windows privacy switch** (no prompt; open fails): "Windows may be blocking desktop apps from the camera: Settings → Privacy & security → Camera → 'Let desktop apps access your camera'."
- **Busy or missing camera:** a plain message; the server stays up and Go retries.
- **Frozen or black frame, low fps, heavy blur, sudden scene change:** a `source.health` event, lower confidence, and a `poor_image` unknown. Scoring continues.
- **Unplugged mid-session:** `session.ended {reason: "camera_lost"}`. Go restarts.

### Go, Apply zone, Stop, Quit
- Validation is as in §2.
- One session at a time; Go while a session is starting is ignored. A failed start rolls back to "no session".
- Stop and Quit are idempotent.

### Launch, port, second launch
- `__main__.py` picks port 8000, or the next free port, and generates a random **launch token**. It writes `run/demo.lock` with `{pid, port, token}` and opens `http://127.0.0.1:<port>/?t=<token>`.
- **Second launch:** if the lock exists and its PID is alive, the launcher opens the running instance's URL and exits. A stale lock is replaced.
- **Launcher safeguards:**
  - It refuses to run from inside a zip or a temp folder, with the message "Extract the zip first, then open the extracted folder."
  - Paths are quoted (`%~dp0` in the `.bat`; `cd "$(dirname "$0")"` in the `.command`).

### Local server security
The server binds to `127.0.0.1` only. Other web pages open in the same browser could otherwise reach it, so:
- **Host allowlist:** `TrustedHostMiddleware` accepts only `127.0.0.1:<port>` and `localhost:<port>`. This defeats DNS rebinding.
- **Origin check:** non-GET routes and the WebSocket handshake reject any `Origin` other than the demo's own.
- **Launch token:**
  - It is required on every route except `GET /` and static assets, including `/video` (`?t=`), `/events` (`?t=`), `/health`, and `/cameras`.
  - The page reads it from its URL and keeps it in memory.
  - Requests without it get **403**.
- `session_id` path parameters must be UUIDs, so they cannot become arbitrary file paths.

### Model and offline
- **Pinned downloads:**
  - The launcher downloads a **pinned uv binary** (version + SHA-256 in the launcher) into `bin/` with `UV_INSTALL_DIR` and `UV_NO_MODIFY_PATH=1`, and ignores any uv already on PATH.
  - It sets `UV_PYTHON_PREFERENCE=only-managed`, `UV_PYTHON_INSTALL_DIR=.uv/python`, and `UV_CACHE_DIR=.uv/cache`.
- **Environment pinned into the folder:** `YOLO_CONFIG_DIR`, `YOLO_OFFLINE=1`, `YOLO_AUTOINSTALL=False`, `TORCH_HOME`, and `XDG_CACHE_HOME` all point inside the demo folder.
- **CLIP:** the text encoder is a dependency pinned by a hashed archive URL, **not a git source**, so Ultralytics never pip-installs it at runtime. Its weights load from `models/` by path.
- **PyTorch variants:**
  - `pyproject.toml` declares mutually exclusive extras `cpu` and `cu12x` under `[tool.uv] conflicts`, each with its own index in `[tool.uv.sources]`. All are hashed in `uv.lock`.
  - On Windows, the launcher picks `cu12x` if `nvidia-smi` is present, and otherwise `cpu`.
  - After install it checks `torch.cuda.is_available()`. If that is false, it warns and falls back to `cpu`.
  - macOS uses the standard wheels (MPS on Apple Silicon).
- **Intel Macs:** a darwin-x86_64 pin set with torch 2.2.x, torchvision to match, **numpy < 2**, and opencv/ultralytics/supervision versions verified against them, recorded in `pyproject.toml`.
- **Minimum macOS:** 12 (Monterey), to be verified on real machines.
- **Checksums:** the launcher verifies them for every model file (small and large YOLO-World, CLIP weights). If a file is missing and there is no internet: "First-time setup needs internet once." Never a stack trace.
- **Download sizes** (first launch): about 1 GB on CPU and Mac, about 3.5 GB on Windows + NVIDIA.
- **Updates:** a new zip re-downloads on first launch. To keep history and tuning, copy `logs/` and `config/scoring.json` across (copying `logs/` also copies any saved stills).

### Engine crash
- An exception in any stage is caught at the session boundary and logged in full, locally.
- The session ends with `session.ended {reason: "error"}`, and the page shows "Something went wrong — click Go to restart".
- No silent retry loops.

### Privacy
- The event log is metadata only.
- Stills are saved only when **Save stills** is on for that session. It resets to off on every Go, and the "Recording stills" badge is visible while it is on. Each still goes to `logs/<session_id>/`, and its SHA-256 is in the event that saved it.
- One JSONL log per session (`logs/<session_id>.jsonl`). No rotation or automatic deletion in the demo. Production will need a retention policy (a product decision).
- Track IDs are per session. No face, gait, or appearance features are used or stored.
- Test clips live in `tests/clips/` under **Git LFS**, marked `export-ignore` so they never ship in the zip. Team members in them have consented.

### Tamper check
`python -m demo.verify_log logs/<id>.jsonl` recomputes the chain and reports one of:
- the first broken link;
- "truncated or crashed" (no `session.ended`);
- "OK".

## 5. Testing

Tests are written first (test-driven development). There are five layers.

**Layer 1: unit tests** (pytest, pure logic, synthetic inputs, runs in seconds).
- **Scorer:**
  - contributions are integers and sum exactly to the score;
  - clamp cases: 105 → 100 with a `clamp` item, and a lone −5 → 0;
  - the band sequence 49 → 55 → 52 → 44 gives medium, high, high, medium;
  - one linked object gives 55 (high); two linked objects give 110 → 100 with the summary naming both;
  - unstable tracks score 0;
  - templates render for every rule;
  - the confidence mean matches its dimensions.
- **Linker:**
  - the overlap denominator is object-box area;
  - a knife raised above the head links (top expansion);
  - largest-overlap wins;
  - transfer needs 0.5 s;
  - break while visible, followed by unattended +30 after 2 s;
  - fade: points held, `linked_s` frozen, strength decays, resume on reappear;
  - **the link forms within 2 s at 8 fps with a 50% object hit ratio.**
- **Tracker and motion:**
  - heading and speed from synthetic box sequences (down-left ≈ 225°);
  - a stationary person with a raised arm gets 0 approach points;
  - a truncated box suspends motion and adds `truncated`;
  - camera-mode switching;
  - class-agnostic NMS keeps one class per object;
  - a 0.18-likelihood object detection produces a track.
- **Events:**
  - canonical hashing;
  - the genesis `prev_hash`;
  - `verify-log` catches an edited, a deleted, and a reordered line, and a missing `session.ended`.
- **Contracts:**
  - `SessionConfig` rejects empty, over-long, more than 5, duplicate, and person-naming words;
  - zone polygons with fewer than 3 or more than 20 points, out of range, or self-intersecting are rejected;
  - **drift check:** generated `schemas/` must equal the committed files.

**Layer 2: server and session integration** (pytest, `FakeDetector` + `SyntheticSource` via `testing.make_session`; no camera, no model).
- Go → events → Stop releases the source and writes `reason: "stopped"`.
- Quit exits cleanly with the log closed.
- Apply zone starts a new session that keeps the words and camera.
- Idle auto-stop after 30 s without a page.
- `PUT /config` rejects out-of-range values, and the saved hash appears in the next `session.started`.
- History lists sessions, including a crashed one, which is reported as truncated.
- **Security:**
  - a missing token gets 403;
  - a foreign `Origin` on non-GET routes and on the WebSocket gets 403;
  - a foreign `Host` gets 400;
  - a non-UUID `session_id` gets 422.
- Step-down emits `pipeline.changed`, and it is disabled for `VideoFile`.
- A second-launch lock is detected.

**Layer 3: offline guarantee with the real detector.**
- With `pytest-socket` blocking all non-localhost connections, the test:
  - imports Ultralytics;
  - loads the pinned model;
  - calls `set_classes(["person", "knife"])`;
  - runs 30 synthetic frames.
- The test fails on any connection attempt, on any file written outside the test's demo folder, or on any runtime pip install.
- **In CI**, the pinned models are cached with `actions/cache`, keyed on the checksum manifest, so this layer runs on every push.

**Layer 4: clip pipeline tests** (real model, `slow`, local only; the clips come from Git LFS and the tests skip cleanly if absent).
- Clips:
  - empty room;
  - person walking past;
  - person holding a knife;
  - apple left on a table;
  - handheld camera;
  - a toy/replica gun;
  - two threat words set at once.
- Assertions are on outcomes, not exact numbers:
  - the knife clip links and reaches ≥ high;
  - the empty room produces no track events;
  - the apple is scored unattended;
  - the handheld clip reports `camera_moving`;
  - a prop matching both words yields one link.

**Layer 5: web** (Vitest).
- Event-feed state, zone clicks → normalized coordinates, and comma-list parsing.
- The critical tone fires once per entry into critical and respects mute.
- The settings form is validated.
- The Save stills badge.
- The token is attached to every request.
- **Drift check:** `types.ts` must equal what is generated from `schemas/`.

**Continuous integration** (GitHub Actions, Windows + macOS). On every push it runs:
- layers 1, 2, 3 and 5, and both drift checks;
- `uv lock --check`, plus `uv sync --frozen --extra cpu` (and a resolution check for `cu12x` and the darwin-x86_64 set);
- a check that `Start Demo.command` has git mode **100755**.

**Acceptance check (the success bar).** Only runs at **640 px** count. Record the machine, device, model, and input size with the result in `docs/knowledge/`. A stepped-down machine is recorded as "below bar at 640".
- **Hits:** at 2–3 m in normal room light, type the prop's own word (kitchen knife → "knife", replica gun → "gun", apple → "apple", book → "book"), then raise the prop 10 times.
  - Measure latency from the object track's first detection `ts` to the link-formed event `ts`.
  - **≥ 8 of 10** must link within 2 s and reach `high`.
- **False links:** with "knife" typed, raise each harmless prop (apple, book, cup, phone) 10 times. **At most 2 of 10** per prop may link. Record the likelihoods.

**Manual release checklist** (`docs/release-checklist.md`):
- Use a fresh Windows machine (CPU and NVIDIA) and a fresh Mac (Apple Silicon and Intel).
- Download the zip built with `git archive --format=zip` and extract it.
- Get past SmartScreen ("More info → Run anyway"), or the macOS warning (on Sequoia: System Settings → Privacy & Security → "Open Anyway").
- Allow the camera, type "knife", click Go, and see a link.
- **Second launch with Wi-Fi off** reaches Go.
- **No new files outside the demo folder.**
- The Mac launcher is still executable after extraction.
- A second double-click reopens the running instance.

## 6. Documentation and setup guides

Two audiences, humans and AI, with one fact in one place. Every doc uses YAML frontmatter (`title`, `status`, `date`, `related`).

| File | Audience | Contents |
|---|---|---|
| `README.md` | Everyone | What this is, the demo/product split with links to `scrye-docs`, and a **three-step quick start**. |
| `docs/setup-guide.md` | Non-technical people | Windows and Mac steps with a screenshot per step: extract (not run from the zip), OS warning (including the Sequoia "Open Anyway" path), camera permission for Terminal, and Windows camera privacy. Download sizes per platform (~1 GB / ~3.5 GB NVIDIA). Updating (copy `logs/` and `config/scoring.json`; stills included). A troubleshooting table keyed by the exact on-screen message. The real-knife safety note. Measured fps per machine. |
| `AGENTS.md` | AI assistants (the primary builders; the team reviews) | Exact install/run/test commands per layer. How to confirm it's running (`/health` with the token from `run/demo.lock`). The stage map, the rules (contracts first; product decisions in `scrye-docs`; a field that is always the same value is dropped), and where each kind of change goes. `CLAUDE.md` contains only `@AGENTS.md`. |
| `docs/requirements.md` / `docs/design.md` | Both | What the demo must do, and how. Kept current. |
| `docs/knowledge/` | Both | One note per learning (`YYYY-MM-DD-<topic>.md`: *observed*, *evidence*, *implication*). For example: acceptance results, fps per machine, open-vocabulary likelihoods, the camera-index ordering check. Technical here; product learnings go to `scrye-docs`. |
| `docs/release-checklist.md` | Whoever ships | The manual check from §5. |
| `schemas/` | Integrators | Generated JSON Schema. Field descriptions come from `contracts.py`. |

**Definition of done for any change:**
- Code, tests, and affected docs go in the same commit.
- A new learning gets a `docs/knowledge/` note.
- A product-level change goes to `scrye-docs` first.

## Review log

**Adversarial review, 2026-09-26.** Five attackers (CV realism, consistency, security, non-technical ops, buildability) raised 41 findings; two skeptics refuted each; a chair merged the survivors into 19. All were applied above.

User decisions taken during the review:
- The link is worth **+55**, so holding an object alone reaches high.
- Acceptance counts only at **640 px**.
- GPU machines start on the **large model** with auto-fallback.
- **Save stills is per session** and resets on Go.
- **False links are capped at ≤ 2/10** per harmless prop.
