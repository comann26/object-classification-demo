"""Image-quality confidence dimension and source-health signals.

`image_quality` is the pure per-frame formula (see docs/design.md §2). The
brightness and sharpness numbers it returns feed `ConfidenceDimensions.image_quality`.

`HealthMonitor` is stateful across frames of one source: it detects black/frozen/
blurred frames, sudden scene changes, and a measured fps below the configured
floor, and reports each condition once on entry (see docs/design.md §4 Camera).
"""

from __future__ import annotations

import cv2
import numpy as np

from demo.config import ScoringConfig
from demo.contracts import Frame

HealthCode = str  # "fps_low" | "frozen_frame" | "black_frame" | "blur" | "scene_change"
HealthEvent = tuple[HealthCode, float, str]


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _brightness(luma: float, lo: int, hi: int) -> float:
    if luma < lo:
        return _clamp01(luma / lo)
    if luma > hi:
        return _clamp01((255 - luma) / (255 - hi))
    return 1.0


def image_quality(img: np.ndarray, cfg: ScoringConfig) -> tuple[float, float, float]:
    """Return (brightness, sharpness, quality = mean of the two)."""
    gray = _to_gray(img)
    luma = float(gray.mean())
    brightness = _brightness(luma, cfg.confidence.luma_lo, cfg.confidence.luma_hi)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness = _clamp01(variance / cfg.confidence.sharp_ref)
    quality = (brightness + sharpness) / 2
    return brightness, sharpness, quality


class HealthMonitor:
    """Tracks per-source health state across consecutive frames."""

    def __init__(self, cfg: ScoringConfig) -> None:
        self._cfg = cfg
        self._prev_gray: np.ndarray | None = None
        self._fps_low_active = False
        self._black_active = False
        self._blur_active = False
        self._scene_change_active = False
        self._frozen_since: float | None = None
        self._frozen_active = False

    @property
    def active_codes(self) -> set[str]:
        """Health conditions active right now (feed the `poor_image` unknown)."""
        active = {
            "fps_low": self._fps_low_active,
            "scene_change": self._scene_change_active,
            "black_frame": self._black_active,
            "blur": self._blur_active,
            "frozen_frame": self._frozen_active,
        }
        return {code for code, on in active.items() if on}

    def update(self, frame: Frame, fps: float) -> list[HealthEvent]:
        cfg = self._cfg.health
        events: list[HealthEvent] = []
        gray = _to_gray(frame.image)
        luma = float(gray.mean())

        diff: float | None = None
        if self._prev_gray is not None:
            diff = float(
                np.abs(gray.astype(np.float64) - self._prev_gray.astype(np.float64)).mean()
            )

        # fps_low
        if fps < self._cfg.runtime.fps_floor:
            if not self._fps_low_active:
                events.append(("fps_low", float(fps), f"fps {fps:.1f} below floor"))
                self._fps_low_active = True
        else:
            self._fps_low_active = False

        # black_frame
        if luma < cfg.black_luma:
            if not self._black_active:
                events.append(("black_frame", luma, f"mean luma {luma:.1f}"))
                self._black_active = True
        else:
            self._black_active = False

        # blur
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if variance < cfg.blur_var:
            if not self._blur_active:
                events.append(("blur", variance, f"laplacian variance {variance:.1f}"))
                self._blur_active = True
        else:
            self._blur_active = False

        # frozen_frame (sustained low diff for >= frozen_s of Frame.ts)
        if diff is not None and diff < cfg.frozen_diff:
            if self._frozen_since is None:
                self._frozen_since = frame.ts
            elapsed = frame.ts - self._frozen_since
            if not self._frozen_active and elapsed >= cfg.frozen_s:
                events.append(("frozen_frame", elapsed, f"frozen for {elapsed:.1f}s"))
                self._frozen_active = True
        else:
            self._frozen_since = None
            self._frozen_active = False

        # scene_change (instantaneous; re-armed once the diff drops back down)
        if diff is not None and diff > cfg.scene_change_diff:
            if not self._scene_change_active:
                events.append(("scene_change", diff, f"mean frame diff {diff:.1f}"))
                self._scene_change_active = True
        else:
            self._scene_change_active = False

        self._prev_gray = gray
        return events
