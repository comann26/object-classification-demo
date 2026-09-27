"""Task 12: FastAPI routes (docs/design.md §1 routes/behaviour, §2 requests, §4 camera)."""

import builtins
import json
import shutil
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import demo.server as server
from demo.cameras import MESSAGES, CameraError, CameraInfo
from demo.config import ScoringConfig, config_sha256, load_config
from demo.detector import FakeDetector
from demo.session import Session
from demo.source import SyntheticSource
from demo.testing import quiet_frame

REPO = Path(__file__).resolve().parents[2]
CAMS = [CameraInfo(id="cam-0", name="Test Cam", index=0, backend=0)]
GO = {"threat_objects": ["knife"], "source": "cam-0"}


def _slow_frame(i):
    time.sleep(0.005)  # fps=1000 frame clock: idle_stop_s (30 s) is 30 000 frames away
    return quiet_frame(i)


class Factory:
    """A session_factory on SyntheticSource + FakeDetector, recording its calls."""

    def __init__(self):
        self.calls = []
        self.errors: list[CameraError] = []  # raised (in order) before succeeding
        self.gate: threading.Event | None = None

    def __call__(self, req, zone, camera, *, cfg, logs_dir, fanout):
        self.calls.append((req, zone, camera))
        if self.gate is not None:
            self.gate.wait(10)
        if self.errors:
            raise self.errors.pop(0)
        source = SyntheticSource(_slow_frame, fps=1000, id=camera.id)
        return Session(req, zone, source, FakeDetector(lambda f: []), cfg, logs_dir, fanout, "test")


@pytest.fixture
def root(tmp_path):
    shutil.copytree(REPO / "config", tmp_path / "config")
    (tmp_path / "web" / "dist" / "assets").mkdir(parents=True)
    (tmp_path / "web" / "dist" / "index.html").write_text("<title>demo</title>")
    (tmp_path / "web" / "dist" / "assets" / "app.js").write_text("x")
    return tmp_path


@pytest.fixture
def factory():
    return Factory()


@pytest.fixture
def shutdown():
    calls = []
    fn = lambda: calls.append(1)  # noqa: E731
    fn.calls = calls
    return fn


@pytest.fixture
def client(root, factory, shutdown):
    app = server.create_app(
        root=root,
        token="tok",
        port=8000,
        session_factory=factory,
        cameras=lambda: CAMS,
        shutdown=shutdown,
    )
    headers = {"X-Demo-Token": "tok", "Host": "127.0.0.1:8000"}  # Host: TestClient's websocket
    # handshake ignores base_url and always sends "testserver" unless overridden here.
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=headers) as c:
        yield c


def _first_event(root, session_id):
    with open(root / "logs" / f"{session_id}.jsonl", encoding="utf-8") as f:
        return json.loads(f.readline())


def test_go_starts_session_and_ws_receives_started(client):
    with client.websocket_connect("/events?t=tok") as ws:
        r = client.post("/session", json=GO)
        assert r.status_code == 200
        sid = r.json()["session_id"]
        ev = ws.receive_json()
        assert ev["type"] == "session.started"
        assert ev["session_id"] == sid
        assert ev["source"] == "cam-0"
        assert ev["threat_objects"] == ["knife"]


def test_second_go_while_starting_is_409(client, factory):
    factory.gate = threading.Event()
    first = {}
    t = threading.Thread(target=lambda: first.update(r=client.post("/session", json=GO)))
    t.start()
    for _ in range(200):
        if factory.calls:
            break
        time.sleep(0.01)
    r = client.post("/session", json=GO)
    assert r.status_code == 409
    assert r.json() == {"code": "starting", "message": "Already starting — please wait."}
    factory.gate.set()
    t.join(10)
    assert first["r"].status_code == 200


def test_zone_apply_keeps_words_and_camera_new_session_id(client, root, factory):
    assert client.post("/session/zone", json={"zone": None}).status_code == 409  # no session
    sid = client.post("/session", json={**GO, "save_stills": True}).json()["session_id"]
    zone = [[0.1, 0.6], [0.5, 0.6], [0.5, 0.95], [0.1, 0.95]]
    r = client.post("/session/zone", json={"zone": zone})
    assert r.status_code == 200
    new = r.json()["session_id"]
    assert new != sid
    req, got_zone, camera = factory.calls[-1]
    assert req.threat_objects == ["knife"] and req.source == "cam-0"
    assert req.save_stills is False
    assert camera == CAMS[0]
    started = _first_event(root, new)
    assert started["zone"] == zone and started["source"] == "cam-0"
    # the old session ended normally
    old_last = (root / "logs" / f"{sid}.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(old_last)["type"] == "session.ended"
    assert client.get("/health").json()["session_id"] == new


def test_stop_is_204_and_idempotent(client, root):
    sid = client.post("/session", json=GO).json()["session_id"]
    assert client.delete("/session").status_code == 204
    assert client.delete("/session").status_code == 204
    last = (root / "logs" / f"{sid}.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(last)["reason"] == "stopped"
    assert client.get("/health").json()["status"] == "idle"


def test_quit_calls_shutdown(client, shutdown, root):
    sid = client.post("/session", json=GO).json()["session_id"]
    r = client.post("/quit")
    assert r.status_code == 202 and r.json() == {}
    assert shutdown.calls == [1]
    last = (root / "logs" / f"{sid}.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(last)["reason"] == "quit"


def test_put_config_out_of_range_422(client, root):
    cfg = client.get("/config").json()
    before = (root / "config" / "scoring.json").read_text(encoding="utf-8")
    cfg["detect"]["person_min"] = 1.5
    assert client.put("/config", json=cfg).status_code == 422
    assert (root / "config" / "scoring.json").read_text(encoding="utf-8") == before


def test_put_config_hash_in_next_session_started(client, root):
    cfg = client.get("/config").json()
    cfg["weights"]["link"] = 42
    assert client.put("/config", json=cfg).status_code == 204
    assert client.get("/config").json()["weights"]["link"] == 42
    sid = client.post("/session", json=GO).json()["session_id"]
    started = _first_event(root, sid)
    expected = config_sha256(ScoringConfig.model_validate(cfg))
    assert started["provenance"]["config_sha256"] == expected
    assert expected == config_sha256(load_config(root / "config" / "scoring.json"))


def test_go_unexpected_error_is_500_json(client, factory, caplog):
    # e.g. CUDA .to() or CLIP load failing: a plain message, never "failed: 500" (final review #3).
    factory.errors = [RuntimeError("CUDA error: device-side assert")]
    r = client.post("/session", json=GO)
    assert r.status_code == 500
    assert r.json() == {"code": "error", "message": server.RESTART_MESSAGE}
    assert server.RESTART_MESSAGE == "Something went wrong — click Go to restart"
    assert any(rec.exc_info for rec in caplog.records)  # the console gets the traceback
    assert not any("tok" in rec.getMessage() for rec in caplog.records)
    assert client.get("/health").json()["status"] == "idle"


def _corrupt_config(root):
    (root / "config" / "scoring.json").write_text("{not json", encoding="utf-8")


def test_get_config_corrupt_is_500_json(client, root):
    _corrupt_config(root)
    r = client.get("/config")
    assert r.status_code == 500
    assert r.json() == {"code": "config", "message": server.CONFIG_DAMAGED_MESSAGE}
    assert server.CONFIG_DAMAGED_MESSAGE == "Settings file is damaged — use Reset to defaults."


def test_put_config_repairs_corrupt_file(client, root):
    # "Reset to defaults" PUTs schema defaults; it must work even when the file is damaged.
    _corrupt_config(root)
    assert client.put("/config", json=ScoringConfig().model_dump(mode="json")).status_code == 204
    assert client.get("/config").json() == ScoringConfig().model_dump(mode="json")


def test_go_with_corrupt_config_is_500_json(client, root):
    _corrupt_config(root)
    r = client.post("/session", json=GO)
    assert r.status_code == 500
    assert r.json() == {"code": "error", "message": server.RESTART_MESSAGE}


def _write_log(path, first, last, filler_bytes=0):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(first) + "\n")
        line = json.dumps({"type": "source.health", "pad": "x" * 1000}) + "\n"
        for _ in range(filler_bytes // len(line)):
            f.write(line)
        if last is not None:
            f.write(json.dumps(last) + "\n")


def _started(sid, ts, words=("knife",)):
    return {"type": "session.started", "session_id": sid, "ts": ts, "threat_objects": list(words)}


def test_sessions_list_reads_only_first_and_last_lines(client, root, monkeypatch):
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    sid = "11111111-1111-1111-1111-111111111111"
    _write_log(
        logs / f"{sid}.jsonl",
        _started(sid, "2026-09-26T10:00:00.000Z"),
        {"type": "session.ended", "reason": "stopped", "peak_band": "critical"},
        filler_bytes=50 * 1024 * 1024,
    )
    read = [0]
    real_open = builtins.open

    class Spy:
        def __init__(self, f):
            self._f = f

        def __getattr__(self, name):
            return getattr(self._f, name)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self._f.close()

        def __iter__(self):
            for line in self._f:
                read[0] += len(line)
                yield line

        def read(self, *a):
            data = self._f.read(*a)
            read[0] += len(data)
            return data

        def readline(self, *a):
            data = self._f.readline(*a)
            read[0] += len(data)
            return data

    monkeypatch.setattr(server, "open", lambda *a, **k: Spy(real_open(*a, **k)), raising=False)
    rows = client.get("/sessions").json()
    assert rows == [
        {
            "session_id": sid,
            "started_at": "2026-09-26T10:00:00.000Z",
            "threat_objects": ["knife"],
            "peak_band": "critical",
            "ended_normally": True,
        }
    ]
    assert read[0] < 1024 * 1024


def test_sessions_list_skips_foreign_files(client, root):
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    (logs / "notes.txt").write_text("hello")
    (logs / "broken.jsonl").write_bytes(b"\x00\xffnot json\n")
    a, b = "22222222-2222-2222-2222-222222222222", "33333333-3333-3333-3333-333333333333"
    _write_log(
        logs / f"{a}.jsonl",
        _started(a, "2026-09-26T10:00:00.000Z"),
        {"type": "session.ended", "peak_band": "high"},
    )
    _write_log(
        logs / f"{b}.jsonl",
        _started(b, "2026-09-26T11:00:00.000Z", ["gun"]),
        {"type": "track.updated", "threat": {"band": "high"}},
    )
    rows = client.get("/sessions").json()
    assert [r["session_id"] for r in rows] == [b, a]  # newest first
    assert rows[0]["peak_band"] == "low" and rows[0]["ended_normally"] is False  # crashed
    assert rows[1]["peak_band"] == "high" and rows[1]["ended_normally"] is True


def test_crashed_session_listed_as_truncated(client, root):
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    sid = "44444444-4444-4444-4444-444444444444"
    _write_log(logs / f"{sid}.jsonl", _started(sid, "2026-09-26T10:00:00.000Z"), None)
    with open(logs / f"{sid}.jsonl", "a", encoding="utf-8") as f:
        f.write('{"type": "session.ended", "rea')  # half-written last line, no newline
    rows = client.get("/sessions").json()
    assert rows[0]["session_id"] == sid and rows[0]["ended_normally"] is False
    events = client.get(f"/sessions/{sid}/events").json()
    assert [e["type"] for e in events] == ["session.started"]  # the torn line is dropped
    assert client.get("/sessions/55555555-5555-5555-5555-555555555555/events").status_code == 404
    assert client.get("/sessions/not-a-uuid/events").status_code == 422


def test_sessions_live_session_listed_with_events(client):
    sid = client.post("/session", json=GO).json()["session_id"]
    client.delete("/session")
    rows = client.get("/sessions").json()
    assert rows[0]["session_id"] == sid and rows[0]["ended_normally"] is True
    assert rows[0]["peak_band"] == "low"  # from session.ended; no detections
    events = client.get(f"/sessions/{sid}/events").json()
    assert events[0]["type"] == "session.started" and events[-1]["type"] == "session.ended"


def test_health_fields(client):
    keys = {"status", "session_id", "fps", "camera", "model", "input_size", "device"}
    idle = client.get("/health").json()
    assert idle == {
        "status": "idle",
        "session_id": None,
        "fps": 0,
        "camera": None,
        "model": None,
        "input_size": None,
        "device": None,
    }
    sid = client.post("/session", json=GO).json()["session_id"]
    h = client.get("/health").json()
    assert set(h) == keys
    assert h["session_id"] == sid and h["status"] == "running" and h["camera"] == "cam-0"
    assert client.get("/cameras").json() == [{"id": "cam-0", "name": "Test Cam"}]


def test_go_maps_camera_error_to_message(client, factory, monkeypatch):
    monkeypatch.setattr(server, "permission_status", lambda: "denied")
    factory.errors = [CameraError("denied")]
    r = client.post("/session", json=GO)
    assert r.status_code == 409
    assert r.json() == {"code": "denied", "message": MESSAGES["denied"]}
    assert client.get("/health").json()["status"] == "idle"
    r = client.post("/session", json={**GO, "source": "cam-9"})  # not in GET /cameras
    assert r.status_code == 409 and r.json()["code"] == "missing"


def test_go_maps_setup_error_to_503_plain_message(client, factory, caplog):
    from demo.models import SetupError

    factory.errors = [SetupError("First-time setup needs internet once.")]
    r = client.post("/session", json=GO)
    assert r.status_code == 503
    assert r.json() == {"code": "setup", "message": "First-time setup needs internet once."}
    assert client.get("/health").json()["status"] == "idle"
    assert not any(rec.exc_info for rec in caplog.records)  # never a stack trace


def test_macos_not_determined_requests_then_retries_once(client, factory, monkeypatch):
    requested = []
    monkeypatch.setattr(server, "permission_status", lambda: "not_determined")
    monkeypatch.setattr(server, "request_permission", lambda: requested.append(1) or True)
    factory.errors = [CameraError("busy")]
    r = client.post("/session", json=GO)
    assert r.status_code == 200
    assert requested == [1] and len(factory.calls) == 2
    # still failing after the retry: no third attempt
    factory.errors = [CameraError("busy"), CameraError("busy")]
    calls = len(factory.calls)
    r = client.post("/session", json=GO)
    assert r.status_code == 409 and r.json()["code"] == "busy"
    assert len(factory.calls) == calls + 2


def test_connected_ws_marks_client_seen(client, monkeypatch):
    seen = []
    monkeypatch.setattr(Session, "last_client_seen", lambda self: seen.append(self.id))
    sid = client.post("/session", json=GO).json()["session_id"]
    with client.websocket_connect("/events?t=tok"):
        time.sleep(1.3)  # the keep-alive ticks every 1 s while a client is connected
    n = len(seen)
    assert n >= 2 and set(seen) == {sid}  # once on connect, then per tick
    time.sleep(1.2)
    assert len(seen) == n  # no clients: no more marks


def test_static_index_and_assets(client):
    assert "demo" in client.get("/").text
    assert client.get("/assets/app.js").text == "x"
    r = client.get("/video")  # no session: the stream ends at once
    assert r.headers["content-type"].startswith("multipart/x-mixed-replace; boundary=frame")
    # Never cached: an identical URL across sessions must always be re-fetched
    # (docs/knowledge — a cached empty pre-session stream showed as a dead feed).
    assert r.headers["cache-control"] == "no-store"


def test_video_accepts_session_query_param(client, monkeypatch):
    # The web client appends `&s=<sessionId>` to bust the browser's image
    # cache; the security middleware only reads `t`, so the extra param must
    # not affect the token check or the stream.
    monkeypatch.setattr(Session, "latest_jpeg", lambda self: self.id.encode())
    sid = client.post("/session", json=GO).json()["session_id"]
    body = {}
    t = threading.Thread(target=lambda: body.update(r=client.get(f"/video?t=tok&s={sid}")))
    t.start()
    time.sleep(0.3)
    client.delete("/session")  # ends the stream
    t.join(10)
    r = body["r"]
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert sid.encode() in r.content


def test_video_stream_survives_zone_swap(client, monkeypatch):
    # Each "frame" is the id of the session it came from.
    monkeypatch.setattr(Session, "latest_jpeg", lambda self: self.id.encode())
    old = client.post("/session", json=GO).json()["session_id"]
    body = {}
    t = threading.Thread(target=lambda: body.update(r=client.get("/video")))
    t.start()
    time.sleep(0.3)
    new = client.post("/session/zone", json={"zone": None}).json()["session_id"]
    time.sleep(0.3)
    client.delete("/session")  # no session and no start: the stream ends
    t.join(10)
    data = body["r"].content  # TestClient buffers the whole stream
    assert old.encode() in data and new.encode() in data
    assert data.rindex(new.encode()) > data.rindex(old.encode())
