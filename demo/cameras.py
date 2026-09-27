"""Camera listing and permission handling, without ever opening a device.

`list_cameras()` enumerates devices through the OS's own device list
(AVFoundation on macOS, DirectShow on Windows) and never calls
`cv2.VideoCapture` — so no camera light and no permission prompt (see
docs/design.md §4 Camera). macOS-specific imports (pyobjc) happen lazily,
inside the `_macos_*` helpers, so importing this module on Windows never
touches pyobjc.

The OpenCV index of a listed device is assumed to equal its position in the
platform device list; that assumption is verified on real machines and
recorded in docs/knowledge/ (not yet written — see design.md §4).
"""

from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from typing import Literal

import cv2

from demo.source import Webcam

log = logging.getLogger(__name__)

PermissionStatus = Literal["authorized", "not_determined", "denied", "unknown"]
CameraErrorCode = Literal["busy", "missing", "denied", "windows_privacy"]

MESSAGES: dict[CameraErrorCode, str] = {
    "denied": (
        "Camera access is off for Terminal: System Settings → Privacy & Security "
        "→ Camera → turn on Terminal, then quit and relaunch the demo."
    ),
    "windows_privacy": (
        "Windows may be blocking desktop apps from the camera: Settings → "
        "Privacy & security → Camera → 'Let desktop apps access your camera'."
    ),
    "busy": "Camera unavailable: close other apps using it, then click Go.",
    "missing": "Camera not found: check it is connected, then click Go.",
}


@dataclass(frozen=True, slots=True)
class CameraInfo:
    id: str
    name: str
    index: int
    backend: int


class CameraError(Exception):
    """Raised by `open_webcam` with one of the codes in `MESSAGES`."""

    def __init__(self, code: CameraErrorCode) -> None:
        super().__init__(MESSAGES[code])
        self.code = code
        self.message = MESSAGES[code]


def _list_macos() -> list[str]:
    from AVFoundation import AVCaptureDevice, AVMediaTypeVideo  # noqa: PLC0415

    devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeVideo)
    return [str(d.localizedName()) for d in devices]


def _list_windows() -> list[str]:
    from pygrabber.dshow_graph import FilterGraph  # noqa: PLC0415

    return list(FilterGraph().get_input_devices())


def list_cameras() -> list[CameraInfo]:
    """Enumerate cameras via the OS device list. Never opens a device."""
    if sys.platform == "darwin":
        backend = cv2.CAP_AVFOUNDATION
        lister = _list_macos
    elif sys.platform == "win32":
        backend = cv2.CAP_DSHOW
        lister = _list_windows
    else:
        return []

    try:
        names = lister()
    except Exception:
        log.warning("camera enumeration failed", exc_info=True)
        return []

    return [
        CameraInfo(id=f"cam-{i}", name=name, index=i, backend=backend)
        for i, name in enumerate(names)
    ]


def _macos_authorization_status() -> int:
    from AVFoundation import AVCaptureDevice, AVMediaTypeVideo  # noqa: PLC0415

    return AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeVideo)


def permission_status() -> PermissionStatus:
    if sys.platform != "darwin":
        return "unknown"

    status = _macos_authorization_status()
    return {0: "not_determined", 1: "denied", 2: "denied", 3: "authorized"}.get(status, "unknown")


def _macos_request_access(timeout_s: float) -> bool:
    from AVFoundation import AVCaptureDevice, AVMediaTypeVideo  # noqa: PLC0415

    granted = False
    done = threading.Event()

    def _completion(result: bool) -> None:
        nonlocal granted
        granted = bool(result)
        done.set()

    AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVMediaTypeVideo, _completion)
    if not done.wait(timeout_s):
        return False
    return granted


def request_permission(timeout_s: float = 60) -> bool:
    if sys.platform != "darwin":
        return True
    return _macos_request_access(timeout_s)


def open_webcam(cam: CameraInfo) -> Webcam:
    """Open `cam`, or raise `CameraError` mapped per docs/design.md §4."""
    webcam = Webcam(index=cam.index, backend=cam.backend, id=cam.id, name=cam.name)
    ok = False
    try:
        webcam.open()
        ok = webcam.read() is not None
    except Exception:
        ok = False
    if ok:
        return webcam

    webcam.close()

    listed_indexes = {c.index for c in list_cameras()}
    if cam.index not in listed_indexes:
        raise CameraError("missing")
    if sys.platform == "darwin" and permission_status() == "denied":
        raise CameraError("denied")
    if sys.platform == "win32":
        raise CameraError("windows_privacy")
    raise CameraError("busy")
