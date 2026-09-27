"""Launch entry point: `python -m demo` (docs/design.md §4 "Launch, port, second
launch", "Model and offline"; §1 — this is the only place that opens the browser).

Flow: pick a free port, write `run/demo.lock` ({pid, port, token}), start uvicorn
on 127.0.0.1 with the launch token baked into the opened URL. A second launch
while a live lock exists just reopens that URL and exits. `make_session_factory`
wires the production `Session` (opens the webcam first, so a `CameraError`
never leaves a stray session or log — see docs/server.py's `create_app` docstring).

Torch/Ultralytics are never imported at module scope: `_set_env` runs first in
`main()`, and the default `detector_builder` imports `demo.detector.YoloWorldDetector`
lazily, after verifying the pinned model files (`demo.models`).
"""

from __future__ import annotations

import atexit
import json
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import uvicorn

from demo import models
from demo.cameras import list_cameras, open_webcam
from demo.config import ScoringConfig
from demo.server import create_app
from demo.session import Session

ROOT = Path(__file__).resolve().parent.parent
_HOST = "127.0.0.1"


def pick_port(start: int = 8000) -> int:
    """The first free port at or after `start` on `_HOST`."""
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((_HOST, port))
            except OSError:
                port += 1
                continue
            return port


def _lock_path(root: Path) -> Path:
    return Path(root) / "run" / "demo.lock"


def read_lock(root: Path) -> dict | None:
    try:
        return json.loads(_lock_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_lock(root: Path, pid: int, port: int, token: str) -> None:
    path = _lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": pid, "port": port, "token": token}), encoding="utf-8")


def _remove_lock(root: Path) -> None:
    _lock_path(root).unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import psutil  # noqa: PLC0415
    except ImportError:
        pass
    else:
        return psutil.pid_exists(pid)

    if sys.platform == "win32":
        import ctypes  # noqa: PLC0415

        # 0x1000 = PROCESS_QUERY_LIMITED_INFORMATION
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not owned by us
    return True


def lock_is_live(lock: dict) -> bool:
    pid = lock.get("pid")
    return isinstance(pid, int) and not isinstance(pid, bool) and _pid_alive(pid)


def detect_device() -> str:
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _app_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

        return version("object-classification-demo")
    except PackageNotFoundError:
        return "0.0.0"


def _default_detector_builder(cfg: ScoringConfig, device: str) -> Any:
    """YOLO-World for `runtime.model` on `device`, after checking the pinned files.

    ponytail: re-hashes the weights + CLIP (~380 MB) on every Go; cache by
    (size, mtime) if Go latency ever matters.
    """
    from demo.detector import YoloWorldDetector  # noqa: PLC0415

    name = models.MODEL_FILES[models.select_model(cfg.runtime.model, device)]
    # small too: it is always the step-down target (§3), loaded mid-session by swap_model.
    needed = list(dict.fromkeys([name, models.SMALL, models.CLIP]))
    for file, ok in models.verify(ROOT, needed).items():
        if not ok:
            raise models.SetupError(models.DAMAGED_MESSAGE.format(file=file))
    return YoloWorldDetector(models.models_dir(ROOT) / name, device)


def make_session_factory(
    detector_builder: Callable[[ScoringConfig, str], Any],
) -> Callable[..., Session]:
    """A production `session_factory` for `create_app` (see its docstring).

    Opens the webcam *first*: a `CameraError` then propagates before any
    `Session` (and its log file) exists. Only once the camera is open does it
    build the detector and the `Session`; if either of those fails, the
    webcam is closed before the error is re-raised.
    """

    def factory(req, zone, camera, *, cfg: ScoringConfig, logs_dir: Path, fanout) -> Session:
        source = open_webcam(camera)
        try:
            detector = detector_builder(cfg, detect_device())
            return Session(req, zone, source, detector, cfg, logs_dir, fanout, _app_version())
        except Exception:
            source.close()
            raise

    return factory


def _set_env(root: Path) -> None:
    """§4 "Model and offline": env vars pinned inside `root`, set only if missing."""
    defaults = {
        "YOLO_CONFIG_DIR": str(root / ".uv" / "yolo"),
        "YOLO_OFFLINE": "1",
        "YOLO_AUTOINSTALL": "False",
        "TORCH_HOME": str(root / ".uv" / "torch"),
        "XDG_CACHE_HOME": str(root / ".uv" / "cache"),
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    # Ultralytics falls back to <cwd>/Ultralytics if YOLO_CONFIG_DIR does not exist yet.
    for key in ("YOLO_CONFIG_DIR", "TORCH_HOME", "XDG_CACHE_HOME"):
        Path(os.environ[key]).mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None, *, detector_builder: Callable | None = None) -> int:
    _set_env(ROOT)  # before any import that might touch torch/ultralytics

    lock = read_lock(ROOT)
    if lock is not None and lock_is_live(lock):
        webbrowser.open(f"http://{_HOST}:{lock['port']}/?t={lock['token']}")
        return 0

    port = pick_port()
    token = secrets.token_urlsafe(32)
    write_lock(ROOT, os.getpid(), port, token)
    atexit.register(_remove_lock, ROOT)

    srv: uvicorn.Server | None = None

    def shutdown() -> None:
        if srv is not None:
            srv.should_exit = True

    app = create_app(
        root=ROOT,
        token=token,
        port=port,
        session_factory=make_session_factory(detector_builder or _default_detector_builder),
        cameras=list_cameras,
        shutdown=shutdown,
    )

    url = f"http://{_HOST}:{port}/?t={token}"
    config = uvicorn.Config(app, host=_HOST, port=port, access_log=False, log_level="warning")
    srv = uvicorn.Server(config)

    # `srv.started` flips true once uvicorn is accepting connections; open the
    # browser then, in a daemon thread so it never blocks/delays serving.
    def _open_when_ready() -> None:
        while not getattr(srv, "started", False):
            time.sleep(0.02)
        webbrowser.open(url)

    threading.Thread(target=_open_when_ready, daemon=True).start()

    try:
        srv.run()
    finally:
        _remove_lock(ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
