import numpy as np

import demo.source as source_mod
from demo.source import SyntheticSource


def _frame(v: int = 128) -> np.ndarray:
    return np.full((120, 160, 3), v, np.uint8)


def test_synthetic_ts_is_video_time():
    frames = [_frame() for _ in range(60)]
    src = SyntheticSource(frames, fps=30)
    src.open()
    got = None
    for _ in range(46):
        got = src.read()
    assert got is not None
    assert got.index == 45
    assert got.ts == 1.5


def test_synthetic_not_realtime_and_id():
    src = SyntheticSource([_frame()], fps=30)
    assert src.realtime is False
    assert src.id == "synthetic"


def test_synthetic_ends_with_none():
    src = SyntheticSource([_frame(), _frame()], fps=30)
    src.open()
    assert src.read() is not None
    assert src.read() is not None
    assert src.read() is None
    src.close()


def test_synthetic_accepts_callable():
    src = SyntheticSource(lambda i: _frame(i % 256), fps=30)
    src.open()
    f0 = src.read()
    f1 = src.read()
    assert f0.index == 0
    assert f1.index == 1


def test_webcam_open_is_idempotent(monkeypatch):
    # open_webcam() opens it, then Session._begin() opens it again: a second
    # VideoCapture on the same device often fails on Windows DSHOW (final review #2).
    created = []

    class FakeCapture:
        def __init__(self, *args):
            created.append(args)

        def isOpened(self):
            return True

        def release(self):
            pass

    monkeypatch.setattr(source_mod.cv2, "VideoCapture", FakeCapture)
    cam = source_mod.Webcam(index=0, backend=0, id="cam-0", name="Cam")
    cam.open()
    cam.open()
    assert len(created) == 1
    cam.close()
    cam.open()  # after close, a real reopen
    assert len(created) == 2
