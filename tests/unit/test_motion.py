import cv2
import numpy as np
import pytest

from demo.config import MotionConfig, ScoringConfig
from demo.contracts import Frame
from demo.motion import (
    CameraModeDetector,
    approach,
    direction_label,
    heading_deg,
    speed_bh_s,
    truncated,
)


def _hist(fn, secs=1.0, fps=10):
    return [(i / fps, fn(i / fps)) for i in range(int(secs * fps) + 1)]


def test_heading_down_left_is_225():
    hist = _hist(lambda t: (0.5 - 0.1 * t, 0.2 + 0.1 * t, 0.6 - 0.1 * t, 0.6 + 0.1 * t))
    assert heading_deg(hist, 1.0) == pytest.approx(225.0)
    assert direction_label(heading_deg(hist, 1.0)) == "down-left"


def test_heading_up_is_0():
    hist = _hist(lambda t: (0.4, 0.4 - 0.1 * t, 0.5, 0.8 - 0.1 * t))
    assert heading_deg(hist, 1.0) == pytest.approx(0.0, abs=1e-6)


def test_heading_pixel_diagonal_on_16_9_is_135():
    # 1920x1080: 10 px right + 10 px down per 0.1 s.
    hist = _hist(lambda t: (0.4 + t / 192, 0.3 + t / 108, 0.5 + t / 192, 0.7 + t / 108))
    assert heading_deg(hist, 1.0, aspect=16 / 9) == pytest.approx(135.0)


def test_speed_sideways_on_16_9():
    # 1920x1080: a 400 px-tall box moving 400 px/s horizontally = 1 body height/s.
    h = 400 / 1080
    hist = _hist(lambda t: (0.1 + t * 400 / 1920, 0.2, 0.2 + t * 400 / 1920, 0.2 + h))
    assert speed_bh_s(hist, 1.0, aspect=16 / 9) == pytest.approx(1.0)


def test_motion_none_for_short_history():
    hist = _hist(lambda t: (0.4, 0.4, 0.5, 0.8), secs=0.3)
    assert heading_deg(hist, 1.0) is None
    assert speed_bh_s(hist, 1.0) is None
    assert approach(hist, 2.0) is None


def test_direction_label_boundaries():
    assert direction_label(0.0) == "up"
    assert direction_label(22.4) == "up"
    assert direction_label(22.5) == "up-right"
    assert direction_label(337.4) == "up-left"
    assert direction_label(337.5) == "up"
    assert direction_label(359.9) == "up"
    assert direction_label(90.0) == "right"
    assert direction_label(180.0) == "down"
    assert direction_label(225.0) == "down-left"
    assert direction_label(270.0) == "left"
    assert direction_label(315.0) == "up-left"


def test_speed_body_heights():
    hist = _hist(lambda t: (0.1 + 0.5 * t, 0.2, 0.2 + 0.5 * t, 0.7))
    assert speed_bh_s(hist, 1.0) == pytest.approx(1.0)


def test_raised_arm_no_approach():
    # Height grows 30% over 2 s (arm raised overhead); width constant.
    hist = _hist(lambda t: (0.4, 0.4 - 0.12 * t / 2, 0.5, 0.8), secs=2.0)
    a = approach(hist, 2.0)
    assert a is not None and a < 0.05


def test_approach_width_growth():
    hist = _hist(lambda t: (0.4, 0.4, 0.5 + 0.1 * 0.08 * t / 2, 0.8), secs=2.0)
    assert approach(hist, 2.0) == pytest.approx(0.08)


def test_truncated_top_and_bottom():
    assert truncated((0.2, 0.005, 0.4, 0.5), 0.01)
    assert truncated((0.2, 0.5, 0.4, 0.995), 0.01)
    assert not truncated((0.2, 0.3, 0.4, 0.7), 0.01)


def _texture() -> np.ndarray:
    rng = np.random.default_rng(0)
    small = rng.integers(0, 256, (60, 80, 3), dtype=np.uint8)
    return cv2.resize(small, (640, 480), interpolation=cv2.INTER_LINEAR)


def test_camera_mode_switches_on_global_shift():
    cfg = ScoringConfig(motion=MotionConfig(camera_moving_s=1.0))
    img = _texture()
    shift = int(0.03 * img.shape[1])

    static = CameraModeDetector(cfg)
    modes = [static.update(Frame(i, i / 10, img), []) for i in range(20)]
    assert set(modes) == {"fixed"}

    moving = CameraModeDetector(cfg)
    modes = [
        moving.update(Frame(i, i / 10, np.roll(img, i * shift, axis=1)), []) for i in range(25)
    ]
    assert "moving" not in modes[:10]  # under 1 s of motion
    assert modes[-1] == "moving"

    # Camera stops: back to fixed after camera_moving_s of stillness.
    last = np.roll(img, 24 * shift, axis=1)
    modes = [moving.update(Frame(i, i / 10, last), []) for i in range(25, 45)]
    assert modes[0] == "moving" and modes[-1] == "fixed"
