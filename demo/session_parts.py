"""Pure helpers for `session.py`: zone dwell, unknowns, wire payloads, preview drawing."""

from __future__ import annotations

import cv2
import numpy as np
import supervision as sv

from demo.contracts import BBox, Frame, Link, LinkOut, Track, TrackOut, Unknown
from demo.motion import direction_label
from demo.tracker import PERSON

_EPS = 1e-9


def in_polygon(zone: list[tuple[float, float]], bbox: BBox) -> bool:
    """Bottom-centre of the box inside (or on the edge of) the zone polygon."""
    pt = ((bbox[0] + bbox[2]) / 2, bbox[3])
    return cv2.pointPolygonTest(np.array(zone, np.float32), pt, False) >= 0


class Dwell:
    """Continuous seconds inside the zone, tolerating gaps up to `gap_s`."""

    def __init__(self) -> None:
        self.start: float | None = None
        self.last_in: float | None = None

    def update(self, inside: bool, ts: float, gap_s: float) -> float:
        gap_ok = self.last_in is not None and ts - self.last_in <= gap_s + _EPS
        if inside:
            if not gap_ok:
                self.start = ts
            self.last_in = ts
        elif not gap_ok:
            self.start = None
        return 0.0 if self.start is None else ts - self.start


def unknowns_for(
    t: Track, links: list[Link], poor: list[str], camera_moving: bool, trunc: bool
) -> list[Unknown]:
    out = [
        Unknown(
            code="object_out_of_view",
            detail=f"{lk.object_class} {lk.object_id} out of view for {lk.out_of_view_s:.1f} s",
        )
        for lk in links
        if lk.out_of_view_s is not None
    ]
    if t.restarted_from is not None:
        out.append(Unknown(code="track_restarted", detail=f"continues track {t.restarted_from}"))
    if poor:
        out.append(Unknown(code="poor_image", detail=", ".join(poor)))
    if camera_moving:
        out.append(Unknown(code="camera_moving", detail="motion rules suspended"))
    if trunc:
        out.append(Unknown(code="truncated", detail="box touches the frame edge"))
    return out


def _r(v: float | None, nd: int = 3) -> float | None:
    return None if v is None else round(v, nd)


def track_out(t: Track, heading: float | None, speed: float | None, mode: str) -> TrackOut:
    return TrackOut(
        track_id=t.track_id,
        class_name=t.class_name,
        bbox=tuple(round(v, 4) for v in t.bbox),
        likelihood=round(t.likelihood, 3),
        heading_deg=_r(heading, 1),
        direction=None if heading is None else direction_label(heading),
        speed_body_heights_per_s=_r(speed),
        camera_mode=mode,
    )


def link_out(lk: Link) -> LinkOut:
    return LinkOut(
        object_track_id=lk.object_id,
        object_class=lk.object_class,
        object_likelihood=round(lk.object_likelihood, 3),
        linked_s=round(lk.linked_s, 3),
        strength=round(lk.strength, 3),
        out_of_view_s=_r(lk.out_of_view_s),
    )


def track_name(t: Track) -> str:
    return f"{'Person' if t.class_name == PERSON else t.class_name.capitalize()} {t.track_id}"


class Annotator:
    """Draws boxes, traces and labels on the preview with `supervision`."""

    def __init__(self) -> None:
        self._box = sv.BoxAnnotator()
        self._label = sv.LabelAnnotator()
        self._trace = sv.TraceAnnotator()

    def draw(self, frame: Frame, tracks: list[Track], labels: dict[int, str]) -> np.ndarray:
        img = frame.image.copy()
        shown = [t for t in tracks if t.visible]
        if not shown:
            return img
        scale = np.array([frame.width, frame.height] * 2, np.float32)
        det = sv.Detections(
            xyxy=np.array([t.bbox for t in shown], np.float32) * scale,
            class_id=np.array([int(t.class_name != PERSON) for t in shown]),
            tracker_id=np.array([t.track_id for t in shown]),
        )
        img = self._trace.annotate(img, det)
        img = self._box.annotate(img, det)
        return self._label.annotate(
            img, det, labels=[labels.get(t.track_id, track_name(t)) for t in shown]
        )
