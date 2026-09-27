"""Detector protocol, fake detector for tests, and threat-class NMS/filtering.

The real detector (YOLO-World, Task 15) implements the same `Detector`
protocol so `session.py` and tests never care which one is wired in
(`testing.py` injects `FakeDetector`). See docs/design.md §3 Detect.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
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
        d for d in dets if d.likelihood >= (person_min if d.class_name == "person" else object_min)
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


# Ultralytics' own confidence floor. The config mins (person/object) are applied
# afterwards by `filter_min`; a config min below this floor has no effect.
_CONF_FLOOR = 0.05


class YoloWorldDetector:
    """The real `Detector`: YOLO-World with the CLIP text encoder, all from `models/`.

    Ultralytics/torch are imported lazily, here, never at module import. The
    caller pins `YOLO_*`/`TORCH_HOME`/`XDG_CACHE_HOME` before constructing one
    (see `demo.__main__._set_env`). `model_name` is "small"/"large".
    """

    def __init__(self, weights: Path, device: str) -> None:
        from demo.models import CLIP  # noqa: PLC0415

        self.device = device
        self._clip_path = Path(weights).parent / CLIP
        self._clip = None
        self._words: list[str] = []
        self._load(Path(weights))

    def _load(self, weights: Path) -> None:
        from ultralytics import YOLOWorld  # noqa: PLC0415
        from ultralytics.nn.text_model import CLIP  # noqa: PLC0415

        from demo.models import MODEL_FILES, sha256  # noqa: PLC0415

        self.weights = weights
        self.model_name = {v: k for k, v in MODEL_FILES.items()}.get(weights.name, weights.stem)
        self.model_sha256 = sha256(weights)
        self._model = YOLOWorld(str(weights))
        self._model.model.to(self.device)
        if self._clip is None:
            # Ultralytics itself builds CLIP("ViT-B/32") -> clip.load(name, download_root=
            # WEIGHTS_DIR/"clip"), which downloads when absent. Given a file path,
            # clip.load just loads it. Pre-setting clip_model makes set_classes use ours.
            self._clip = CLIP(str(self._clip_path), self.device)
        self._model.model.clip_model = self._clip
        if self._words:
            self.set_classes(self._words)

    def swap_model(self, name: str) -> None:
        """Step-down: load the `small`/`large` weights from the same folder, keeping the classes."""
        from demo.models import MODEL_FILES  # noqa: PLC0415

        if name != self.model_name:
            self._load(self.weights.with_name(MODEL_FILES[name]))

    def set_classes(self, words: list[str]) -> None:
        self._words = list(words)
        self._model.set_classes(list(words))  # ultralytics mutates the list it is given

    def detect(self, frame: Frame, input_size: int) -> list[Detection]:
        r = self._model.predict(
            frame.image, imgsz=input_size, conf=_CONF_FLOOR, device=self.device, verbose=False
        )[0]
        boxes = r.boxes
        xyxyn = boxes.xyxyn.tolist()
        return [
            Detection(self._words[int(c)], float(p), tuple(b))
            for b, c, p in zip(xyxyn, boxes.cls.tolist(), boxes.conf.tolist(), strict=True)
        ]
