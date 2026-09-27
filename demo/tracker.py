"""Two ByteTrack instances (people, threat objects) wrapped in our own track registry.

ByteTrack's IDs are per-instance, so each Tracker hands out its own monotonically
increasing `track_id`s. All durations are in seconds of Frame.ts.
See docs/design.md §3 Track.
"""

from __future__ import annotations

import math
import warnings
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import supervision as sv

from demo.config import ScoringConfig
from demo.contracts import BBox, Detection, Frame, Track

PERSON = "person"
_EPS = 1e-9


def _bottom_centre(b: BBox) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2, b[3])


@dataclass
class _Rec:
    track_id: int
    class_name: str
    bbox: BBox
    likelihood: float
    first_ts: float
    last_seen: float
    restarted_from: int | None
    hist: deque
    frames: deque  # (ts, matched) for every frame since first_ts
    detections: int = 0
    visible: bool = True
    ended_ts: float = field(default=-math.inf)


def _new_bytetrack(activation: float, cfg: ScoringConfig, frame_rate: int) -> sv.ByteTrack:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)  # sv.ByteTrack deprecated in 0.28
        bt = sv.ByteTrack(
            track_activation_threshold=activation,
            lost_track_buffer=cfg.tracker.lost_track_buffer,
            minimum_matching_threshold=cfg.tracker.minimum_matching_threshold,
            frame_rate=frame_rate,
            minimum_consecutive_frames=1,
        )
    return bt


class Tracker:
    def __init__(self, cfg: ScoringConfig, frame_rate: int) -> None:
        self._cfg = cfg
        self._maxlen = 10 * frame_rate
        self._activation = {
            "person": cfg.tracker.person_activation,
            "object": cfg.tracker.object_activation,
        }
        self._bt = {k: _new_bytetrack(a, cfg, frame_rate) for k, a in self._activation.items()}
        self._recs: dict[tuple[str, int], _Rec] = {}
        self._by_id: dict[int, _Rec] = {}
        self._gone: list[_Rec] = []  # ended recently, still restart candidates
        self._ended: list[Track] = []
        self._next_id = 1

    def update(self, frame: Frame, dets: list[Detection]) -> tuple[list[Track], list[Track]]:
        ts = frame.ts
        out: dict[str, list[Track]] = {}
        for kind, bt in self._bt.items():
            mine = [d for d in dets if (d.class_name == PERSON) == (kind == "person")]
            matched = self._run(bt, mine, frame, self._activation[kind])
            alive = set(matched)
            alive |= {t.external_track_id for t in bt.tracked_tracks if t.is_activated}
            alive |= {t.external_track_id for t in bt.lost_tracks}

            for key in [k for k in self._recs if k[0] == kind and k[1] not in alive]:
                rec = self._recs.pop(key)
                rec.ended_ts = ts
                self._gone.append(rec)
                self._by_id.pop(rec.track_id)
                self._ended.append(self._track(rec, rec.last_seen))

            for key, rec in self._recs.items():
                if key[0] == kind:
                    rec.visible = False
            for ext_id, det in matched.items():
                rec = self._recs.get((kind, ext_id))
                if rec is None:
                    rec = self._start(kind, ext_id, det, ts)
                rec.class_name, rec.bbox, rec.likelihood = det.class_name, det.bbox, det.likelihood
                rec.last_seen, rec.visible = ts, True
                rec.detections += 1
                rec.hist.append((ts, det.bbox))

            tracks = []
            for key, rec in self._recs.items():
                if key[0] == kind:
                    rec.frames.append((ts, rec.visible))
                    tracks.append(self._track(rec, ts))
            out[kind] = tracks
        self._gone = [
            r for r in self._gone if ts - r.last_seen <= self._cfg.restart.window_s + _EPS
        ]
        return out["person"], out["object"]

    def ended(self) -> list[Track]:
        ended, self._ended = self._ended, []
        return ended

    def history(self, track_id: int) -> Sequence[tuple[float, BBox]]:
        rec = self._by_id.get(track_id)
        return rec.hist if rec is not None else ()

    # ------------------------------------------------------------------

    def _run(
        self, bt: sv.ByteTrack, dets: list[Detection], frame: Frame, activation: float
    ) -> dict[int, Detection]:
        """Feed ByteTrack pixel boxes; return {ByteTrack external id: matched detection}.

        ByteTrack's raw scores would break our activation thresholds twice over:
        it only *starts* a track at `activation + 0.1`, and its first association
        costs `1 - IoU * score`, so with minimum_matching_threshold 0.8 a detection
        below 0.2 can never be matched even at IoU 1. A 0.18 knife (activation
        0.15) would never become a track. So every detection at or above
        `activation` is fed as 1.0; lower ones keep their score for ByteTrack's
        low-score second association. Our Track still reports the real likelihood.
        """
        scale = np.array([frame.width, frame.height, frame.width, frame.height], np.float32)
        conf = np.array([d.likelihood for d in dets], np.float32)
        svd = sv.Detections(
            xyxy=np.array([d.bbox for d in dets], np.float32).reshape(-1, 4) * scale,
            confidence=np.where(conf >= activation, 1.0, conf).astype(np.float32),
            class_id=np.arange(len(dets)),  # index back into `dets`
        )
        res = bt.update_with_detections(svd)
        return {int(tid): dets[int(i)] for tid, i in zip(res.tracker_id, res.class_id)}

    def _start(self, kind: str, ext_id: int, det: Detection, ts: float) -> _Rec:
        rec = _Rec(
            track_id=self._next_id,
            class_name=det.class_name,
            bbox=det.bbox,
            likelihood=det.likelihood,
            first_ts=ts,
            last_seen=ts,
            restarted_from=self._restart_of(det, ts),
            hist=deque(maxlen=self._maxlen),
            frames=deque(maxlen=self._maxlen),
        )
        self._next_id += 1
        self._recs[(kind, ext_id)] = rec
        self._by_id[rec.track_id] = rec
        return rec

    def _restart_of(self, det: Detection, ts: float) -> int | None:
        """Nearest same-class track lost within restart.window_s and restart.max_distance."""
        rc = self._cfg.restart
        claimed = {r.restarted_from for r in self._by_id.values()}
        bx, by = _bottom_centre(det.bbox)
        best: tuple[float, int] | None = None
        for rec in [*self._by_id.values(), *self._gone]:
            if (
                rec.visible
                and rec.ended_ts == -math.inf
                or rec.class_name != det.class_name
                or rec.track_id in claimed
                or ts - rec.last_seen > rc.window_s + _EPS
            ):
                continue
            ox, oy = _bottom_centre(rec.bbox)
            dist = math.hypot(bx - ox, by - oy)
            if dist <= rc.max_distance + _EPS and (best is None or dist < best[0]):
                best = (dist, rec.track_id)
        return best[1] if best else None

    def _track(self, rec: _Rec, ts: float) -> Track:
        return Track(
            track_id=rec.track_id,
            class_name=rec.class_name,
            bbox=rec.bbox,
            likelihood=rec.likelihood,
            first_ts=rec.first_ts,
            ts=ts,
            detections=rec.detections,
            hit_ratio_1s=_hit_ratio(rec.frames, ts, 1.0),
            hit_ratio_2s=_hit_ratio(rec.frames, ts, 2.0),
            visible=rec.visible,
            restarted_from=rec.restarted_from,
        )


def _hit_ratio(frames: deque, now: float, window_s: float) -> float:
    win = [hit for t, hit in frames if t > now - window_s + _EPS]
    return sum(win) / len(win) if win else 0.0


def person_eligible(t: Track, cfg: ScoringConfig) -> bool:
    e = cfg.eligibility
    return (
        t.ts - t.first_ts >= e.person_min_age_s - _EPS and t.hit_ratio_1s >= e.person_min_hit_ratio
    )


def object_eligible(t: Track, cfg: ScoringConfig) -> bool:
    return t.detections >= cfg.eligibility.object_min_detections
