"""Detector protocol, fake detector for tests, and threat-class NMS/filtering.

The real detector (YOLO-World, Task 15) implements the same `Detector`
protocol so `session.py` and tests never care which one is wired in
(`testing.py` injects `FakeDetector`). See docs/design.md §3 Detect.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from demo.contracts import BBox, Detection, Frame


class Detector(Protocol):
    model_name: str
    model_sha256: str

    def set_classes(self, words: list[str]) -> None: ...

    def detect(self, frame: Frame, input_size: int) -> list[Detection]: ...


def _box_iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0.0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else 0.0


# Public alias — kept separate from the `iou` parameter name in threat_nms below.
iou = _box_iou


def threat_nms(dets: list[Detection], threat_words: set[str], iou: float) -> list[Detection]:
    """Class-agnostic greedy NMS among threat-class detections only.

    Detections whose class is not in `threat_words` (persons included) pass
    through untouched. Output order: kept threat detections sorted by
    descending likelihood, then all other detections in their input order.
    """
    threats = [d for d in dets if d.class_name in threat_words]
    passthrough = [d for d in dets if d.class_name not in threat_words]

    threats.sort(key=lambda d: d.likelihood, reverse=True)
    kept: list[Detection] = []
    for d in threats:
        if any(_box_iou(d.bbox, k.bbox) >= iou for k in kept):
            continue
        kept.append(d)

    return kept + passthrough


def filter_min(dets: list[Detection], person_min: float, object_min: float) -> list[Detection]:
    """Drop detections below the minimum likelihood for their kind (inclusive)."""
    return [
        d
        for d in dets
        if d.likelihood >= (person_min if d.class_name == "person" else object_min)
    ]


@dataclass
class FakeDetector:
    """A `Detector` for tests: delegates to a caller-supplied script."""

    script: Callable[[Frame], list[Detection]]
    model_name: str = "fake"
    model_sha256: str = "0" * 64
    classes: list[str] = field(default_factory=list)

    def set_classes(self, words: list[str]) -> None:
        self.classes = list(words)

    def detect(self, frame: Frame, input_size: int) -> list[Detection]:
        return self.script(frame)
