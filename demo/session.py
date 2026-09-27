"""Session engine: source → detector → tracker → linker → scorer → events.

One `Session` per Go click. `start()` runs the frame loop in a daemon thread;
`run_to_end()` runs the same loop in the calling thread (tests). Every event
is appended to the hash-chained log (`logs_dir/<id>.jsonl`) and published to
the fan-out. See docs/design.md §2 (payloads), §3 (Emit) and §4 (Engine crash).

ByteTrack's frame_rate: a source with a nominal `fps` (SyntheticSource,
VideoFile) uses it directly; otherwise (Webcam) the frames of the first
second of `Frame.ts` are counted, and frames before the Tracker exists are
shown in the preview but not tracked.
"""

from __future__ import annotations

import copy
import logging
import math
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from demo.config import ScoringConfig, config_sha256
from demo.contracts import (
    Band,
    Frame,
    Provenance,
    Raw,
    SessionEnded,
    SessionRequest,
    SessionStarted,
    SourceHealth,
    Threat,
    Track,
    TrackEnded,
    TrackUpdated,
)
from demo.detector import Detector, filter_min, threat_nms
from demo.events import EventLog, Fanout
from demo.health import HealthMonitor, image_quality
from demo.linker import Linker
from demo.motion import (
    CameraModeDetector,
    approach,
    heading_deg,
    speed_bh_s,
    truncated,
)
from demo.scorer import BandTracker, Inputs, score
from demo.session_parts import (
    Annotator,
    Dwell,
    in_polygon,
    link_out,
    track_name,
    track_out,
    unknowns_for,
)
from demo.source import Source
from demo.tracker import PERSON, Tracker, object_eligible, person_eligible

log = logging.getLogger(__name__)

SCORER_ID = "rules-v1"
DEFAULT_INPUT_SIZE = 640
_EPS = 1e-9
_JOIN_TIMEOUT_S = 5.0
_BAND_ORDER: tuple[Band, ...] = ("low", "medium", "high", "critical")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class _TrackState:
    dwell: Dwell = field(default_factory=Dwell)
    prev_in_zone: bool = False
    lik: deque = field(default_factory=deque)  # (ts, likelihood) over the last 1 s
    emitted: bool = False
    last_emit: float = -math.inf
    band: Band | None = None
    peak_score: int = 0
    peak_band: Band = "low"
    ended_at: float | None = None


class Session:
    def __init__(
        self,
        req: SessionRequest,
        zone: list[tuple[float, float]] | None,
        source: Source,
        detector: Detector,
        cfg: ScoringConfig,
        logs_dir: Path,
        fanout: Fanout,
        app_version: str,
    ) -> None:
        self.id = str(uuid.uuid4())
        self.req = req
        self.zone = zone
        self.source = source
        self.detector = detector
        self.cfg = cfg
        self.fanout = fanout
        self.app_version = app_version
        self.threat_objects = list(req.threat_objects)
        self.input_size = DEFAULT_INPUT_SIZE
        self.device = getattr(detector, "device", "cpu")
        self.log_path = Path(logs_dir) / f"{self.id}.jsonl"
        self._log = EventLog(self.log_path)
        self._prov = {
            "scorer_id": SCORER_ID,
            "config_sha256": config_sha256(cfg),
            "model_sha256": detector.model_sha256,
        }

        self._lock = threading.Lock()  # guards the log, stop flags and the preview
        self._halt = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = self._stopped = self._closed = False

        self._health = HealthMonitor(cfg)
        self._camera = CameraModeDetector(cfg)
        self._linker = Linker(cfg)
        self._bands = BandTracker(cfg.bands.hysteresis)
        self._tracker: Tracker | None = None
        self._states: dict[int, _TrackState] = {}
        self._first_ts: float | None = None
        self._window: deque[float] = deque()  # Frame.ts of the last 1 s
        self._fps = 0.0

        self._annotator = Annotator()
        self._preview: np.ndarray | None = None
        self._jpeg: bytes | None = None

    @property
    def source_id(self) -> str:
        return self.source.id

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        self._begin()
        self._thread = threading.Thread(target=self._loop, name=f"session-{self.id}", daemon=True)
        self._thread.start()

    def run_to_end(self) -> None:
        """Run the loop in this thread until the source ends (tests)."""
        self._begin()
        self._loop()

    def stop(self, reason: str, detail: str | None = None) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
        self._halt.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(_JOIN_TIMEOUT_S)
        try:
            self.source.close()
        except Exception:
            log.exception("session %s: closing the source failed", self.id)
        self._emit(SessionEnded, final=True, reason=reason, detail=detail)

    def _begin(self) -> None:
        try:
            self._emit(
                SessionStarted,
                threat_objects=self.threat_objects,
                zone=self.zone,
                source=self.req.source,
                camera_name=self.source.name,
                device=self.device,
                model=self.detector.model_name,
                model_sha256=self.detector.model_sha256,
                input_size=self.input_size,
                save_stills=self.req.save_stills,
                config=self.cfg.model_dump(mode="json"),
                app_version=self.app_version,
            )
            self.detector.set_classes([PERSON, *self.threat_objects])
            self.source.open()
            self._started = True
        except Exception:
            log.exception("session %s failed to start", self.id)
            self.stop("error")
            raise

    def _loop(self) -> None:
        try:
            while not self._halt.is_set():
                frame = self.source.read()
                if frame is None:
                    self.stop("camera_lost" if self.source.realtime else "stopped")
                    return
                self._step(frame)
        except Exception:
            if self._halt.is_set():
                return  # the source was closed under a blocking read by stop()
            log.exception("session %s crashed", self.id)
            self.stop("error")

    # -- outputs ---------------------------------------------------------

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            if self._jpeg is None and self._preview is not None:
                ok, buf = cv2.imencode(".jpg", self._preview)
                self._jpeg = buf.tobytes() if ok else None
            return self._jpeg

    def health(self) -> dict:
        return {
            "status": "running" if self._started and not self._stopped else "stopped",
            "session_id": self.id,
            "fps": round(self._fps, 1),
            "camera": self.source.name,
            "model": self.detector.model_name,
            "input_size": self.input_size,
            "device": self.device,
        }

    def _emit(self, cls, final: bool = False, **payload) -> None:
        event = cls(
            event_id=str(uuid.uuid4()),
            session_id=self.id,
            source_id=self.source_id,
            ts=_now_iso(),
            provenance=Provenance(**self._prov, input_size=self.input_size, prev_hash="", hash=""),
            **payload,
        ).model_dump(mode="json", by_alias=True)
        with self._lock:
            if self._closed:
                return
            self._log.append(event)
            self.fanout.publish(event)
            if final:
                self._log.close()
                self._closed = True

    # -- one frame -------------------------------------------------------

    def _step(self, frame: Frame) -> None:
        ts = frame.ts
        cfg = self.cfg
        if self._first_ts is None:
            self._first_ts = ts
        self._window.append(ts)
        while self._window[0] <= ts - 1.0 + _EPS:
            self._window.popleft()
        measured = len(self._window) if ts - self._first_ts >= 1.0 - _EPS else None
        if measured is not None:
            self._fps = float(measured)

        for code, value, detail in self._health.update(
            frame, measured if measured is not None else math.inf
        ):
            self._emit(SourceHealth, code=code, value=value, detail=detail)

        if self._tracker is None:
            rate = getattr(self.source, "fps", None) or measured
            if not rate:
                self._annotate(frame, [], {})
                return
            self._tracker = Tracker(cfg, frame_rate=max(1, round(rate)))

        dets = self.detector.detect(frame, self.input_size)
        dets = filter_min(dets, cfg.detect.person_min, cfg.detect.object_min)
        dets = threat_nms(dets, set(self.threat_objects), cfg.detect.threat_nms_iou)
        people, objects = self._tracker.update(frame, dets)
        tracks = people + objects
        mode = self._camera.update(frame, [t.bbox for t in tracks if t.visible])
        links = self._linker.update(ts, people, objects)
        link_changed = {i for _, lk in self._linker.events() for i in (lk.person_id, lk.object_id)}
        quality = image_quality(frame.image, cfg)[2]
        poor = sorted(self._health.image_codes)
        aspect = frame.width / frame.height

        labels: dict[int, str] = {}
        for t in tracks:
            st = self._state(t)
            in_zone = self.zone is not None and t.visible and in_polygon(self.zone, t.bbox)
            dwell = st.dwell.update(in_zone, ts, cfg.zone.dwell_gap_s)
            if t.visible:
                st.lik.append((ts, t.likelihood))
            while st.lik and st.lik[0][0] <= ts - 1.0 + _EPS:
                st.lik.popleft()
            is_person = t.class_name == PERSON
            if not (person_eligible(t, cfg) if is_person else object_eligible(t, cfg)):
                continue
            left_zone, st.prev_in_zone = st.prev_in_zone and not in_zone, in_zone
            mine = [lk for lk in links if lk.person_id == t.track_id] if is_person else []
            held = not is_person and any(lk.object_id == t.track_id for lk in links)

            trunc = is_person and truncated(t.bbox, cfg.motion.truncation_margin)
            motion = is_person and mode == "fixed" and not trunc
            hist = self._tracker.history(t.track_id)
            heading = heading_deg(hist, cfg.motion.smoothing_s, aspect) if motion else None
            speed = speed_bh_s(hist, cfg.motion.smoothing_s, aspect) if motion else None
            growth = approach(hist, cfg.motion.approach_window_s) if motion else None

            det_conf = sum(v for _, v in st.lik) / len(st.lik) if st.lik else t.likelihood

            unknowns = unknowns_for(t, mine, poor, mode == "moving", trunc)

            a = score(
                Inputs(
                    track=t,
                    links=mine,
                    motion_enabled=motion,
                    heading=heading,
                    speed=speed,
                    approach=growth,
                    in_zone=in_zone and not held,  # a held object's own track scores 0
                    left_zone=left_zone and not held,
                    dwell_s=dwell,
                    unattended_s=None if held else self._linker.unattended_s(t.track_id, ts),
                    detector_conf=round(det_conf, 3),
                    track_stability=round(t.hit_ratio_2s, 3),
                    image_quality=round(quality, 3),
                    unknowns=unknowns,
                ),
                cfg,
            )
            band = self._bands.update(t.track_id, a.score)
            st.peak_score = max(st.peak_score, a.score)
            st.peak_band = max(st.peak_band, band, key=_BAND_ORDER.index)
            emit = (
                not st.emitted
                or band != st.band
                or t.track_id in link_changed
                or (band != "low" and ts - st.last_emit >= cfg.emit.heartbeat_s - _EPS)
            )
            st.band = band
            labels[t.track_id] = f"{track_name(t)} · {band} {a.score}"
            if not emit:
                continue
            st.emitted, st.last_emit = True, ts
            self._emit(
                TrackUpdated,
                track=track_out(t, heading, speed, mode),
                links=[link_out(lk) for lk in mine],
                summary=a.summary,
                threat=Threat(score=a.score, band=band, evidence=a.evidence),
                confidence=a.confidence,
                unknowns=a.unknowns,
                raw=Raw(
                    in_zone=in_zone,
                    dwell_s=round(dwell, 3),
                    approach=round(growth or 0.0, 3),
                    truncated=trunc,
                ),
            )

        for t in self._tracker.ended():
            st = self._states.get(t.track_id)
            if st is None:
                continue
            st.ended_at = ts
            self._bands.forget(t.track_id)
            if st.emitted:
                self._emit(
                    TrackEnded,
                    track_id=t.track_id,
                    class_name=t.class_name,
                    duration_s=round(t.ts - t.first_ts, 3),
                    peak_score=st.peak_score,
                    peak_band=st.peak_band,
                )
        # Ended tracks' dwell is kept for restart.window_s so a restart can take it over.
        for tid in [
            i
            for i, s in self._states.items()
            if s.ended_at is not None and ts - s.ended_at > cfg.restart.window_s + _EPS
        ]:
            del self._states[tid]

        self._annotate(frame, tracks, labels)

    def _state(self, t: Track) -> _TrackState:
        st = self._states.get(t.track_id)
        if st is None:
            st = self._states[t.track_id] = _TrackState()
            old = self._states.get(t.restarted_from) if t.restarted_from is not None else None
            if old is not None:  # dwell carries across track_restarted
                st.dwell, st.prev_in_zone = copy.copy(old.dwell), old.prev_in_zone
        return st

    def _annotate(self, frame: Frame, tracks: list[Track], labels: dict[int, str]) -> None:
        img = self._annotator.draw(frame, tracks, labels)
        with self._lock:
            self._preview, self._jpeg = img, None
