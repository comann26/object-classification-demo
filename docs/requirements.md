---
title: Demo requirements
status: draft
date: 2026-09-26
related:
  - ../README.md
  - ../../scrye-docs/decisions/2026-09-26-camera-threat-scoring.md
---

# Demo requirements

These are the requirements gathered so far for this demo. How they are met is in [design.md](design.md). Product-level decisions live in `scrye-docs` and are only linked here.

## Audience and success

- **Audience:** internal team only. It is a proof of capability and a learning tool.
- **Success means:**
  1. A person holding a typed object is **linked to it and scored high, reliably at ~2–3 m in normal room light.** "Reliably" means **at least 8 of 10 attempts** link within 2 s and reach high, **measured at full 640 px input**. Holding one threat object alone scores high (link = +55).
  3. **Few false links:** with "knife" typed, each harmless prop (apple, book, cup, phone) links **at most 2 of 10** times.
  2. Someone unfamiliar with the system can **read why a score is what it is** from the evidence panel. Every event carries plain-English text: a one-line summary plus one sentence per evidence item.
- **Test props:** a real kitchen knife (the setup guide carries a safety note), toy or replica weapons (orange-tip), and harmless objects (apple, book, cup, phone).

## Who builds it

- **Mostly AI (Claude), with the team reviewing.** `AGENTS.md` and the implementation plan must be detailed enough for AI-driven development: exact commands, file ownership, and conventions.

## Setup

- **Setup must be easy for a non-technical person.** There should be no terminal commands, no manual Python install, and no config editing. They download the demo, double-click, and it runs.
- Setup instructions come in two forms:
  - **human:** a few short steps with screenshots;
  - **AI:** a step-by-step section an AI assistant can follow to install and run the demo.
- **Platforms: Windows and macOS only.** Linux is not a target.
- **Hardware the team will use:** Apple Silicon Macs, Intel Macs, Windows laptops without an NVIDIA GPU, and Windows with an NVIDIA GPU.
- **Minimum acceptable speed: ~10 fps.**
- **Machines are personally administered.** No IT policies or blocked downloads to plan around.
- **Self-contained folder:** everything lives inside the demo folder: private Python, libraries, models, caches, settings and session logs. Nothing is written elsewhere on the machine. A new version is a new zip. It re-downloads on first launch (about 1 GB on CPU and Mac, about 4.7 GB on Windows + NVIDIA). History and tuning are lost unless `logs/` and `config/scoring.json` are copied across (the setup guide says so).
- **Minimum macOS: 14 (Sonoma) on Apple Silicon, 12 (Monterey) on Intel** — to be verified on real machines.
- **Distribution channel: undecided.** Design for a plain zip; the zip excludes developer-only files such as test clips.
- **Delivery: a launcher, not a packaged app.** `Start Demo.bat` (Windows) and `Start Demo.command` (macOS). The first launch needs internet once: it sets up a private Python via `uv`, installs the libraries, downloads the pinned model and checks its checksum. After that it runs offline and opens the browser.
- **Unsigned is acceptable.** No code signing or notarization. The one-time OS warnings (macOS Gatekeeper, Windows SmartScreen) are acceptable and will be documented with screenshots.
- Works fully offline after setup. Model files are pinned with checksums, and nothing is downloaded unexpectedly at runtime. No telemetry.

## Input

- A live webcam on the demo machine. **Webcam only: no recorded-clip fallback in the page.** A **camera dropdown** next to Go picks among the available cameras.
- Later inputs (standalone cameras, body cams, and data from other systems in our standard or an open one) must fit without code changes to the core.

## Operator controls

- A local web page, served by the demo itself, with no internet needed.
- A text box for the **threat objects**: a short comma-separated list (up to 5, e.g. "knife, gun, bat"), all scored the same way. Plus a **Go** button.
- **Go** resets the camera and the classification/tracking pipeline for the new threat objects and starts a new session.
- **Threat words may not name people** ("person", "people", "man", "woman", "child"…). The page rejects them with: "People are always tracked — type an object instead."
- **Zone:** drawn on the live video **after Go**. **Apply zone** starts a new session with the same threat words and camera plus the zone.
- **Stop** ends the session and turns the camera off. **Quit** shuts the whole demo down cleanly from the page. If the page is closed, the session stops on its own after 30 s.
- **Only this page may control the demo:** other websites open in the same browser must not be able to reach the local server.
- **Save stills:** a per-session switch next to Go, off by default and reset to off on every Go. A visible "Recording stills" badge shows while it is on.
- **Tuning with sliders:** a settings drawer with sliders for scoring weights and thresholds. Changes apply on the next Go and are saved to the config file, so every event still records exactly which settings produced it.
- **No remembered inputs:** threat words, camera and zone start blank on every page load and after each Go.
- **Session history:** a drawer listing past sessions. Opening one shows its events and evidence, without video, because video isn't stored.
- **Alerts:** when a track reaches **critical**, the page shows a red highlight and banner **and plays a short tone**. A mute toggle is provided.
- **Branding: neutral** ("Object Classification Demo"). No company name or logo; Omega's styling is kept so panels port cleanly.

## Detection and awareness

- Open-vocabulary detection, so any typed object name works (e.g. YOLO-World).
- People and the threat object are tracked across frames, with direction of motion.
- **Small objects at distance:** NVIDIA and Apple Silicon machines **start on the larger YOLO-World model**, falling back to the small one automatically if below 10 fps. CPU machines use the small model. If a slow machine has to shrink its input below 640 px to hold 10 fps, it is recorded as below the bar.
- **Linking an object to a person:** when the threat object overlaps a person's box (widened a little) for several frames, the person carries the threat. The link fades over a few seconds if the object leaves view, and that uncertainty is reported. A threat object linked to no one is scored on its own.

## Scores

- A person linked to **several** threat objects gets the link points **for each object** (clamped to 100). The summary and evidence name every object.
- Every object gets two separate scores:
  - **threat** (advisory);
  - **confidence** (how much to trust the observation).
- The demo's scoring rules and weights are in [design.md §3](design.md#3-pipeline-logic). The product-level scoring policy is a separate, proposed decision in [scrye-docs](../../scrye-docs/decisions/2026-09-26-camera-threat-scoring.md). The demo does not settle it.

## Output

- Overlays on the video: boxes, track trails, direction, both scores.
- A structured event stream, shaped for Guardian Intelligence, which is the seed of the future API.
- **Local only:** events go to the page and to the JSONL logs, nowhere else. No webhook or export to Guardian in the demo.

## Production note: real-world direction needs camera pose

In the demo, `heading_deg` is direction **on screen** (0° = toward the top of the frame, clockwise), because the webcam's position and orientation are unknown. In production, if each camera's **geo-coordinates, compass bearing, tilt and mounting height** were known (surveyed, or from GPS and IMU on a body cam), then:
- screen motion could be converted to **real-world heading** (e.g. "moving north-east") and **speed in m/s**;
- people and objects could be given **map positions**;
- zones could be checked against Guardian's real geofences rather than a screen-drawn mapping;
- output in geolocated standards such as Cursor on Target would become possible.

The data format should add a camera-pose field on the source and world-coordinate fields on tracks when this arrives, as a minor version bump.

## Approved tech stack (2026-09-26)

Python 3.12 via `uv` (lockfile with hashes) · Ultralytics YOLO-World (`yolov8s-worldv2`) · `supervision` (ByteTrack, zones, overlays) · OpenCV · PyTorch (CPU / MPS / CUDA) · FastAPI + uvicorn (MJPEG video, WebSocket events) · Pydantic models exported to JSON Schema in `schemas/` · versioned JSON scoring config · hash-chained JSONL event log · pytest with recorded clips · ruff.

**Presentation layer: React + Vite**, chosen to match the Guardian / OmegaGuard Pro portal so UI panels can be reused there.
- TypeScript. **CSS and UI: the same libraries as Omega**, confirmed from its production bundle on 2026-09-26:
  - **Tailwind CSS v4**;
  - **shadcn/ui** (Radix primitives, CSS variable tokens);
  - **lucide-react** icons;
  - `vaul` drawers.
- Omega's theme tokens are copied: dark background, gold primary `hsl(46 60% 52%)`, the shadcn token names. Its Google Fonts (Montserrat, Oswald, Rajdhani, IBM Plex Mono…) are **self-hosted** so the demo stays offline.
- TS types generated from `schemas/`.
- The built `web/dist/` is committed and served by FastAPI, so end users and the launchers never need Node. Node is a developer-only tool.
- Trade-off accepted: a second toolchain and a large npm dependency tree (a second lockfile and SBOM to audit for CMMC).

## Licensing risk: Ultralytics is AGPL-3.0

- **Fine for this internal demo.**
- **Commercial use needs a decision:** shipping Ultralytics inside a product, or offering it as a network service to clients, requires either releasing that product's source under AGPL or buying an Ultralytics Enterprise license.
- **Mitigation built into the design:** the detector sits behind one stage boundary, so it can be swapped for a model with a permissive license (e.g. OWLv2 or Grounding DINO, both Apache-2.0, currently too slow for real time on a laptop CPU) or run through ONNX, without changing other stages.
- **Owner:** undecided. Must be resolved before any client-facing or commercial deployment.

## Open questions

- Resolved: open standards for detection data. We use our own JSON Schema, aligned with ONVIF Profile M and SAPIENT; adapters come later. See [the research](../../scrye-docs/research/2026-09-26-sensor-data-standards.md).
- Unresolved: the AGPL licensing decision (above). The product policy on weapons and named threat objects is in `scrye-docs`.
