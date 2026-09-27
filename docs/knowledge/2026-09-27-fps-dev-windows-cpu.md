---
title: Detector fps on the dev Windows laptop (CPU)
date: 2026-09-27
tags: [fps, model, cpu, windows]
machine: 13th Gen Intel Core i7-13620H (16 logical CPUs), 16 GB RAM, Windows 11, no CUDA
device: cpu
model: small (yolov8s-worldv2)
status: measured
---

# Detector fps on the dev Windows laptop (CPU)

## Observed

| input size | fps  | ms/frame |
|-----------:|-----:|---------:|
| **640**    | 11.6 | 86.3     |
| 480        | 18.0 | 55.5     |
| 320        | 30.5 | 32.8     |

## Evidence

- `YoloWorldDetector(models/yolov8s-worldv2.pt, "cpu")`, classes
  `["person", "knife", "gun", "bat"]`, one synthetic 640×480 random-noise frame,
  5 warm-up frames, then 50 timed `detect()` calls per size.
- torch 2.14.0+cpu (8 intra-op threads), ultralytics 8.4.163, Python 3.12.
- Detector only: tracker, linker, scorer, annotation and JPEG encoding are not included.

## Implication

- At 640 the detector alone is just above the 10 fps step-down floor; with the rest of the
  pipeline and a real webcam this machine may step down to 480 (below the acceptance bar
  at 640). Re-measure end to end with `/health` fps once the camera path is exercised.
