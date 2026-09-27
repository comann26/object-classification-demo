"""Task 14: launch entry point (docs/design.md §4 "Launch, port, second launch",
"Model and offline"; `demo/__main__.py`).

No real server or camera: `uvicorn.Config`/`uvicorn.Server` and `webbrowser.open`
are patched throughout.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys

import pytest

import demo.__main__ as m
from demo.cameras import CameraError, CameraInfo


def _dead_pid() -> int:
    """A PID guaranteed not to be alive: a subprocess that has already exited."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


class FakeServer:
    """Stands in for `uvicorn.Server`: records the config, never actually serves."""

    instances: list[FakeServer] = []

    def __init__(self, config):
        self.config = config
        self.should_exit = False
        self.started = True  # so the "open browser once ready" poll thread exits promptly
        FakeServer.instances.append(self)

    def run(self) -> None:
        pass


@pytest.fixture
def fake_uvicorn(monkeypatch):
    FakeServer.instances = []
    configs = []

    def fake_config(app, **kwargs):
        configs.append(kwargs)
        return kwargs

    monkeypatch.setattr(m.uvicorn, "Config", fake_config)
    monkeypatch.setattr(m.uvicorn, "Server", FakeServer)
    return configs


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(m.webbrowser, "open", lambda url: urls.append(url))
    return urls


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "scoring.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    return tmp_path


def test_pick_port_skips_busy():
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        busy.bind(("127.0.0.1", 8000))
        busy.listen(1)
        port = m.pick_port(8000)
        assert port != 8000
        # the chosen port really is free
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", port))
        probe.close()
    finally:
        busy.close()


def test_second_launch_opens_existing_and_exits(root, opened, fake_uvicorn):
    m.write_lock(root, os.getpid(), 8123, "tok-existing")

    rc = m.main()

    assert rc == 0
    assert opened == ["http://127.0.0.1:8123/?t=tok-existing"]
    assert FakeServer.instances == []  # never started a server


def test_stale_lock_replaced(root, opened, monkeypatch):
    dead_pid = _dead_pid()
    m.write_lock(root, dead_pid, 9999, "tok-stale")

    snapshot = {}

    class SnapshottingServer(FakeServer):
        def run(self) -> None:
            # the lock on disk *while the server is up*, before shutdown cleans it up
            snapshot.update(m.read_lock(root))

    monkeypatch.setattr(m.uvicorn, "Config", lambda app, **kw: kw)
    monkeypatch.setattr(m.uvicorn, "Server", SnapshottingServer)

    rc = m.main()

    assert rc == 0
    assert snapshot["pid"] == os.getpid()
    assert snapshot["token"] != "tok-stale"
    assert snapshot["port"] != 9999
    # clean shutdown (Server.run() returned normally) removes the lock
    assert not (root / "run" / "demo.lock").exists()


def test_env_points_inside_root(root, opened, fake_uvicorn, monkeypatch):
    env_vars = (
        "YOLO_CONFIG_DIR",
        "YOLO_OFFLINE",
        "YOLO_AUTOINSTALL",
        "TORCH_HOME",
        "XDG_CACHE_HOME",
    )
    for key in env_vars:
        monkeypatch.delenv(key, raising=False)

    m.main()

    assert os.environ["YOLO_CONFIG_DIR"] == str(root / ".uv" / "yolo")
    assert os.environ["YOLO_OFFLINE"] == "1"
    assert os.environ["YOLO_AUTOINSTALL"] == "False"
    assert os.environ["TORCH_HOME"] == str(root / ".uv" / "torch")
    assert os.environ["XDG_CACHE_HOME"] == str(root / ".uv" / "cache")


def test_env_does_not_override_existing(root, opened, fake_uvicorn, monkeypatch):
    monkeypatch.setenv("YOLO_OFFLINE", "already-set")

    m.main()

    assert os.environ["YOLO_OFFLINE"] == "already-set"


def test_access_log_disabled(root, opened, fake_uvicorn):
    m.main()

    assert len(fake_uvicorn) == 1
    assert fake_uvicorn[0]["access_log"] is False
    assert fake_uvicorn[0]["log_level"] == "warning"
    assert fake_uvicorn[0]["host"] == "127.0.0.1"


def test_shutdown_sets_should_exit(root, opened, fake_uvicorn, monkeypatch):
    real_create_app = m.create_app
    captured = {}

    def spy_create_app(**kwargs):
        captured.update(kwargs)
        return real_create_app(**kwargs)

    monkeypatch.setattr(m, "create_app", spy_create_app)

    m.main()

    srv = FakeServer.instances[0]
    assert srv.should_exit is False
    captured["shutdown"]()
    assert srv.should_exit is True


def test_factory_opens_camera_before_session(tmp_path, monkeypatch):
    def boom(camera):
        raise CameraError("busy")

    monkeypatch.setattr(m, "open_webcam", boom)
    factory = m.make_session_factory(lambda cfg, device: (_ for _ in ()).throw(AssertionError))

    from demo.config import ScoringConfig
    from demo.contracts import SessionRequest
    from demo.events import Fanout

    camera = CameraInfo(id="cam-0", name="Test Cam", index=0, backend=0)
    req = SessionRequest(threat_objects=["knife"], source="cam-0", save_stills=False)
    logs_dir = tmp_path / "logs"

    with pytest.raises(CameraError):
        factory(req, None, camera, cfg=ScoringConfig(), logs_dir=logs_dir, fanout=Fanout())

    assert not logs_dir.exists() or not list(logs_dir.glob("*.jsonl"))


def test_default_detector_builder_missing_model():
    with pytest.raises(RuntimeError, match="Model not installed"):
        m._default_detector_builder(cfg=None, device="cpu")


def test_lock_is_live_true_for_current_process():
    assert m.lock_is_live({"pid": os.getpid(), "port": 8000, "token": "x"}) is True


def test_lock_is_live_false_for_dead_pid():
    assert m.lock_is_live({"pid": _dead_pid(), "port": 8000, "token": "x"}) is False


def test_lock_is_live_false_for_missing_or_bad_data():
    assert m.lock_is_live({}) is False
    assert m.lock_is_live({"pid": "not-a-number"}) is False


def test_read_lock_missing_returns_none(tmp_path):
    assert m.read_lock(tmp_path) is None


def test_read_lock_corrupt_returns_none(tmp_path):
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "demo.lock").write_text("not json", encoding="utf-8")
    assert m.read_lock(tmp_path) is None


def test_write_lock_round_trip(tmp_path):
    m.write_lock(tmp_path, 123, 8001, "abc")
    data = json.loads((tmp_path / "run" / "demo.lock").read_text(encoding="utf-8"))
    assert data == {"pid": 123, "port": 8001, "token": "abc"}
