"""Camera listing, permission status and open-failure mapping.

macOS code paths are exercised on Windows by monkeypatching demo.cameras'
platform-dispatch points (`sys.platform`, the private `_list_macos` /
`_list_windows` helpers, and `AVFoundation`-shaped stand-ins) — never by
importing pyobjc, which is not installed on this machine.
"""

from __future__ import annotations

import cv2
import pytest

from demo import cameras
from demo.cameras import MESSAGES, CameraError, CameraInfo, list_cameras, open_webcam


def test_list_uses_backend_names_and_indexes(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    monkeypatch.setattr(cameras, "_list_windows", lambda: ["Front Camera", "USB Webcam"])

    cams = list_cameras()

    assert cams == [
        CameraInfo(id="cam-0", name="Front Camera", index=0, backend=cv2.CAP_DSHOW),
        CameraInfo(id="cam-1", name="USB Webcam", index=1, backend=cv2.CAP_DSHOW),
    ]


def test_list_macos_uses_avfoundation_backend(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "darwin")
    monkeypatch.setattr(cameras, "_list_macos", lambda: ["FaceTime HD Camera"])

    cams = list_cameras()

    assert cams == [
        CameraInfo(id="cam-0", name="FaceTime HD Camera", index=0, backend=cv2.CAP_AVFOUNDATION),
    ]


def test_list_never_opens_devices(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    monkeypatch.setattr(cameras, "_list_windows", lambda: ["Webcam"])

    def _boom(*args, **kwargs):
        raise AssertionError("list_cameras must never open a device")

    monkeypatch.setattr(cv2, "VideoCapture", _boom)

    cams = list_cameras()

    assert len(cams) == 1


def test_list_returns_empty_on_enumeration_error(monkeypatch, caplog):
    monkeypatch.setattr(cameras.sys, "platform", "win32")

    def _raise():
        raise OSError("dshow enumeration failed")

    monkeypatch.setattr(cameras, "_list_windows", _raise)

    with caplog.at_level("WARNING"):
        cams = list_cameras()

    assert cams == []
    assert "dshow enumeration failed" in caplog.text or "camera" in caplog.text.lower()


def test_list_other_platform_returns_empty(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "linux")

    assert list_cameras() == []


def test_messages_exact():
    assert MESSAGES["denied"] == (
        "Camera access is off for Terminal: System Settings → Privacy & Security "
        "→ Camera → turn on Terminal, then quit and relaunch the demo."
    )
    assert MESSAGES["windows_privacy"] == (
        "Windows may be blocking desktop apps from the camera: Settings → "
        "Privacy & security → Camera → 'Let desktop apps access your camera'."
    )
    assert MESSAGES["busy"] == "Camera unavailable: close other apps using it, then click Go."
    assert MESSAGES["missing"] == "Camera not found: check it is connected, then click Go."


def test_camera_error_exposes_code_and_message():
    err = CameraError("busy")
    assert err.code == "busy"
    assert err.message == MESSAGES["busy"]


def test_permission_status_windows_is_unknown(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    assert cameras.permission_status() == "unknown"


def test_permission_status_other_platform_is_unknown(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "linux")
    assert cameras.permission_status() == "unknown"


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [(0, "not_determined"), (1, "denied"), (2, "denied"), (3, "authorized")],
)
def test_permission_status_macos_maps_avfoundation_status(monkeypatch, raw_status, expected):
    monkeypatch.setattr(cameras.sys, "platform", "darwin")
    monkeypatch.setattr(cameras, "_macos_authorization_status", lambda: raw_status)

    assert cameras.permission_status() == expected


def test_request_permission_non_macos_returns_true(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    assert cameras.request_permission() is True


def test_request_permission_macos_returns_granted_result(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "darwin")

    def _fake_request(timeout_s):
        return True

    monkeypatch.setattr(cameras, "_macos_request_access", _fake_request)

    assert cameras.request_permission(timeout_s=1) is True


def test_request_permission_macos_timeout_returns_false(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "darwin")
    monkeypatch.setattr(cameras, "_macos_request_access", lambda timeout_s: False)

    assert cameras.request_permission(timeout_s=0.01) is False


def test_open_success_returns_webcam(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    monkeypatch.setattr(cameras, "_list_windows", lambda: ["Webcam"])
    cam = CameraInfo(id="cam-0", name="Webcam", index=0, backend=cv2.CAP_DSHOW)

    class FakeWebcam:
        def __init__(self, index, backend, id, name):
            self.index, self.backend, self.id, self.name = index, backend, id, name
            self._opened = False

        def open(self):
            self._opened = True

        def read(self):
            return object()

        def close(self):
            self._opened = False

    monkeypatch.setattr(cameras, "Webcam", FakeWebcam)

    webcam = open_webcam(cam)

    assert isinstance(webcam, FakeWebcam)
    assert webcam._opened is True


def test_open_failure_maps_to_windows_privacy(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    monkeypatch.setattr(cameras, "_list_windows", lambda: ["Webcam"])
    cam = CameraInfo(id="cam-0", name="Webcam", index=0, backend=cv2.CAP_DSHOW)

    class FakeWebcam:
        def __init__(self, index, backend, id, name):
            self.closed = False

        def open(self):
            pass

        def read(self):
            return None

        def close(self):
            self.closed = True

    monkeypatch.setattr(cameras, "Webcam", FakeWebcam)

    with pytest.raises(CameraError) as exc_info:
        open_webcam(cam)

    assert exc_info.value.code == "windows_privacy"


def test_open_missing_device_maps_to_missing(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "win32")
    monkeypatch.setattr(cameras, "_list_windows", lambda: [])
    cam = CameraInfo(id="cam-5", name="Ghost Camera", index=5, backend=cv2.CAP_DSHOW)

    class FakeWebcam:
        def __init__(self, index, backend, id, name):
            pass

        def open(self):
            pass

        def read(self):
            return None

        def close(self):
            pass

    monkeypatch.setattr(cameras, "Webcam", FakeWebcam)

    with pytest.raises(CameraError) as exc_info:
        open_webcam(cam)

    assert exc_info.value.code == "missing"


def test_open_failure_macos_denied_maps_to_denied(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "darwin")
    monkeypatch.setattr(cameras, "_list_macos", lambda: ["FaceTime HD Camera"])
    monkeypatch.setattr(cameras, "permission_status", lambda: "denied")
    cam = CameraInfo(id="cam-0", name="FaceTime HD Camera", index=0, backend=cv2.CAP_AVFOUNDATION)

    class FakeWebcam:
        def __init__(self, index, backend, id, name):
            pass

        def open(self):
            pass

        def read(self):
            return None

        def close(self):
            pass

    monkeypatch.setattr(cameras, "Webcam", FakeWebcam)

    with pytest.raises(CameraError) as exc_info:
        open_webcam(cam)

    assert exc_info.value.code == "denied"


def test_open_failure_default_maps_to_busy(monkeypatch):
    monkeypatch.setattr(cameras.sys, "platform", "darwin")
    monkeypatch.setattr(cameras, "_list_macos", lambda: ["FaceTime HD Camera"])
    monkeypatch.setattr(cameras, "permission_status", lambda: "authorized")
    cam = CameraInfo(id="cam-0", name="FaceTime HD Camera", index=0, backend=cv2.CAP_AVFOUNDATION)

    class FakeWebcam:
        def __init__(self, index, backend, id, name):
            pass

        def open(self):
            pass

        def read(self):
            return None

        def close(self):
            pass

    monkeypatch.setattr(cameras, "Webcam", FakeWebcam)

    with pytest.raises(CameraError) as exc_info:
        open_webcam(cam)

    assert exc_info.value.code == "busy"
