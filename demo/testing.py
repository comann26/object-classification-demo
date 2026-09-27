"""Test helpers: a Session wired to a SyntheticSource and a FakeDetector."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from demo.config import ScoringConfig
from demo.contracts import Detection, Frame, SessionRequest
from demo.detector import FakeDetector
from demo.events import Fanout
from demo.session import Session
from demo.source import SyntheticSource

_BASE = np.random.default_rng(0).integers(40, 216, (120, 160, 3), dtype=np.uint8)


def quiet_frame(i: int) -> np.ndarray:
    """A textured mid-grey frame that trips no health check.

    Sharp (no `blur`), bright enough (no `black_frame`), and alternates by a
    few grey levels so it is never `frozen_frame` nor a `scene_change`.
    """
    return _BASE + np.uint8(4 * (i % 2))


def quiet_frames(n: int) -> list[np.ndarray]:
    return [quiet_frame(i) for i in range(n)]


def make_session(
    tmp_path: Path,
    frames_or_script: list[np.ndarray] | Callable[[int], np.ndarray],
    fps: float = 10,
    detector_script: Callable[[Frame], list[Detection]] = lambda frame: [],
    zone: list[tuple[float, float]] | None = None,
    threat_objects: list[str] | None = None,
) -> Session:
    """A not-yet-started Session; call `run_to_end()` (sync) or `start()`."""
    source = SyntheticSource(frames_or_script, fps=fps)
    req = SessionRequest(threat_objects=threat_objects or ["knife"], source=source.id)
    return Session(
        req,
        zone,
        source,
        FakeDetector(detector_script),
        ScoringConfig(),
        Path(tmp_path) / "logs",
        Fanout(),
        app_version="test",
    )
