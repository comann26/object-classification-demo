import numpy as np

from demo.config import ScoringConfig
from demo.contracts import Frame
from demo.health import HealthMonitor, image_quality


def _flat(v: int) -> np.ndarray:
    return np.full((120, 160, 3), v, np.uint8)


def _half_and_half(a: int, b: int) -> np.ndarray:
    img = np.full((120, 160, 3), a, np.uint8)
    img[:60, :, :] = b
    return img


def _checkerboard() -> np.ndarray:
    yy, xx = np.indices((120, 160))
    pattern = ((xx // 8 + yy // 8) % 2) * 255
    return np.repeat(pattern[:, :, None], 3, axis=2).astype(np.uint8)


def test_brightness_curve():
    cfg = ScoringConfig()
    assert image_quality(_flat(128), cfg)[0] == 1.0
    assert image_quality(_flat(0), cfg)[0] == 0.0
    assert image_quality(_flat(30), cfg)[0] == 0.5
    assert image_quality(_half_and_half(227, 228), cfg)[0] == 0.5


def test_sharpness_clamped():
    cfg = ScoringConfig()
    assert image_quality(_flat(128), cfg)[1] == 0.0
    assert image_quality(_checkerboard(), cfg)[1] == 1.0


def test_quality_is_mean_of_brightness_and_sharpness():
    cfg = ScoringConfig()
    brightness, sharpness, quality = image_quality(_checkerboard(), cfg)
    assert quality == (brightness + sharpness) / 2


def test_black_frame_reported_once():
    cfg = ScoringConfig()
    mon = HealthMonitor(cfg)
    dark = np.zeros((120, 160, 3), np.uint8)

    codes1 = [c for c, _, _ in mon.update(Frame(0, 0.0, dark), fps=30)]
    codes2 = [c for c, _, _ in mon.update(Frame(1, 0.033, dark), fps=30)]

    assert "black_frame" in codes1
    assert "black_frame" not in codes2


def test_black_frame_recovers_and_retriggers():
    cfg = ScoringConfig()
    mon = HealthMonitor(cfg)
    dark = np.zeros((120, 160, 3), np.uint8)
    bright = _flat(128)

    mon.update(Frame(0, 0.0, dark), fps=30)
    codes2 = [c for c, _, _ in mon.update(Frame(1, 0.1, bright), fps=30)]
    codes3 = [c for c, _, _ in mon.update(Frame(2, 0.2, dark), fps=30)]

    assert "black_frame" not in codes2
    assert "black_frame" in codes3


def test_frozen_after_frozen_s():
    cfg = ScoringConfig()
    mon = HealthMonitor(cfg)
    img = _flat(128)
    fps = 30

    found_at = None
    for i in range(70):
        ts = i / fps
        codes = [c for c, _, _ in mon.update(Frame(i, ts, img), fps=fps)]
        if "frozen_frame" in codes:
            found_at = ts
            break

    assert found_at is not None
    assert found_at >= cfg.health.frozen_s


def test_blur_reported_once():
    cfg = ScoringConfig()
    mon = HealthMonitor(cfg)
    blurry = _flat(128)

    codes1 = [c for c, _, _ in mon.update(Frame(0, 0.0, blurry), fps=30)]
    codes2 = [c for c, _, _ in mon.update(Frame(1, 0.033, blurry), fps=30)]

    assert "blur" in codes1
    assert "blur" not in codes2


def test_scene_change():
    cfg = ScoringConfig()
    mon = HealthMonitor(cfg)
    dark = np.zeros((120, 160, 3), np.uint8)
    bright = _flat(255)

    mon.update(Frame(0, 0.0, dark), fps=30)
    codes_change = [c for c, _, _ in mon.update(Frame(1, 0.033, bright), fps=30)]
    codes_same = [c for c, _, _ in mon.update(Frame(2, 0.066, bright), fps=30)]
    codes_change_again = [c for c, _, _ in mon.update(Frame(3, 0.1, dark), fps=30)]

    assert "scene_change" in codes_change
    assert "scene_change" not in codes_same
    assert "scene_change" in codes_change_again


def test_fps_low_below_floor():
    cfg = ScoringConfig()
    mon = HealthMonitor(cfg)
    img = _flat(128)
    floor = cfg.runtime.fps_floor

    codes1 = [c for c, _, _ in mon.update(Frame(0, 0.0, img), fps=floor - 1)]
    codes2 = [c for c, _, _ in mon.update(Frame(1, 0.033, img), fps=floor - 1)]
    codes3 = [c for c, _, _ in mon.update(Frame(2, 0.066, img), fps=floor + 5)]
    codes4 = [c for c, _, _ in mon.update(Frame(3, 0.1, img), fps=floor - 1)]

    assert "fps_low" in codes1
    assert "fps_low" not in codes2
    assert "fps_low" not in codes3
    assert "fps_low" in codes4
