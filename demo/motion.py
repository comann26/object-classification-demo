"""Motion math over a track's (ts, bbox) history, plus camera-mode detection.

All geometry is in normalized coordinates. Heading is on-screen: 0° = toward
the top of the frame, clockwise (right = 90°). See docs/design.md §3 Motion.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

import cv2
import numpy as np

from demo.config import ScoringConfig
from demo.contracts import BBox, Direction, Frame

History = Sequence[tuple[float, BBox]]

_LABELS: tuple[Direction, ...] = (
    "up",
    "up-right",
    "right",
    "down-right",
    "down",
    "down-left",
    "left",
    "up-left",
)


def _window(hist: History, window_s: float) -> History | None:
    """The entries in the last `window_s`, or None if they span under half of it."""
    if not hist:
        return None
    end = hist[-1][0]
    win = [h for h in hist if h[0] >= end - window_s - 1e-9]
    if end - win[0][0] < window_s / 2:
        return None
    return win


def _velocity(win: History) -> tuple[float, float]:
    """Least-squares bottom-centre velocity (normalized units per s)."""
    t = np.array([h[0] for h in win])
    x = np.array([(b[0] + b[2]) / 2 for _, b in win])
    y = np.array([b[3] for _, b in win])
    return float(np.polyfit(t, x, 1)[0]), float(np.polyfit(t, y, 1)[0])


def heading_deg(hist: History, smoothing_s: float) -> float | None:
    win = _window(hist, smoothing_s)
    if win is None:
        return None
    vx, vy = _velocity(win)
    return math.degrees(math.atan2(vx, -vy)) % 360.0


def direction_label(deg: float) -> Direction:
    return _LABELS[int(((deg + 22.5) % 360.0) // 45.0)]


def speed_bh_s(hist: History, smoothing_s: float) -> float | None:
    win = _window(hist, smoothing_s)
    if win is None:
        return None
    mean_h = sum(b[3] - b[1] for _, b in win) / len(win)
    if mean_h <= 0:
        return None
    return math.hypot(*_velocity(win)) / mean_h


def approach(hist: History, window_s: float) -> float | None:
    """Relative box-width growth over the window (width, not height: raised arms)."""
    win = _window(hist, window_s)
    if win is None:
        return None
    w0 = win[0][1][2] - win[0][1][0]
    w1 = win[-1][1][2] - win[-1][1][0]
    return (w1 - w0) / w0 if w0 > 0 else None


def truncated(bbox: BBox, margin: float) -> bool:
    return bbox[1] <= margin or bbox[3] >= 1.0 - margin


class CameraModeDetector:
    """Sparse LK optical flow on the background (outside all boxes).

    `moving` once the median flow / frame width stays above the threshold for
    `camera_moving_s` of Frame.ts; back to `fixed` after the same time below it.
    """

    _WIDTH = 320
    _MIN_FEATURES = 10

    def __init__(self, cfg: ScoringConfig) -> None:
        self._threshold = cfg.motion.camera_flow_threshold
        self._hold_s = cfg.motion.camera_moving_s
        self._mode: Literal["fixed", "moving"] = "fixed"
        self._prev: np.ndarray | None = None
        self._since: float | None = None  # ts the opposite state started

    def update(self, frame: Frame, boxes: list[BBox]) -> Literal["fixed", "moving"]:
        img = frame.image
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        h = max(1, round(gray.shape[0] * self._WIDTH / gray.shape[1]))
        gray = cv2.resize(gray, (self._WIDTH, h), interpolation=cv2.INTER_AREA)
        prev, self._prev = self._prev, gray
        if prev is None or prev.shape != gray.shape:
            return self._mode

        mask = np.full(gray.shape, 255, np.uint8)
        for x1, y1, x2, y2 in boxes:
            mask[
                int(y1 * h) : int(math.ceil(y2 * h)),
                int(x1 * self._WIDTH) : int(math.ceil(x2 * self._WIDTH)),
            ] = 0
        pts = cv2.goodFeaturesToTrack(prev, 200, 0.01, 8, mask=mask)
        if pts is None or len(pts) < self._MIN_FEATURES:
            return self._mode  # too little background texture: keep the last mode
        nxt, status, _ = cv2.calcOpticalFlowPyrLK(prev, gray, pts, None)
        ok = status.ravel() == 1
        if ok.sum() < self._MIN_FEATURES:
            return self._mode

        flow = (
            float(np.median(np.linalg.norm((nxt - pts).reshape(-1, 2)[ok], axis=1))) / self._WIDTH
        )
        if (flow > self._threshold) == (self._mode == "moving"):
            self._since = None
        elif self._since is None:
            self._since = frame.ts
        elif frame.ts - self._since >= self._hold_s - 1e-9:
            self._mode = "fixed" if self._mode == "moving" else "moving"
            self._since = None
        return self._mode
