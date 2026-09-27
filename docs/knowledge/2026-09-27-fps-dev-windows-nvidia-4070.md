---
title: Detector fps on the dev Windows laptop (NVIDIA RTX 4070, cu12x)
date: 2026-09-27
tags: [fps, model, cuda, windows, torch-variants]
machine: 13th Gen Intel Core i7-13620H, 16 GB RAM, NVIDIA GeForce RTX 4070 Laptop GPU (8 GB, driver 617.14), Windows 11
device: cuda
model: small (yolov8s-worldv2) and large (yolov8l-worldv2)
status: measured
---

# Detector fps on the dev Windows laptop (NVIDIA RTX 4070, cu12x)

## Observed

| model | input size | fps   | ms/frame |
|-------|-----------:|------:|---------:|
| large | **640**    | 51.7  | 19.3     |
| large | 480        | 73.4  | 13.6     |
| large | 320        | 76.0  | 13.1     |
| small | **640**    | 91.3  | 10.9     |
| small | 480        | 101.4 | 9.9      |
| small | 320        | 96.6  | 10.4     |

Peak CUDA memory allocated by torch: ~1.1 GB (small), ~1.6 GB (large, same process).

## Evidence

- `bin/uv.exe run --frozen --extra cu12x python -c "import torch; ..."` printed
  `2.14.0+cu126 True NVIDIA GeForce RTX 4070 Laptop GPU`. The cu12x extra pulls torch and
  torchvision from `https://download.pytorch.org/whl/cu126`; the torch wheel is 2.4 GiB.
- `YoloWorldDetector(models/<file>, "cuda")`, classes `["person", "knife", "gun", "bat"]`,
  one synthetic 640×480 random-noise frame, 5 warm-up calls, then 50 timed `detect()` calls
  per size, bracketed by `torch.cuda.synchronize()`.
- torch 2.14.0+cu126, ultralytics 8.4.163, Python 3.12. Detector only: tracker, linker,
  scorer, annotation and JPEG encoding are not included.
- Below ~13 ms/frame the time is dominated by per-call overhead (pre/post-processing on the
  CPU, host↔device copies), so smaller input sizes barely help.

## Implication

- `select_model("auto", "cuda")` → large at 640 runs ~5× faster than the CPU small model
  (11.6 fps, see 2026-09-27-fps-dev-windows-cpu.md): far above the 10 fps step-down floor, so
  an NVIDIA laptop should never step down.
- The first-launch download on Windows + NVIDIA is dominated by the cu126 torch wheel
  (2.4 GiB compressed; the uv cache held ~4.7 GB after one install), so the ~3.5 GB figure
  in docs/design.md §4 is a lower bound.
