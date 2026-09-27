# Object Classification Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained, double-click demo. A laptop webcam feeds live frames. The demo detects people and operator-typed threat objects, tracks them, links objects to people, and scores each track for threat and confidence with an itemised evidence receipt. Results appear in a React page and in a hash-chained event log.

**Architecture:**
- One Python process built as independent stages: source → detector → tracker → linker → scorer → events.
- Stages exchange only types from `demo/contracts.py`.
- A FastAPI server exposes a token-protected local API, an MJPEG video stream and a WebSocket event stream.
- The React + Vite UI is prebuilt into `web/dist/` and served by FastAPI.
- The launchers bootstrap a pinned `uv` and keep everything inside the demo folder.

**Tech Stack:**
- Python 3.12 via `uv`: ultralytics (YOLO-World), supervision (ByteTrack), opencv-python, torch, FastAPI + uvicorn, pydantic v2, pytest, pytest-socket, ruff.
- Web: React + TypeScript + Vite, Tailwind CSS v4, shadcn/ui, lucide-react, vaul, Vitest, json-schema-to-typescript.

**Spec:** [`docs/design.md`](../../design.md) (how) and [`docs/requirements.md`](../../requirements.md) (what). Executors must read both. Section references like "§3 Link" point into `design.md`.

## Global Constraints

**Platforms and runtime**
- Platforms are Windows and macOS only. Minimum macOS is 12. Python is exactly 3.12, managed by uv (`UV_PYTHON_PREFERENCE=only-managed`).
- Everything is written inside the demo folder. That includes `bin/`, `.uv/`, `.venv/`, `models/`, `logs/` and `run/`, plus the YOLO, Torch and XDG caches. Nothing goes in the user's home.
- The demo is offline after first setup: `YOLO_OFFLINE=1`, `YOLO_AUTOINSTALL=False`, and no telemetry. The server binds to `127.0.0.1` only.

**API and data**
- Every route except `GET /` and static assets requires the launch token.
- A field that is always the same value is dropped.
- All rule durations are in seconds of `Frame.ts`, never frame counts or wall clock.
- Every number marked *config* in the spec lives in `config/scoring.json` (Task 2 lists them all). Do not hard-code them.
- Evidence `contribution`s are integers that sum exactly to `threat.score`. Clamping adds a `clamp` item.
- Plain-English `summary` and `evidence[].text` come from fixed templates. No LLM.

**UI**
- Branding is neutral: page title and header read "Object Classification Demo".
- UI libraries match Omega: Tailwind v4, shadcn/ui, lucide-react, vaul.
- Theme tokens: `--background: 0 0% 4%`, `--foreground: 0 0% 98%`, `--card: 0 0% 7%`, `--primary: 46 60% 52%`, `--primary-foreground: 0 0% 8%`, `--muted: 0 0% 12%`, `--muted-foreground: 0 0% 60%`, `--border: 0 0% 14%`, `--ring: 46 60% 52%`, `--destructive: 0 62.8% 30.6%`.
- Fonts are self-hosted: Montserrat, Oswald, Rajdhani, IBM Plex Mono.

**Workflow**
- Tests come first (TDD).
- Code, tests and affected docs go in the same commit.
- Every commit message ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work on branch `feat/demo`. Create it with superpowers:using-git-worktrees at execution time.

**Licensing**
- Ultralytics is AGPL-3.0. That is acceptable for this internal demo only. The detector stays behind the `Detector` protocol.

## Review Focus

These are the input classes the spec implies but no feature test would naturally hit. Each has a pinned test in the owning task.

1. **Camera aspect or orientation differs from the page's box.** A 4:3 camera, a 16:9 camera, or a portrait phone camera (Continuity Camera) shown with `object-fit: contain` letterboxing. A zone click must still map to the right normalized frame point. *(Task 17: `test_zone_click_maps_through_letterbox`)*
2. **Messy threat-word input.** For example `"Knife,, knife , "`, `"KNIFE"`, `"🔪"`, or a 51-character word. Expected: duplicates collapse case-insensitively to `["knife"]`, the emoji is accepted as a word (an open-vocabulary prompt), and the over-long word is rejected with a message. *(Task 1: `test_threat_words_normalised`; Task 17: `test_parse_threat_words`)*
3. **A slow or stalled WebSocket client, or several tabs open.** The engine loop must never block on a subscriber. The log file stays complete, and a slow client drops events rather than stalling the demo. *(Task 3: `test_fanout_never_blocks_on_stalled_subscriber`)*
4. **A long session (hours).** Per-track history and fan-out queues stay bounded. The history drawer must not read whole large logs to list sessions. *(Task 6: `test_history_is_bounded`; Task 12: `test_sessions_list_reads_only_first_and_last_lines`)*
5. **A corrupted or partial final log line** (power loss or crash mid-write), or non-log files in `logs/`. The history list, the replay and `verify_log` report the problem without crashing. *(Task 3: `test_verify_log_partial_last_line`; Task 12: `test_sessions_list_skips_foreign_files`)*

---

## File Map

```
pyproject.toml, uv.lock, .gitignore, .gitattributes, ruff.toml
AGENTS.md, CLAUDE.md (only "@AGENTS.md"), README.md
Start Demo.bat, Start Demo.command
config/scoring.json, config/scoring.default.json
models/manifest.json                     pinned URLs + SHA-256 per model file
demo/
  __init__.py      __version__
  __main__.py      launch: port, token, lock, browser                     (Task 14)
  contracts.py     internal dataclasses + wire Pydantic models           (Task 1)
  config.py        ScoringConfig load/save/hash                          (Task 2)
  events.py        canonical hash, EventLog, Fanout                      (Task 3)
  verify_log.py    CLI                                                   (Task 3)
  source.py        SyntheticSource, VideoFile, Webcam                    (Task 4)
  health.py        image quality + source.health detection               (Task 4)
  detector.py      Detector protocol, FakeDetector, threat NMS, YoloWorldDetector (Tasks 5, 15)
  motion.py        heading/speed/approach/truncation/camera mode (split out of tracker.py; §3 Motion) (Task 6)
  tracker.py       two ByteTracks, eligibility, restarts, history        (Task 6)
  linker.py        Linker                                                (Task 7)
  scorer.py        rules, bands, confidence, templates                   (Task 8)
  session.py       Session, emission rules, step-down, idle stop, stills (Tasks 9, 10)
  testing.py       make_session()                                        (Task 9)
  cameras.py       list_cameras(), permission status                     (Task 11)
  server.py        FastAPI app, security middleware, routes              (Tasks 12, 13)
  models.py        manifest, verify, download (setup)                    (Task 15)
  setup.py         `python -m demo.setup`: variant check, model fetch    (Task 16)
scripts/export_schemas.py                                                 (Task 1)
schemas/*.json                                                            (Task 1)
tests/unit/ tests/integration/ tests/offline/ tests/pipeline/ tests/clips/ (LFS)
web/ (Vite app; src/api/, src/components/, src/lib/)                     (Tasks 17–19)
.github/workflows/ci.yml                                                  (Task 20)
docs/setup-guide.md, docs/release-checklist.md, docs/knowledge/           (Task 21)
```

---

## Milestone A: Foundations

### Task 1: Project scaffold, contracts and schema export

**Files:**
- Create: `pyproject.toml`, `ruff.toml`, `.gitignore`, `.gitattributes`, `CLAUDE.md`, `AGENTS.md` (stub: commands only), `demo/__init__.py`, `demo/contracts.py`, `scripts/export_schemas.py`, `schemas/` (generated)
- Test: `tests/unit/test_contracts.py`, `tests/unit/test_schema_drift.py`

**Interfaces:**
- Produces (all in `demo/contracts.py`):
  - `BBox = tuple[float, float, float, float]` (normalized x1, y1, x2, y2)
  - Frozen dataclasses:
    - `Frame(index: int, ts: float, image: np.ndarray)` with properties `width`, `height`
    - `Detection(class_name: str, likelihood: float, bbox: BBox)`
    - `Track(track_id: int, class_name: str, bbox: BBox, likelihood: float, first_ts: float, ts: float, detections: int, hit_ratio_1s: float, hit_ratio_2s: float, visible: bool, restarted_from: int | None)`
    - `Link(person_id: int, object_id: int, object_class: str, object_likelihood: float, linked_s: float, strength: float, out_of_view_s: float | None)`
  - `Band = Literal["low","medium","high","critical"]`
  - `UnknownCode = Literal["object_out_of_view","track_restarted","poor_image","camera_moving","truncated"]`
  - Wire Pydantic models:
    - requests: `SessionRequest(threat_objects: list[str], source: str, save_stills: bool = False)`, `ZoneRequest(zone: list[tuple[float, float]] | None)`
    - parts: `Provenance`, `TrackOut`, `LinkOut`, `EvidenceItem`, `Threat`, `ConfidenceDimensions`, `Confidence`, `Unknown`, `Raw`, `Snapshot`
    - events: `SessionStarted`, `PipelineChanged`, `TrackUpdated`, `TrackEnded`, `SourceHealth`, `SessionEnded`, and `Event` (a discriminated union on `type`)
  - `PERSON_WORDS: frozenset[str]`
  - Field names and enums are exactly as in §2. Field descriptions come from §2 "Field meanings".
  - `SCHEMA_VERSION = "1.0"`.

**Steps:**

- [ ] **Step 1: Scaffold the project**
  - `pyproject.toml`:
    - `requires-python = "==3.12.*"`;
    - dependencies: `ultralytics`, `supervision`, `opencv-python`, `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `numpy`;
    - dev group: `pytest`, `pytest-socket`, `httpx`, `ruff`;
    - `[project.scripts]` is not needed.

    Leave torch variants to Task 16.
  - `.gitignore`: `bin/ .uv/ .venv/ logs/ run/ models/*.pt models/*.pth web/node_modules/`
  - `.gitattributes`:
    - `tests/clips/** filter=lfs diff=lfs merge=lfs -text export-ignore`
    - `*.command text eol=lf`
    - `*.bat text eol=crlf`
  - Then run `uv lock`.

- [ ] **Step 2: Write the failing contract tests**

```python
def test_threat_words_normalised():
    r = SessionRequest(threat_objects=["Knife", " knife ", "", "🔪"], source="cam-1")
    assert r.threat_objects == ["knife", "🔪"]           # trimmed, lower-cased dedupe, blanks dropped, emoji allowed

@pytest.mark.parametrize("words", [[], ["a"*51], ["a","b","c","d","e","f"], ["person"], ["Women"], ["kids"]])
def test_threat_words_rejected(words):
    with pytest.raises(ValidationError): SessionRequest(threat_objects=words, source="cam-1")

def test_person_word_message():
    with pytest.raises(ValidationError, match="People are always tracked — type an object instead."):
        SessionRequest(threat_objects=["person"], source="cam-1")

@pytest.mark.parametrize("zone", [[(0,0),(1,0)], [(0,0)]*21, [(0,0),(1.2,0),(1,1)], [(0,0),(1,1),(1,0),(0,1)]])
def test_zone_rejected(zone):   # <3 pts, >20 pts, out of range, self-intersecting (bow-tie)
    with pytest.raises(ValidationError): ZoneRequest(zone=zone)

def test_zone_none_clears(): assert ZoneRequest(zone=None).zone is None

def test_event_union_roundtrip():  # every event type parses back through Event by its "type"
    ...
```

- [ ] **Step 3:** Run `uv run pytest tests/unit/test_contracts.py -v`. Expected: FAIL on import.

- [ ] **Step 4: Implement `demo/contracts.py`**
  - Threat words are validated with a `field_validator`. Case-insensitive dedupe keeps the first spelling, lower-cased.
  - `PERSON_WORDS` holds: person, persons, people, human, humans, man, men, woman, women, child, children, kid, kids, boy, boys, girl, girls.
  - The self-intersection check tests every pair of non-adjacent segments for proper intersection.

- [ ] **Step 5: Implement `scripts/export_schemas.py`**
  - It writes `schemas/<Model>.json` for `SessionRequest`, `ZoneRequest` and `Event` via `model_json_schema()`.
  - Output is sorted keys with 2-space indent, and `--check` exits 1 on any diff.
  - Then add `tests/unit/test_schema_drift.py`, which asserts `export_schemas.main(["--check"]) == 0`.

- [ ] **Step 6:** Run `uv run python scripts/export_schemas.py`, then `uv run pytest tests/unit -v`. Expected: all pass.

- [ ] **Step 7: Commit**
  - Include `docs/`, `README.md`, the scaffold, contracts, schemas and tests.
  - Message: `feat: scaffold project, contracts and schema export`.

### Task 2: Scoring config

**Files:**
- Create: `demo/config.py`, `config/scoring.default.json`, `config/scoring.json` (an identical copy)
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces:
  - `ScoringConfig` (Pydantic, nested groups below; every field has `ge`/`le` bounds used by the sliders)
  - `load_config(path: Path) -> ScoringConfig`
  - `save_config(cfg: ScoringConfig, path: Path) -> None`
  - `config_sha256(cfg: ScoringConfig) -> str` (SHA-256 of canonical JSON, same canonicalisation as Task 3)
  - `reset_to_defaults(config_dir: Path) -> ScoringConfig`

**Default values** (copy exactly):

```json
{ "detect":      {"person_min": 0.35, "object_min": 0.15, "threat_nms_iou": 0.5},
  "tracker":     {"person_activation": 0.35, "object_activation": 0.15, "lost_track_buffer": 30, "minimum_matching_threshold": 0.8},
  "eligibility": {"person_min_age_s": 1.0, "person_min_hit_ratio": 0.6, "object_min_detections": 3},
  "motion":      {"smoothing_s": 1.0, "approach_window_s": 2.0, "truncation_margin": 0.01, "camera_flow_threshold": 0.01, "camera_moving_s": 1.0},
  "restart":     {"window_s": 1.0, "max_distance": 0.1},
  "link":        {"expand_side": 0.15, "expand_top": 0.15, "min_overlap": 0.30, "form_s": 0.5, "break_s": 1.0, "fade_s": 3.0, "strength_full_s": 2.0},
  "zone":        {"dwell_gap_s": 1.0, "loiter_s": 10.0},
  "weights":     {"link": 55, "unattended": 30, "unattended_after_s": 2.0, "in_zone": 25, "loiter": 15, "motion_cap": 20,
                  "approach_min": 0.05, "approach_max": 0.25, "run_min": 1.0, "run_max": 2.0, "moving_away_shrink": 0.05, "contradictory": 5},
  "bands":       {"hysteresis": 5},
  "confidence":  {"sharp_ref": 100.0, "luma_lo": 60, "luma_hi": 200},
  "health":      {"black_luma": 10, "frozen_diff": 1.0, "frozen_s": 2.0, "blur_var": 20.0, "scene_change_diff": 60.0},
  "emit":        {"heartbeat_s": 2.0},
  "runtime":     {"model": "auto", "fps_floor": 10, "stepdown_after_s": 5.0, "idle_stop_s": 30.0} }
```

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_defaults_load_and_match_file`
  - `test_out_of_range_rejected` (e.g. `weights.link = 500` raises)
  - `test_hash_stable_and_changes` (identical configs hash the same; changing one value changes the hash)
  - `test_reset_copies_default` (after a modified save, reset gives a hash equal to the default's)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_config.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement `demo/config.py` and the two JSON files.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: versioned scoring config`.

### Task 3: Event log, hash chain, fan-out, verify_log

**Files:**
- Create: `demo/events.py`, `demo/verify_log.py`
- Test: `tests/unit/test_events.py`

**Interfaces:**
- Consumes: `Event` (Task 1).
- Produces:
  - `canonical_json(obj: dict) -> bytes` (`sort_keys=True`, `separators=(",",":")`, `ensure_ascii=False`, UTF-8)
  - `GENESIS = "0"*64`
  - `class EventLog(path: Path)` with:
    - `.append(event: dict) -> dict`, which fills `provenance.prev_hash` and `provenance.hash`, writes one line, flushes, and returns the sealed event;
    - `.close()`.
  - `class Fanout` with:
    - `.subscribe() -> asyncio.Queue` (maxsize 256);
    - `.unsubscribe(q)`;
    - `.publish(event: dict) -> None` (non-blocking; on a full queue it drops the oldest item).
  - `verify(path: Path) -> VerifyResult(ok: bool, first_broken_line: int | None, truncated: bool, message: str)`
  - CLI: `python -m demo.verify_log <file>` prints `message` and exits 0 when ok, 1 otherwise.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_hash_excludes_own_hash_field`
  - `test_first_prev_hash_is_genesis`
  - `test_chain_verifies_ok` (the log ends with `session.ended` → `ok` and "OK")
  - `test_verify_detects_edit`, `test_verify_detects_deleted_line`, `test_verify_detects_reordered_lines` (each reports the correct `first_broken_line`)
  - `test_verify_missing_session_ended_is_truncated` (message contains "truncated or crashed")
  - `test_verify_log_partial_last_line` (a half-written final line → `truncated=True`, no exception)
  - `test_fanout_never_blocks_on_stalled_subscriber` (a subscriber never reads; 10,000 publishes finish in under 1 s, and its queue size is ≤ 256)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_events.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement `demo/events.py` and `demo/verify_log.py`.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: hash-chained event log, fanout and verify_log`.

### Task 4: Sources and image health

**Files:**
- Create: `demo/source.py`, `demo/health.py`
- Test: `tests/unit/test_source.py`, `tests/unit/test_health.py`

**Interfaces:**
- Produces:
  - `class Source(Protocol)`: `open() -> None`, `read() -> Frame | None` (`None` = ended or lost), `close() -> None`, `realtime: bool`, `id: str`, `name: str`
  - `SyntheticSource(frames: list[np.ndarray] | Callable[[int], np.ndarray], fps: float, id="synthetic")`: `ts = index / fps`, `realtime = False`
  - `VideoFile(path: Path)`: `ts = index / clip_fps`, `realtime = False`
  - `Webcam(index: int, backend: int, id: str, name: str)`: `ts = time.monotonic()` at capture, `realtime = True`
  - In `demo/health.py`:
    - `image_quality(img, cfg) -> tuple[float, float, float]` (brightness, sharpness, quality = their mean)
    - `class HealthMonitor(cfg)` with `.update(frame: Frame, fps: float) -> list[tuple[str, float, str]]`. It returns codes from `fps_low`, `frozen_frame`, `black_frame`, `blur` and `scene_change`, emitted on state *entry* only.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_synthetic_ts_is_video_time` (30 fps → frame 45 has `ts == 1.5`)
  - `test_brightness_curve`:
    - luma 128 → 1.0;
    - luma 0 → 0.0;
    - luma 30 → 0.5 (linear from 0 to 60);
    - luma 227.5 → 0.5.
  - `test_sharpness_clamped` (a flat image → 0.0; a checkerboard → 1.0)
  - `test_black_frame_reported_once`
  - `test_frozen_after_frozen_s` (identical frames for 2.1 s of `ts` → `frozen_frame`)
  - `test_scene_change`
  - `test_fps_low_below_floor`

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_source.py tests/unit/test_health.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement both modules. `Webcam` is exercised only in Task 11 and in manual testing.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: frame sources and image health`.

## Milestone B: Pipeline logic (pure, fully unit-tested)

### Task 5: Detector protocol, fake detector, threat-class NMS

**Files:**
- Create: `demo/detector.py` (the real detector is added in Task 15)
- Test: `tests/unit/test_detector.py`

**Interfaces:**
- Produces:
  - `class Detector(Protocol)`: `set_classes(words: list[str]) -> None`, `detect(frame: Frame, input_size: int) -> list[Detection]`, `model_name: str`, `model_sha256: str`
  - `FakeDetector(script: Callable[[Frame], list[Detection]], model_name="fake", model_sha256="0"*64)`
  - `threat_nms(dets: list[Detection], threat_words: set[str], iou: float) -> list[Detection]`: class-agnostic among threat classes only; keeps the highest likelihood; person detections pass through untouched.
  - `filter_min(dets, person_min, object_min) -> list[Detection]`

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_nms_keeps_best_threat_class` (knife 0.4 and gun 0.3 on the same box → one knife detection)
  - `test_nms_leaves_person_alone`
  - `test_nms_keeps_separate_objects` (IoU 0.1 → both kept)
  - `test_filter_min` (a person at 0.30 is dropped; an object at 0.16 is kept)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_detector.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: detector protocol, fake detector, threat NMS`.

### Task 6: Tracker and motion

**Files:**
- Create: `demo/tracker.py`, `demo/motion.py`
- Test: `tests/unit/test_tracker.py`, `tests/unit/test_motion.py`

**Interfaces:**
- Consumes: `Detection`, `Frame`, `Track`, `ScoringConfig`.
- Produces:
  - In `demo/tracker.py`:
    - `class Tracker(cfg, frame_rate: int)`, which holds two `supervision.ByteTrack` instances (people use `person_activation`; objects use `object_activation`).
    - `Tracker.update(frame: Frame, dets: list[Detection]) -> tuple[list[Track], list[Track]]` returns (people, objects), including tracks just lost this frame with `visible=False`.
    - `Tracker.ended() -> list[Track]` returns tracks removed since the last call.
    - `Tracker.history(track_id) -> Sequence[tuple[float, BBox]]` is a bounded deque (`maxlen = 10 s × frame_rate`).
    - `person_eligible(t: Track, cfg) -> bool` and `object_eligible(t: Track, cfg) -> bool`.
    - Restart rule: a new track of the same class within `restart.window_s` and `restart.max_distance` (bottom-centre distance) of a track lost in that window gets `restarted_from = <old id>`.
  - In `demo/motion.py` (pure functions over history):
    - `heading_deg(hist, smoothing_s) -> float | None` (0° = up, clockwise; uses bottom-centre velocity)
    - `direction_label(deg) -> str` (8-way: up, up-right, right, down-right, down, down-left, left, up-left)
    - `speed_bh_s(hist, smoothing_s) -> float | None`
    - `approach(hist, window_s) -> float | None` (relative width growth)
    - `truncated(bbox, margin) -> bool` (top or bottom edge)
    - `class CameraModeDetector(cfg)` with `.update(frame, boxes: list[BBox]) -> Literal["fixed","moving"]` (sparse LK optical flow on the background, normalized by frame width; the mode is `moving` after `camera_moving_s` above threshold)

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_heading_down_left_is_225`
  - `test_heading_up_is_0`
  - `test_direction_label_boundaries`
  - `test_speed_body_heights` (a box of height 0.5 moving 0.5 per s → 1.0)
  - `test_raised_arm_no_approach` (height +30% at constant width → `approach < 0.05`)
  - `test_approach_width_growth` (width +8% over 2 s → 0.08)
  - `test_truncated_top_and_bottom` (y1 = 0.005 → True; y2 = 0.995 → True; mid-frame → False)
  - `test_camera_mode_switches_on_global_shift` (every frame shifted by 3% → `moving` after 1 s; static → `fixed`)
  - `test_low_likelihood_object_becomes_track` (object detections at 0.18 over 5 frames → an object track exists)
  - `test_person_eligibility_seconds` (at 10 fps: eligible at `ts ≥ 1.0` with hit ratio ≥ 0.6; not at 0.9)
  - `test_restart_links_to_lost_track`
  - `test_history_is_bounded` (60 s at 30 fps → `len(history) ≤ 300`)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_tracker.py tests/unit/test_motion.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement. Hit ratio = frames with a matched detection ÷ frames elapsed in the window, measured by `ts`.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: dual ByteTrack tracker and motion math`.

### Task 7: Linker

**Files:**
- Create: `demo/linker.py`
- Test: `tests/unit/test_linker.py`

**Interfaces:**
- Consumes: `Track`, `Link`, `ScoringConfig`.
- Produces:
  - `overlap(obj: BBox, person: BBox, expand_side: float, expand_top: float) -> float` = area(obj ∩ expanded person) ÷ area(obj)
  - `class Linker(cfg)` with:
    - `.update(ts: float, people: list[Track], objects: list[Track]) -> list[Link]` (active links, including fading ones)
    - `.events() -> list[tuple[Literal["formed","broken"], Link]]` (drained each call)
    - `.unattended_s(object_id, ts) -> float | None` (seconds since the object was last linked or first seen, if unlinked)

**Steps:**

- [ ] **Step 1: Write the failing tests** (all values come from §3 Link)
  - `test_overlap_denominator_is_object_area` (a small object fully inside the person box → 1.0)
  - `test_raised_knife_above_head_links` (object 10% of the person's height above the box top → overlap ≥ 0.30)
  - `test_forms_after_form_s` (overlap 0.5 held: no link at 0.4 s; a link at 0.5 s)
  - `test_largest_overlap_wins`
  - `test_transfer_needs_full_form_s`
  - `test_breaks_when_visible_and_apart` (overlap 0 for 1.0 s while visible → "broken")
  - `test_unattended_after_break` (`unattended_s` reaches 2.0 two seconds after the break)
  - `test_fade_holds_link_and_freezes_linked_s` (object invisible 1.5 s → link still present, `linked_s` unchanged, strength = pre × 0.5, `out_of_view_s = 1.5`)
  - `test_resume_on_reappear`
  - `test_break_after_fade` (invisible 3.1 s → broken)
  - `test_strength_formula` (mean overlap 0.8, `linked_s` 1.0 → 0.4)
  - `test_links_within_2s_at_8fps_half_hit_ratio` (object detected on alternate frames at 8 fps → a link within 2.0 s of the first detection `ts`)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_linker.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement. The overlap state per (person, object) pair tracks `above_since` and `below_since` timestamps.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: object-to-person linker`.

### Task 8: Scorer, bands, confidence, templates

**Files:**
- Create: `demo/scorer.py`
- Test: `tests/unit/test_scorer.py`

**Interfaces:**
- Consumes: `Track`, `Link`, motion values, `ScoringConfig`, `Unknown`, `EvidenceItem`.
- Produces:
  - `RULES = ("threat_object_link","unattended","in_zone","loiter","approach","running","moving_away","leaving_zone","clamp")`, all `rule_version = 1`
  - `@dataclass Inputs(track: Track, links: list[Link], motion_enabled: bool, heading: float|None, speed: float|None, approach: float|None, in_zone: bool, left_zone: bool, dwell_s: float, unattended_s: float|None, detector_conf: float, track_stability: float, image_quality: float, unknowns: list[Unknown])`
  - `@dataclass Assessment(score: int, raw_band: Band, evidence: list[EvidenceItem], summary: str, confidence: Confidence, unknowns: list[Unknown])`
  - `score(inp: Inputs, cfg) -> Assessment`
  - `class BandTracker(hysteresis: int)` with `.update(track_id, score) -> Band` (a new track starts in its raw band)
  - `band_of(score) -> Band` (bands 0–24, 25–49, 50–74, 75–100)

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_single_link_scores_55_high`
  - `test_two_links_clamped_to_100_with_clamp_item` (items: 55, 55, clamp −10; sum 100; the summary names "knife" and "gun")
  - `test_lone_contradictory_clamps_to_zero` (−5 plus clamp +5 = 0)
  - `test_contributions_are_ints_and_sum_to_score` (property test over random inputs)
  - `test_approach_linear` (growth 0.08 → 3; 0.25 → 20; the approach + running cap is 20)
  - `test_running_linear` (speed 1.5 → 10)
  - `test_motion_suspended_gives_no_motion_items`
  - `test_loiter_needs_dwell_10s`
  - `test_unattended_after_2s`
  - `test_band_hysteresis_sequence` (`BandTracker(5)` over 49, 55, 52, 44 → medium, high, high, medium)
  - `test_confidence_mean` (0.91, 0.8, 0.7 → 0.80)
  - `test_templates_render_for_every_rule` (each rule id yields non-empty `text`; exact strings: `"Holding a knife for 1.8 s (needs 0.5 s): +55"` and `"Moving closer: box grew 8% wider in 2 s (needs 5%): +3"`)
  - `test_example_event_matches_spec` (reproduces the §2 example: score 58, band high, confidence 0.80)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_scorer.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement. Rounding is half-up per item (`int(x + 0.5)` for x ≥ 0; mirror it for negatives). Summary templates:
  - `"Person {id} is holding a {objs}{ctx}."` where `ctx` joins `" inside the zone"`, `" and moving closer"` and `" and running"`;
  - `"Unattended {obj} (object {id})."`;
  - `"Person {id}{ctx}."` when there is no link.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: rules scorer with bands, confidence and templates`.

## Milestone C: Session and server

### Task 9: Session engine and emission rules

**Files:**
- Create: `demo/session.py`, `demo/testing.py`
- Test: `tests/integration/test_session.py`

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces:
  - `class Session` with constructor `Session(req: SessionRequest, zone: list[tuple[float,float]] | None, source: Source, detector: Detector, cfg: ScoringConfig, logs_dir: Path, fanout: Fanout, app_version: str)`. It has:
    - `.id: str` (uuid4)
    - `.start()`, which runs the loop in a background thread
    - `.stop(reason: str)`, which is idempotent, releases the source, and writes `session.ended`
    - `.latest_jpeg() -> bytes | None` (annotated with `supervision` box, trace and label annotators)
    - `.health() -> dict` with keys `status`, `session_id`, `fps`, `camera`, `model`, `input_size`, `device`
    - `.threat_objects`, `.source_id`
  - `make_session(tmp_path, frames_or_script, fps=10, detector_script=..., zone=None, threat_objects=["knife"]) -> Session` in `demo/testing.py`
  - Emission (§3 Emit):
    - `track.updated` on becoming eligible, a band change, a link formed or broken, and every `heartbeat_s` while above low;
    - `track.ended` on removal;
    - `source.health` from `HealthMonitor`;
    - the first line is always `session.started`, carrying the full config and its hash.
  - `raw.dwell_s` uses the gap tolerance `zone.dwell_gap_s` and is carried across `restarted_from`.
  - Point-in-polygon uses the bbox bottom-centre.
  - Any exception in the loop → `stop("error")` with the full traceback logged via `logging`.

**Steps:**

- [ ] **Step 1: Write the failing tests** (`SyntheticSource` + `FakeDetector`)
  - `test_first_line_session_started_with_config_hash`
  - `test_knife_held_emits_link_and_high` (a scripted person plus a knife inside the box for 3 s at 10 fps → a `track.updated` with `links[0].object_class=="knife"` and `band=="high"` at or before `ts ≤ first_knife_ts + 2.0`)
  - `test_heartbeat_every_2s_above_low`
  - `test_no_events_for_empty_scene` (only `session.started` and `session.ended`)
  - `test_zone_dwell_and_loiter` (a person inside the zone for 11 s → a loiter item)
  - `test_stop_releases_source_and_writes_stopped`
  - `test_exception_in_stage_ends_with_error` (the detector script raises at frame 5)
  - `test_log_verifies_ok`
  - `test_source_lost_ends_camera_lost` (a realtime source returns `None` → `session.ended {reason: "camera_lost"}`)

- [ ] **Step 2:** Run `uv run pytest tests/integration/test_session.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: session engine and emission rules`.

### Task 10: Step-down, idle stop, stills

**Files:**
- Modify: `demo/session.py`
- Test: `tests/integration/test_session_runtime.py`

**Interfaces:**
- Produces:
  - `class StepDown(cfg, large_available: bool)` with `.observe(ts, fps) -> tuple[str, int] | None`. It returns a new `(model, input_size)` after fps stays below `fps_floor` for `stepdown_after_s`. The order is large→small, then 640→480, then 480→320.
  - The Session emits `pipeline.changed {reason:"fps_below_floor"}` and swaps the model or size. Step-down is disabled when `source.realtime is False`.
  - `Session.last_client_seen(ts)` is called by the server. The session stops with `"idle"` after `idle_stop_s` with no subscriber.
  - Stills: when `req.save_stills` is true and a track enters high or critical, the session writes `logs/<id>/<event_id>.jpg` and adds `snapshot {path, sha256}` to that event.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_stepdown_order` (large 640 → small 640 → small 480 → small 320 → None)
  - `test_stepdown_disabled_for_non_realtime`
  - `test_pipeline_changed_event_emitted` (a realtime fake source reporting 5 fps)
  - `test_idle_stop_after_30s`
  - `test_stills_off_by_default`
  - `test_still_saved_with_hash_on_high` (the file's SHA-256 equals `snapshot.sha256`)

- [ ] **Step 2:** Run `uv run pytest tests/integration/test_session_runtime.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: step-down, idle auto-stop and per-session stills`.

### Task 11: Camera listing and permissions

**Files:**
- Create: `demo/cameras.py`
- Modify: `pyproject.toml`, adding `pyobjc-framework-AVFoundation; sys_platform == 'darwin'` and `pygrabber; sys_platform == 'win32'`
- Test: `tests/unit/test_cameras.py`

**Interfaces:**
- Produces:
  - `CameraInfo(id: str, name: str, index: int, backend: int)`
  - `list_cameras() -> list[CameraInfo]`. It never opens a device. It uses AVFoundation `AVCaptureDevice.devicesWithMediaType_` on macOS and `pygrabber.dshow_graph.FilterGraph().get_input_devices()` on Windows, and maps position i to OpenCV index i with `CAP_AVFOUNDATION` / `CAP_DSHOW`. Ids are `cam-<index>`.
  - `permission_status() -> Literal["authorized","not_determined","denied","unknown"]`. On Windows it always returns `"unknown"`.
  - `request_permission(timeout_s: float = 60) -> bool`, used on macOS only.
  - `open_webcam(cam: CameraInfo) -> Webcam`, which raises `CameraError(code)` with code `busy`, `missing`, `denied` or `windows_privacy`.
  - `MESSAGES: dict[str, str]`, containing the exact strings from §4 Camera.

**Steps:**

- [ ] **Step 1: Write the failing tests** (the backends are monkeypatched)
  - `test_list_uses_backend_names_and_indexes`
  - `test_list_never_opens_devices` (patching `cv2.VideoCapture` to raise must not break the call)
  - `test_messages_exact` (the denied and Windows-privacy strings are verbatim from §4)
  - `test_open_failure_maps_to_windows_privacy` (on Windows a listed device fails to open → `windows_privacy`)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_cameras.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: camera listing without opening devices`.

### Task 12: Server routes

**Files:**
- Create: `demo/server.py`
- Test: `tests/integration/test_server.py`

**Interfaces:**
- Consumes: `Session`, `make_session`, `list_cameras`, the config functions and `Fanout`.
- Produces:
  - `create_app(*, root: Path, token: str, port: int, session_factory: Callable[..., Session], cameras: Callable[[], list[CameraInfo]], shutdown: Callable[[], None]) -> FastAPI`
  - Routes are exactly those in the §1 table:
    - `POST /session` → `{session_id}`; a 409 while another start is in progress.
    - `POST /session/zone` → a new session with the active words and camera.
    - `DELETE /session` → 204.
    - `POST /quit` → 202, then `shutdown()`.
    - `GET /video` → `multipart/x-mixed-replace; boundary=frame`.
    - `WS /events`.
    - `GET /health`.
    - `GET /cameras`.
    - `GET` and `PUT /config`.
    - `GET /sessions`: `[{session_id, started_at, threat_objects, peak_band, ended_normally}]`, newest first.
    - `GET /sessions/{session_id}/events`.
  - `/sessions` reads only the first and last line of each `logs/*.jsonl`.
  - The static `web/dist/` is served at `/`.
  - `POST /session` camera handling: on macOS, if `permission_status()` is `not_determined`, call `request_permission()` and then open once more. A `CameraError(code)` returns 409 with `{code, message: MESSAGES[code]}`.

**Steps:**

- [ ] **Step 1: Write the failing tests** (`httpx`/`TestClient` with a fake `session_factory`; the token is supplied)
  - `test_go_starts_session_and_ws_receives_started`
  - `test_second_go_while_starting_is_409`
  - `test_zone_apply_keeps_words_and_camera_new_session_id`
  - `test_stop_is_204_and_idempotent`
  - `test_quit_calls_shutdown`
  - `test_put_config_out_of_range_422`
  - `test_put_config_hash_in_next_session_started`
  - `test_sessions_list_reads_only_first_and_last_lines` (a spy on file reads over a 50 MB log)
  - `test_sessions_list_skips_foreign_files` (`notes.txt` and a corrupted `.jsonl` are both skipped or marked truncated)
  - `test_crashed_session_listed_as_truncated`
  - `test_health_fields`
  - `test_go_maps_camera_error_to_message` (`denied` gives 409 with the §4 message verbatim)
  - `test_macos_not_determined_requests_then_retries_once`

- [ ] **Step 2:** Run `uv run pytest tests/integration/test_server.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: FastAPI routes`.

### Task 13: Local-server security

**Files:**
- Modify: `demo/server.py`
- Test: `tests/integration/test_security.py`

**Interfaces:**
- Produces:
  - Middleware order: `TrustedHostMiddleware(allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"])`, then the Origin check, then the token check.
  - Token: the header `X-Demo-Token`, or the query param `t` (needed for `<img src>` and WebSocket). It is compared with `hmac.compare_digest`.
  - Exempt from the token: `GET /` and `/assets/*`.
  - `session_id` path params are typed `uuid.UUID`.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_missing_token_403` (parametrized over every protected route)
  - `test_wrong_token_403`
  - `test_foreign_origin_on_post_403` (`Origin: https://evil.example`)
  - `test_foreign_origin_on_ws_rejected`
  - `test_foreign_host_400` (`Host: evil.example:8000`)
  - `test_non_uuid_session_id_422` (`/sessions/..%2F..%2Fetc/events`)
  - `test_index_served_without_token`

- [ ] **Step 2:** Run `uv run pytest tests/integration/test_security.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: host, origin and token protection for local server`.

### Task 14: Launch entry point (`python -m demo`)

**Files:**
- Create: `demo/__main__.py`
- Test: `tests/integration/test_main.py`

**Interfaces:**
- Produces:
  - `pick_port(start: int = 8000) -> int`
  - `read_lock(root) -> dict | None`, `write_lock(root, pid, port, token)`, `lock_is_live(lock) -> bool`
  - `main(argv=None) -> int`:
    - if a live lock exists, it opens that URL and returns 0;
    - otherwise it generates `secrets.token_urlsafe(32)`, writes `run/demo.lock`, starts uvicorn on `127.0.0.1:<port>`, and opens `http://127.0.0.1:<port>/?t=<token>` with `webbrowser`.
  - This is the only place that opens the browser.
  - It sets the §4 environment variables for the process if they are missing: `YOLO_CONFIG_DIR`, `YOLO_OFFLINE`, `YOLO_AUTOINSTALL`, `TORCH_HOME`, `XDG_CACHE_HOME`, all inside the root.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_pick_port_skips_busy`
  - `test_second_launch_opens_existing_and_exits` (patch `webbrowser.open`; assert the URL has the lock's port and token)
  - `test_stale_lock_replaced` (a dead PID)
  - `test_env_points_inside_root`

- [ ] **Step 2:** Run `uv run pytest tests/integration/test_main.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat: launch entry point with lock file and token`.

## Milestone D: Real model, install and offline

### Task 15: Model manifest and YOLO-World detector

**Files:**
- Create: `demo/models.py`, `models/manifest.json`
- Modify: `demo/detector.py` (add `YoloWorldDetector`), `pyproject.toml` (CLIP pinned by a hashed archive URL, **not** git)
- Test: `tests/offline/test_offline.py`, `tests/unit/test_models.py`

**Interfaces:**
- Produces:
  - `manifest.json` has entries `{name, url, sha256, size}` for `yolov8s-worldv2.pt`, `yolov8l-worldv2.pt` and the CLIP ViT-B/32 weights. Record the real hashes when downloading.
  - `verify(root) -> dict[str, bool]`
  - `ensure(root, names: list[str]) -> None`. It downloads a missing file to a `.part` file, checks its SHA-256, then renames it. With no network it raises `SetupError("First-time setup needs internet once.")`.
  - `select_model(cfg_model: str, device: str) -> str`: `auto` gives large on cuda/mps and small on cpu.
  - `YoloWorldDetector(weights: Path, device: str)` with `set_classes()` and `detect(frame, input_size)`. CLIP weights load from `models/` by path.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_verify_detects_corrupt_file`
  - `test_ensure_offline_message`
  - `test_select_model`
  - Offline test `test_real_detector_makes_no_network_calls` (marked `offline`; skipped if the models are absent). Under `pytest-socket` `--disable-socket --allow-hosts=127.0.0.1` it:
    - imports ultralytics;
    - loads the small model;
    - calls `set_classes(["person","knife"])`;
    - detects on 30 synthetic frames;
    - asserts no files were created outside `tmp_path` (snapshot `Path.home()` mtimes before and after);
    - asserts no `pip` subprocess was spawned (patch `subprocess.run` and `subprocess.Popen` to fail on "pip").

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_models.py tests/offline -v`. Expected: FAIL.

- [ ] **Step 3:** Implement. Download the real files once with `uv run python -c "from demo.models import ensure; ..."` and record their SHA-256 in the manifest.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Record the measured fps (small model, 640, this machine) in `docs/knowledge/2026-xx-xx-fps-<machine>.md`.

- [ ] **Step 6:** Commit with `feat: pinned models and YOLO-World detector (offline-safe)`.

### Task 16: Torch variants, setup step and launchers

**Files:**
- Modify: `pyproject.toml`, `uv.lock`
- Create: `demo/setup.py`, `Start Demo.bat`, `Start Demo.command`, `bin/uv.version` (pinned version + SHA-256 per platform)
- Test: `tests/unit/test_setup.py`, `tests/unit/test_launcher_files.py`

**Interfaces:**
- **`pyproject.toml`:**
  - extras `cpu = ["torch", "torchvision"]` and `cu12x = ["torch", "torchvision"]`;
  - `[tool.uv] conflicts = [[{extra="cpu"},{extra="cu12x"}]]`;
  - `[tool.uv.sources]` maps torch and torchvision to index `pytorch-cpu` for the cpu extra and `pytorch-cu12x` for the cu12x extra (explicit indexes);
  - the darwin-x86_64 pin set: `torch==2.2.2`, `torchvision==0.17.2` and `numpy<2`, plus the opencv, ultralytics and supervision versions that resolve with them, applied via `sys_platform == 'darwin' and platform_machine == 'x86_64'` markers.
- **`python -m demo.setup --variant <cpu|cu12x|mac>`:**
  - runs `models.ensure()` for the device's models (small always; large as well when the variant is cu12x or mac arm64);
  - for cu12x, checks `torch.cuda.is_available()` and exits with code 3 plus the message "NVIDIA GPU not usable — continuing on CPU" when it is false;
  - prints plain-English errors only.
- **`Start Demo.bat`:**
  - `cd /d "%~dp0"`;
  - refuses to run when the path contains `\AppData\Local\Temp\` or `.zip\`, with the message "Extract the zip first, then open the extracted folder.";
  - downloads the pinned `uv` to `bin\` if it's missing and verifies its SHA-256 with `certutil`;
  - sets `UV_INSTALL_DIR`, `UV_NO_MODIFY_PATH=1`, `UV_PYTHON_PREFERENCE=only-managed`, `UV_PYTHON_INSTALL_DIR=.uv\python` and `UV_CACHE_DIR=.uv\cache`, and always calls `bin\uv.exe` by full path;
  - picks `cu12x` if `where nvidia-smi` succeeds, otherwise `cpu`;
  - runs `bin\uv.exe run --frozen --extra <v> python -m demo.setup --variant <v>`. On exit code 3 it re-runs with `cpu`;
  - then runs `bin\uv.exe run --frozen --extra <v> python -m demo`.
- **`Start Demo.command`:**
  - `cd "$(dirname "$0")"`;
  - does the same with `shasum -a 256`, variant `mac`, and no extra flag (the default torch);
  - is committed with mode 100755 (`git update-index --chmod=+x`).

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_setup_cuda_unavailable_exits_3` (patch torch)
  - `test_setup_models_for_variant`
  - `test_launchers_have_zip_guard_and_pinned_uv` (greps both launcher files for the guard string, the `UV_PYTHON_PREFERENCE=only-managed` line and the SHA check)
  - `test_command_file_is_executable_in_git` (`git ls-files -s "Start Demo.command"` starts with `100755`)
  - `test_lock_resolves_all_variants` (runs `uv lock --check`)

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_setup.py tests/unit/test_launcher_files.py -v`. Expected: FAIL.

- [ ] **Step 3:** Implement the launchers, the setup step and the pyproject changes; then run `uv lock`.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5: Manual check on this machine.** Double-click the launcher from a fresh extraction. The browser should open with a token, `/health` should respond, and no new files should appear outside the folder.

- [ ] **Step 6:** Commit with `feat: launchers, torch variants and setup step`.

## Milestone E: Web UI

### Task 17: Web scaffold, theme, types and API client

**Files:**
- Create: `web/` (Vite React TS), `web/src/index.css` (Tailwind v4 + theme tokens), `web/src/fonts/` (self-hosted woff2 via `@fontsource/*`), `web/components.json` (shadcn), `web/src/api/types.ts` (generated), `web/src/api/client.ts`, `web/src/lib/threatWords.ts`, `web/src/lib/zoneMap.ts`, `web/scripts/gen-types.mjs`
- Test: `web/src/lib/*.test.ts`, `web/src/api/client.test.ts`

**Interfaces:**
- Produces:
  - `api` in `client.ts`: `startSession(req)`, `applyZone(zone)`, `stop()`, `quit()`, `health()`, `cameras()`, `getConfig()`, `putConfig(cfg)`, `sessions()`, `sessionEvents(id)`, `eventsSocket(): WebSocket` and `videoUrl(): string`. Each attaches the token, which is read once from `?t=` at startup and kept in memory. `eventsSocket` and `videoUrl` carry it as `?t=`.
  - `parseThreatWords(input: string): { words: string[]; error?: string }`, mirroring Task 1's rules and messages.
  - `clientToFrame(x, y, box: DOMRect, frameW, frameH): [number, number] | null`. It accounts for `object-fit: contain` letterboxing and returns `null` outside the image.
  - `npm run gen:types` runs json-schema-to-typescript from `../schemas`. `npm run check:types` fails on drift.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_parse_threat_words`:
    - `"Knife,, knife , "` → `["knife"]`;
    - `"person"` gives the error "People are always tracked — type an object instead.";
    - six words gives an error.
  - `test_zone_click_maps_through_letterbox`:
    - a 4:3 frame in a 16:9 box: a click in the left bar → `null`, and the image centre → `[0.5, 0.5]`;
    - a portrait 9:16 frame is handled the same way.
  - `test_token_attached_to_every_request` (a mocked `fetch`)

- [ ] **Step 2:** Run `cd web && npm test -- --run`. Expected: FAIL.

- [ ] **Step 3:** Implement. Initialise shadcn with the Global Constraints tokens. Page title: "Object Classification Demo".

- [ ] **Step 4:** Run `cd web && npm test -- --run && npm run check:types`. Expected: PASS.

- [ ] **Step 5:** Commit with `feat(web): scaffold, theme, generated types, API client`.

### Task 18: Operator controls, video, zone, status

**Files:**
- Create: `web/src/components/ThreatControl.tsx`, `VideoView.tsx`, `StatusBar.tsx`, `web/src/App.tsx`
- Test: `web/src/components/*.test.tsx`

**Interfaces:**
- `ThreatControl`:
  - a words input, a camera `<Select>` (from `api.cameras()`), a Save stills `<Switch>` (reset to off after each Go), and buttons Go / Stop / Quit;
  - inline validation errors from `parseThreatWords`;
  - a "Recording stills" badge while the active session has `save_stills`.
- `VideoView`:
  - `<img src={api.videoUrl()}>` with a `<canvas>` overlay;
  - clicks add polygon points via `clientToFrame`;
  - buttons: Apply zone (→ `api.applyZone`), Clear zone;
  - the zone stays drawn until the next Go or Stop.
- `StatusBar`: session id, fps, camera, model, input size, device, and the latest `source.health` message.
- After Quit, the page shows "Demo closed — you can close this tab".
- The inputs start blank on load and after Go.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_go_disabled_until_valid_words_and_camera`
  - `test_save_stills_resets_after_go`
  - `test_recording_badge_visible_when_on`
  - `test_apply_zone_sends_polygon_only`
  - `test_quit_shows_closed_message`
  - `test_error_end_shows_restart_message` (`session.ended {reason:"error"}` shows "Something went wrong — click Go to restart")

- [ ] **Step 2:** Run `cd web && npm test -- --run`. Expected: FAIL.

- [ ] **Step 3:** Implement.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `feat(web): controls, video with zone drawing, status bar`.

### Task 19: Event feed, evidence, alert, settings, history; build

**Files:**
- Create: `web/src/components/EventFeed.tsx`, `EvidencePanel.tsx`, `CriticalAlert.tsx`, `SettingsDrawer.tsx`, `HistoryDrawer.tsx`, `web/src/lib/eventStore.ts`
- Modify: `web/dist/` (built)
- Test: the matching `*.test.ts(x)` files

**Interfaces:**
- `eventStore`: a reducer over `Event` that keeps the latest state per track, plus a bounded feed of the last 500 events.
- `EvidencePanel`: the selected track's `summary`, an evidence table (text, contribution, supporting/contradictory tag), confidence dimensions and unknowns. Every band shows its name as text.
- `CriticalAlert`: a red banner and highlight. A Web Audio tone (880 Hz, 200 ms) plays **once per entry into critical** per track. The mute toggle is stored in `localStorage` inside try/catch.
- `SettingsDrawer` (vaul):
  - one slider per `ScoringConfig` field, with ranges taken from the schema's `minimum` and `maximum`;
  - Save → `api.putConfig`, then the message "Applies on next Go";
  - Reset to defaults.
- `HistoryDrawer` (vaul): the `api.sessions()` list (start time, words, peak band, "ended normally / truncated"). Opening one loads `sessionEvents` into the store in replay mode.

**Steps:**

- [ ] **Step 1: Write the failing tests**
  - `test_store_bounded_500`
  - `test_tone_once_per_entry` (critical → high → critical plays 2 tones; critical held plays 1)
  - `test_mute_respected`
  - `test_band_label_text_present`
  - `test_settings_ranges_from_schema`
  - `test_history_replay_populates_panels`

- [ ] **Step 2:** Run `cd web && npm test -- --run`. Expected: FAIL.

- [ ] **Step 3:** Implement. Then run `npm run build` to update `web/dist/`.

- [ ] **Step 4:** Run `cd web && npm test -- --run`, then `uv run pytest tests/integration/test_security.py::test_index_served_without_token -v`. Expected: PASS, and the built page is served.

- [ ] **Step 5:** Commit with `feat(web): events, evidence, alert, settings and history; build dist`.

## Milestone F: CI, clips, docs, acceptance

### Task 20: Continuous integration

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Matrix: `windows-latest` and `macos-latest`. The jobs are:
  1. `uv sync --frozen --extra cpu` (on macOS without the extra);
  2. `uv lock --check`;
  3. `uv run ruff check`;
  4. `uv run pytest tests/unit tests/integration -v`;
  5. restore `models/` with `actions/cache` keyed on `hashFiles('models/manifest.json')`, then `uv run python -m demo.setup --variant cpu` on a cache miss, then `uv run pytest tests/offline -v`;
  6. `cd web && npm ci && npm test -- --run && npm run check:types`;
  7. `python scripts/export_schemas.py --check`.
- `tests/pipeline` is excluded because it runs locally.

**Steps:**

- [ ] **Step 1:** Write the workflow.

- [ ] **Step 2:** Push the branch and confirm both matrix legs are green. Expected: all steps pass.

- [ ] **Step 3:** Commit with `ci: windows + macos matrix with offline layer`.

### Task 21: Clip pipeline tests

**Files:**
- Create: `tests/pipeline/test_clips.py`, `tests/clips/README.md` (what each clip must show, and consent)
- Add (LFS): `tests/clips/*.mp4`, recorded by the team at 5–10 s each

**Interfaces:**
- Clips:
  - `empty_room.mp4`
  - `person_walking.mp4`
  - `person_knife.mp4`
  - `apple_table.mp4`
  - `handheld.mp4`
  - `replica_gun.mp4`
  - `knife_gun_two_words.mp4`
- Each test uses `make_session` with `VideoFile` and the real detector, and asserts outcomes (not exact numbers).
- The module is skipped if `tests/clips/*.mp4` are LFS pointers or absent.

**Steps:**

- [ ] **Step 1: Write the tests**
  - `test_knife_links_and_reaches_high`
  - `test_empty_room_no_track_events`
  - `test_apple_scored_unattended`
  - `test_handheld_reports_camera_moving`
  - `test_replica_gun_links`
  - `test_one_prop_two_words_one_link`
  - `test_skip_when_clips_missing`

- [ ] **Step 2: Human step.** Record the clips with consenting team members, then `git lfs track` and add them.

- [ ] **Step 3:** Run `uv run pytest tests/pipeline -v`. Expected: PASS, or clear failures that turn into tuning notes in `docs/knowledge/`.

- [ ] **Step 4:** Commit with `test: recorded clip pipeline tests (LFS)`.

### Task 22: Documentation

**Files:**
- Create: `docs/setup-guide.md`, `docs/release-checklist.md`, `docs/knowledge/README.md` (note template: observed / evidence / implication)
- Modify: `AGENTS.md` (full), `README.md`, and `docs/design.md` (§1 tree: add `motion.py`, `health.py`, `cameras.py`, `models.py`, `setup.py`, `verify_log.py`, `testing.py`)

**Interfaces:**
- **`AGENTS.md`:**
  - install, run and test commands per layer:
    - `uv run pytest tests/unit`
    - `tests/integration`
    - `tests/offline`
    - `tests/pipeline`
    - `cd web && npm test`
  - how to confirm the demo is running: read `run/demo.lock`, then `curl -H "X-Demo-Token: <token>" http://127.0.0.1:<port>/health`;
  - the stage map;
  - the rules: contracts first; product decisions go in `../scrye-docs`; a field that is always the same value is dropped; the definition of done.
- **`docs/setup-guide.md`:**
  - per-platform steps with screenshot placeholders to fill in during the release check:
    - extract the zip;
    - SmartScreen: More info → Run anyway;
    - Sequoia: System Settings → Privacy & Security → Open Anyway;
    - camera permission for Terminal;
    - Windows camera privacy.
  - download sizes (~1 GB; ~3.5 GB NVIDIA);
  - updating (copy `logs/` and `config/scoring.json`; stills included);
  - a troubleshooting table keyed by every message string in `cameras.MESSAGES` and `SetupError`;
  - the real-knife safety note;
  - fps per machine.
- **`docs/release-checklist.md`:** the §5 manual checklist, verbatim.

**Steps:**

- [ ] **Step 1: Write a failing docs check.** Add `tests/unit/test_docs.py`:
  - `test_every_user_message_in_troubleshooting` (each string in `cameras.MESSAGES`, plus "First-time setup needs internet once." and the zip-guard message, appears in `docs/setup-guide.md`);
  - `test_claude_md_points_to_agents` (`CLAUDE.md` equals `@AGENTS.md\n`).

- [ ] **Step 2:** Run `uv run pytest tests/unit/test_docs.py -v`. Expected: FAIL.

- [ ] **Step 3:** Write the docs.

- [ ] **Step 4:** Run the same command. Expected: PASS.

- [ ] **Step 5:** Commit with `docs: setup guide, AGENTS.md, release checklist, knowledge template`.

### Task 23: Acceptance run and release check (human-in-the-loop)

**Files:**
- Create: `docs/knowledge/<date>-acceptance-<machine>.md`, one per machine type (Apple Silicon, Intel Mac, Windows CPU, Windows NVIDIA)

**Steps:**

- [ ] **Step 1: Build the zip** with `git archive --format=zip -o demo.zip HEAD`. Confirm `tests/clips` is absent and `Start Demo.command` is executable after extraction on macOS.

- [ ] **Step 2: Run the release checklist** on each fresh machine. Fill in the setup-guide screenshots.

- [ ] **Step 3: Acceptance at 640 px** (§5). Record the machine, device, model and input size.
  - **Hits:** knife, replica gun, apple and book at 2–3 m; 10 raises each; latency from first object detection `ts` to link `ts`.
  - **Pass:** ≥ 8/10 link within 2 s and reach high.
  - **False links:** "knife" typed with apple, book, cup and phone; 10 raises each; pass at ≤ 2/10 each.

- [ ] **Step 4:** Where the bar fails, record it as "below bar at 640" with the likelihoods, and propose config tuning in the note. Do not change the spec silently.

- [ ] **Step 5:** Commit with `docs: acceptance results`.
