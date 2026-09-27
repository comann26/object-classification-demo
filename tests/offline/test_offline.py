"""Layer 3: the real YOLO-World detector runs fully offline (docs/design.md §5).

Connections are limited to 127.0.0.1 by pytest-socket (`allow_hosts` marker —
equivalent to `--disable-socket --allow-hosts=127.0.0.1` for this test), DNS
lookups for anything but localhost fail, and any `pip` subprocess fails. The
test also checks that nothing is written to the user's home cache dirs or to
`models/`. Skipped when the pinned model files are absent (run setup first).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from demo import models
from demo.contracts import Frame

ROOT = Path(__file__).resolve().parents[2]
_HOME = Path.home()
_WATCHED = [
    _HOME,
    _HOME / ".cache",
    _HOME / ".cache" / "clip",
    _HOME / ".cache" / "torch",
    _HOME / ".config" / "Ultralytics",
    _HOME / "AppData" / "Roaming" / "Ultralytics",
    _HOME / "Library" / "Application Support" / "Ultralytics",
    ROOT / "models",
    Path.cwd(),  # Ultralytics' fallback config dir and its default weights_dir live here
]
_NAMES_ONLY = {_HOME, Path.cwd()}

pytestmark = [
    pytest.mark.offline,
    pytest.mark.allow_hosts(["127.0.0.1"]),
    pytest.mark.skipif(
        not all((ROOT / "models" / f).is_file() for f in (models.SMALL, models.CLIP)),
        reason="pinned model files absent — run setup",
    ),
]


def _snapshot() -> dict:
    """Shallow: each watched dir's children with their mtimes (None if absent).

    For home and cwd only the names: their own files change for unrelated reasons.
    """
    snap = {}
    for d in _WATCHED:
        try:
            if d in _NAMES_ONLY:
                snap[d] = {p.name for p in d.iterdir()}
            else:
                snap[d] = {p.name: p.stat().st_mtime_ns for p in d.iterdir()}
        except OSError:
            snap[d] = None
    return snap


def _no_pip(real):
    def guarded(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if "pip" in (cmd if isinstance(cmd, str) else " ".join(map(str, cmd))):
            raise AssertionError(f"runtime pip install attempted: {cmd}")
        return real(*args, **kwargs)

    return guarded


@pytest.fixture
def offline_env(tmp_path, monkeypatch):
    """Env pinned into tmp_path, DNS/pip blocked; fails if home/cwd/models/ gained files."""
    for key, value in {
        "YOLO_CONFIG_DIR": tmp_path / "yolo",
        "TORCH_HOME": tmp_path / "torch",
        "XDG_CACHE_HOME": tmp_path / "cache",
        "YOLO_OFFLINE": "1",
        "YOLO_AUTOINSTALL": "False",
    }.items():
        monkeypatch.setenv(key, str(value))
        if isinstance(value, Path):
            value.mkdir()  # as demo.__main__._set_env does

    import socket

    real_getaddrinfo = socket.getaddrinfo

    def local_dns_only(host, *a, **k):
        if host not in ("127.0.0.1", "localhost", None):
            raise AssertionError(f"DNS lookup attempted: {host}")
        return real_getaddrinfo(host, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", local_dns_only)
    monkeypatch.setattr(subprocess, "run", _no_pip(subprocess.run))
    monkeypatch.setattr(subprocess, "check_output", _no_pip(subprocess.check_output))
    monkeypatch.setattr(subprocess, "Popen", _no_pip(subprocess.Popen))
    monkeypatch.setattr(os, "system", _no_pip(os.system))

    before = _snapshot()
    time.sleep(0.01)  # coarse mtime clocks
    yield
    assert _snapshot() == before


def _detect_30(det) -> None:
    rng = np.random.default_rng(0)
    for i in range(30):
        image = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
        for d in det.detect(Frame(index=i, ts=i / 10, image=image), 640):
            assert d.class_name in ("person", "knife")
            assert all(0.0 <= v <= 1.0 for v in d.bbox)


def test_real_detector_makes_no_network_calls(offline_env):
    # First test in the file: ultralytics must see the pinned env at import.
    assert "ultralytics" not in sys.modules, "ultralytics imported before its env was pinned"
    import ultralytics  # noqa: F401

    from demo.detector import YoloWorldDetector

    det = YoloWorldDetector(ROOT / "models" / models.SMALL, "cpu")
    det.set_classes(["person", "knife"])
    assert det.model_name == "small"
    assert det.model_sha256 == models.manifest(ROOT)[models.SMALL]["sha256"]
    _detect_30(det)


@pytest.mark.skipif(not (ROOT / "models" / models.LARGE).is_file(), reason="large model absent")
def test_builder_large_then_stepdown_swap_to_small(offline_env):
    import demo.__main__ as m
    from demo.config import ScoringConfig

    det = m._default_detector_builder(
        ScoringConfig.model_validate({"runtime": {"model": "large"}}), "cpu"
    )
    assert det.model_name == "large" and det.device == "cpu"
    det.set_classes(["person", "knife"])
    det.swap_model("small")  # what Session does on the large->small step-down
    assert det.model_name == "small"
    assert det.model_sha256 == models.manifest(ROOT)[models.SMALL]["sha256"]
    _detect_30(det)  # classes survived the swap
