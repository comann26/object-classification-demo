"""First-run setup, called by the launchers: `python -m demo.setup --variant <cpu|cu12x|mac>`.

Downloads (or re-verifies) the pinned model files this device will use
(docs/design.md §4 "Model and offline"). Exit codes, read by `Start Demo.bat`:
0 ok; 2 a plain-English setup problem (already printed); 3 the cu12x torch
cannot see the GPU, so the launcher re-runs setup with `cpu`.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from demo import models

ROOT = Path(__file__).resolve().parent.parent
NO_GPU_MESSAGE = "NVIDIA GPU not usable — continuing on CPU"


def needed_models(variant: str) -> list[str]:
    """small + CLIP always; large where `select_model("auto", …)` will pick it (cuda, mps)."""
    names = [models.SMALL, models.CLIP]
    if variant == "cu12x" or (variant == "mac" and platform.machine() == "arm64"):
        names.append(models.LARGE)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m demo.setup")
    parser.add_argument("--variant", choices=["cpu", "cu12x", "mac"], required=True)
    variant = parser.parse_args(argv).variant

    if variant == "cu12x":
        try:
            import torch  # noqa: PLC0415

            usable = torch.cuda.is_available()
        except (ImportError, OSError, RuntimeError):  # e.g. a CUDA DLL that will not load
            usable = False
        if not usable:
            print(NO_GPU_MESSAGE, flush=True)
            return 3
    try:
        models.ensure(ROOT, needed_models(variant))
    except models.SetupError as exc:
        print(exc.message, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
