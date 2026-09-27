---
title: Release checklist
status: living — not yet run end to end
date: 2026-09-27
related:
  - design.md
  - setup-guide.md
  - knowledge/README.md
---

# Release checklist

Run this by hand before calling a build ready to hand to the team. It has two parts: the
**manual release checklist** (docs/design.md §5, verbatim below) and the **acceptance check**
(also §5), recorded per machine type. Record results (and add screenshots) in this file, and
add a `docs/knowledge/` note for anything worth remembering for next time.

**Known gaps right now:**
- The Mac launcher (`Start Demo.command`) **has never been run on a real Mac yet.** Everything
  about the Mac steps below is inferred from the code and from `docs/design.md`, not observed.
- CI (design.md §5 "Continuous integration") is **not built — TODO.** This checklist is
  currently the only release gate.
- The clip pipeline test harness (`tests/pipeline`, design.md §5 layer 4) is **not built —
  TODO.** The acceptance check below has to be done by hand until it exists.
- Every screenshot placeholder in `docs/setup-guide.md` is a **TODO**; fill them in while
  running this checklist on each real machine.

## Manual release checklist (docs/design.md §5)

- [ ] Use a fresh Windows machine (CPU and NVIDIA) and a fresh Mac (Apple Silicon and Intel).
- [ ] Download the zip built with `git archive --format=zip` and extract it.
- [ ] Get past SmartScreen ("More info → Run anyway"), or the macOS warning (on Sequoia: System
      Settings → Privacy & Security → "Open Anyway").
- [ ] Allow the camera, type "knife", click Go, and see a link.
- [ ] **Second launch with Wi-Fi off** reaches Go.
- [ ] **No new files outside the demo folder.**
- [ ] The Mac launcher is still executable after extraction.
- [ ] A second double-click reopens the running instance.

## Camera-index-order verification (Task 11 note)

`demo/cameras.py` assumes the OpenCV index of a listed device equals its position in the
platform's own device list (AVFoundation on macOS, DirectShow on Windows) — see the module
docstring and design.md §4 "Listing (`GET /cameras`)". This assumption has **not yet been
verified on real hardware with more than one camera attached.**

- [ ] On a machine with **two or more cameras** (e.g. a laptop's built-in camera plus a USB
      webcam), confirm that the order returned by `GET /cameras` matches the order the OS lists
      them in, and that selecting each one by name in the UI opens the *correct* physical camera
      (check by covering one and confirming only the expected feed goes dark).
- [ ] Do this on both Windows and macOS.
- [ ] Record the result (pass/fail, machine, camera models) in a `docs/knowledge/` note. If it
      fails, `demo/cameras.py`'s indexing needs a fix before release.

| Platform | Machine | Cameras tested | Result | Date |
|---|---|---|---|---|
| Windows | TBD | TBD | TBD | TBD |
| macOS | TBD | TBD | TBD | TBD |

## Acceptance check (docs/design.md §5 "Acceptance check (the success bar)")

Only runs at **640 px** count. Record the machine, device, model, and input size with the
result in `docs/knowledge/`. A stepped-down machine is recorded as "below bar at 640".

- **Hits:** at 2–3 m in normal room light, type the prop's own word (kitchen knife → "knife",
  replica gun → "gun", apple → "apple", book → "book"), then raise the prop 10 times. Measure
  latency from the object track's first detection `ts` to the link-formed event `ts`.
  **≥ 8 of 10** must link within 2 s and reach `high`.
- **False links:** with "knife" typed, raise each harmless prop (apple, book, cup, phone) 10
  times. **At most 2 of 10** per prop may link. Record the likelihoods.

### Results by machine type

| Machine type | Device | Model | Input size | Hits (of 10) | False links (per prop, of 10) | Below bar at 640? | Date | Notes |
|---|---|---|---|---|---|---|---|---|
| Apple Silicon Mac | TBD | TBD | 640 | TBD | TBD | TBD | TBD | never run on real Mac |
| Intel Mac | TBD | TBD | 640 | TBD | TBD | TBD | TBD | never run on real Mac |
| Windows, CPU only | TBD | TBD | 640 | TBD | TBD | TBD | TBD | detector-only fps measured (see knowledge/), not the full pipeline |
| Windows, NVIDIA | TBD | TBD | 640 | TBD | TBD | TBD | TBD | detector-only fps measured (see knowledge/), not the full pipeline |

## Screenshots to capture while running this checklist

All of these are placeholders in `docs/setup-guide.md` — replace them with real screenshots
taken during this checklist, on the actual machine being tested:

- [ ] Windows: extracting the zip in File Explorer
- [ ] Windows: SmartScreen "More info"
- [ ] Windows: SmartScreen "Run anyway"
- [ ] Windows: camera privacy setting ("Let desktop apps access your camera")
- [ ] Mac: extracting the zip in Finder
- [ ] Mac: Sequoia Privacy & Security "Open Anyway"
- [ ] Mac: camera permission prompt naming Terminal

## Sign-off

| Machine | Tester | Date | Passed manual checklist | Passed acceptance check | Notes |
|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD |
