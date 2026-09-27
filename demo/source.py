"""Frame sources: synthetic frames (tests), recorded clips, and live webcams.

`Frame.ts` is always seconds, never a frame count or wall-clock time (see
docs/design.md §3 Clock). `SyntheticSource` and `VideoFile` derive `ts` from
video time, so pipeline rules run identically on fast and slow machines.
`Webcam` is the only realtime source; its `ts` is the monotonic capture time.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from demo.contracts import Frame


class Source(Protocol):
    realtime: bool
    id: str
    name: str

    def open(self) -> None: ...

    def read(self) -> Frame | None: ...

    def close(self) -> None: ...


class SyntheticSource:
    """Frames from an in-memory list or a generator callable — for tests.

    `realtime` defaults to False (step-down is disabled, as for any
    synthetic/file source); tests that need to exercise the realtime-only
    step-down logic pass `realtime=True` to opt in.
    """

    def __init__(
        self,
        frames: list[np.ndarray] | Callable[[int], np.ndarray],
        fps: float,
        id: str = "synthetic",
        realtime: bool = False,
    ) -> None:
        self._frames = frames
        self._fps = fps
        self.id = id
        self.name = id
        self.realtime = realtime
        self._index = 0

    @property
    def fps(self) -> float:
        """Nominal frame rate (the session uses it for ByteTrack's frame_rate)."""
        return self._fps

    def open(self) -> None:
        self._index = 0

    def read(self) -> Frame | None:
        if callable(self._frames):
            image = self._frames(self._index)
        else:
            if self._index >= len(self._frames):
                return None
            image = self._frames[self._index]
        frame = Frame(index=self._index, ts=self._index / self._fps, image=image)
        self._index += 1
        return frame

    def close(self) -> None:
        pass


class VideoFile:
    """Frames read from a recorded clip, timestamped by video time."""

    realtime = False

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.id = self.name = self.path.stem
        self._cap: cv2.VideoCapture | None = None
        self._fps = 30.0
        self._index = 0

    @property
    def fps(self) -> float:
        """Nominal frame rate (the session uses it for ByteTrack's frame_rate)."""
        return self._fps

    def open(self) -> None:
        self._cap = cv2.VideoCapture(str(self.path))
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._index = 0

    def read(self) -> Frame | None:
        assert self._cap is not None, "open() must be called first"
        ok, image = self._cap.read()
        if not ok:
            return None
        frame = Frame(index=self._index, ts=self._index / self._fps, image=image)
        self._index += 1
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class Webcam:
    """A live camera, opened by OpenCV index and backend."""

    realtime = True

    def __init__(self, index: int, backend: int, id: str, name: str) -> None:
        self.index = index
        self.backend = backend
        self.id = id
        self.name = name
        self._cap: cv2.VideoCapture | None = None
        self._frame_index = 0

    def open(self) -> None:
        # Idempotent: open_webcam() opens it, then Session._begin() calls open() again,
        # and a second capture of the same device often fails on Windows DSHOW.
        if self._cap is not None and self._cap.isOpened():
            return
        self._cap = cv2.VideoCapture(self.index, self.backend)
        self._frame_index = 0

    def read(self) -> Frame | None:
        assert self._cap is not None, "open() must be called first"
        ok, image = self._cap.read()
        if not ok:
            return None
        frame = Frame(index=self._frame_index, ts=time.monotonic(), image=image)
        self._frame_index += 1
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
