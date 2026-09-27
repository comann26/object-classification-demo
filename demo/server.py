"""FastAPI routes: wraps the session engine in a local HTTP/WebSocket API.

Routes and behaviour follow docs/design.md §1 (routes table, Go / Apply zone /
Stop / Quit / Tab closed / History drawer), §2 (request shapes) and §4
(camera flow). Host/Origin/token checks are Task 13; `token` and `port` are
kept on `app.state` for it.

`session_factory(req, zone, camera, *, cfg, logs_dir, fanout) -> Session`
builds a not-yet-started Session. The app passes `cfg` (read fresh from
`config/scoring.json` on each Go, so slider changes apply on the next Go),
`logs_dir` and its own `Fanout` (bound to the server loop, so the engine
thread can publish safely). A camera failure is a `CameraError` raised by
the factory or by `Session.start()`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import get_args

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from demo.cameras import CameraError, CameraInfo, permission_status, request_permission
from demo.config import ScoringConfig, load_config, save_config
from demo.contracts import Band, SessionRequest, ZoneRequest
from demo.events import Fanout
from demo.session import Session

_BANDS = get_args(Band)
_VIDEO_FPS = 15
_SEEN_EVERY_S = 1.0
_TAIL_CHUNK = 64 * 1024
_MAX_LINE = 1024 * 1024  # a longer first/last line is treated as corrupt


def _camera_error(e: CameraError) -> JSONResponse:
    return JSONResponse({"code": e.code, "message": e.message}, status_code=409)


def _read_line(line: bytes) -> dict | None:
    try:
        obj = json.loads(line)
    except (ValueError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _last_line(f, size: int) -> bytes:
    """The last line of `f`, found by reading backwards from the end in chunks."""
    buf, pos = b"", size
    while pos > 0 and len(buf) <= _MAX_LINE:
        step = min(_TAIL_CHUNK, pos)
        pos -= step
        f.seek(pos)
        buf = f.read(step) + buf
        parts = buf.rstrip(b"\n").rsplit(b"\n", 1)
        if len(parts) == 2:
            return parts[1]
    return buf.rstrip(b"\n")


def _summarise(path: Path, live_peaks: dict[str, str]) -> dict | None:
    """One GET /sessions row from the first and last line only, or None if not our log.

    Ruling (Task 12): peak_band would need the whole log. Sessions started in
    this process have their peak tracked live (`live_peaks`); for older logs
    we read only the last line: its band if it is a track event, else "low".
    """
    with open(path, "rb") as f:
        first = _read_line(f.readline(_MAX_LINE))
        if first is None or first.get("type") != "session.started":
            return None
        last = _read_line(_last_line(f, path.stat().st_size)) or {}
    sid = first.get("session_id")
    peak = live_peaks.get(sid)
    if peak is None:
        if last.get("type") == "track.updated":
            peak = last.get("threat", {}).get("band", "low")
        elif last.get("type") == "track.ended":
            peak = last.get("peak_band", "low")
        else:
            peak = "low"
    return {
        "session_id": sid,
        "started_at": first.get("ts"),
        "threat_objects": first.get("threat_objects", []),
        "peak_band": peak,
        "ended_normally": last.get("type") == "session.ended",
    }


def create_app(
    *,
    root: Path,
    token: str,
    port: int,
    session_factory: Callable[..., Session],
    cameras: Callable[[], list[CameraInfo]],
    shutdown: Callable[[], None],
) -> FastAPI:
    root = Path(root)
    config_path = root / "config" / "scoring.json"
    logs_dir = root / "logs"

    class State:
        fanout: Fanout = Fanout()  # rebound to the server loop in lifespan
        session: Session | None = None
        camera: CameraInfo | None = None
        clients = 0
        live_peaks: dict[str, str] = {}

    st = State()
    lock = asyncio.Lock()  # one start/stop at a time

    async def _track_peaks() -> None:
        queue = st.fanout.subscribe()
        while True:
            ev = await queue.get()
            band = None
            if ev.get("type") == "track.updated":
                band = ev["threat"]["band"]
            elif ev.get("type") == "track.ended":
                band = ev["peak_band"]
            elif ev.get("type") == "session.started":
                st.live_peaks.setdefault(ev["session_id"], "low")
            if band is not None:
                old = st.live_peaks.get(ev["session_id"], "low")
                st.live_peaks[ev["session_id"]] = max(old, band, key=_BANDS.index)

    async def _keep_alive() -> None:
        while True:
            await asyncio.sleep(_SEEN_EVERY_S)
            if st.clients and st.session is not None:
                st.session.last_client_seen()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        st.fanout = Fanout(asyncio.get_running_loop())
        tasks = [asyncio.create_task(_track_peaks()), asyncio.create_task(_keep_alive())]
        try:
            yield
        finally:
            for t in tasks:
                t.cancel()
            await run_in_threadpool(_stop, "quit")

    app = FastAPI(lifespan=lifespan)
    app.state.token, app.state.port = token, port

    def _stop(reason: str) -> None:
        session, st.session, st.camera = st.session, None, None
        if session is not None:
            session.stop(reason)

    def _open(req: SessionRequest, zone, camera: CameraInfo) -> Session:
        session = session_factory(
            req, zone, camera, cfg=load_config(config_path), logs_dir=logs_dir, fanout=st.fanout
        )
        session.start()
        return session

    def _start(req: SessionRequest, zone, camera: CameraInfo) -> Session:
        try:
            return _open(req, zone, camera)
        except CameraError:
            # §4 macOS: not yet asked → ask (the start waits), then retry the open once.
            if permission_status() != "not_determined":
                raise
            request_permission()
            return _open(req, zone, camera)

    async def _go(req: SessionRequest, zone, camera: CameraInfo | None) -> Response:
        if lock.locked():
            return JSONResponse(
                {"code": "starting", "message": "Already starting — please wait."},
                status_code=409,
            )
        async with lock:
            await run_in_threadpool(_stop, "stopped")  # Go: nothing carries over
            try:
                if camera is None:
                    raise CameraError("missing")
                session = await run_in_threadpool(_start, req, zone, camera)
            except CameraError as e:
                return _camera_error(e)
            st.session, st.camera = session, camera
            return JSONResponse({"session_id": session.id})

    @app.post("/session")
    async def post_session(req: SessionRequest) -> Response:
        listed = await run_in_threadpool(cameras)  # only cameras from GET /cameras
        camera = next((c for c in listed if c.id == req.source), None)
        return await _go(req, None, camera)

    @app.post("/session/zone")
    async def post_zone(body: ZoneRequest) -> Response:
        active, camera = st.session, st.camera
        if active is None or camera is None:
            return JSONResponse(
                {"code": "no_session", "message": "Click Go first."}, status_code=409
            )
        req = SessionRequest(
            threat_objects=active.threat_objects, source=active.req.source, save_stills=False
        )
        return await _go(req, body.zone, camera)

    @app.delete("/session", status_code=204)
    async def delete_session() -> None:
        async with lock:
            await run_in_threadpool(_stop, "stopped")

    @app.post("/quit", status_code=202)
    async def quit_() -> Response:
        def _quit() -> None:
            _stop("quit")
            shutdown()

        return Response(status_code=202, background=BackgroundTask(_quit))

    @app.get("/video")
    async def video() -> StreamingResponse:
        async def frames():
            session = st.session
            while session is not None and st.session is session:
                if session.health()["status"] != "running":
                    return
                jpeg = session.latest_jpeg()
                if jpeg is not None:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                await asyncio.sleep(1 / _VIDEO_FPS)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/events")
    async def events(ws: WebSocket) -> None:
        await ws.accept()
        queue = st.fanout.subscribe()
        st.clients += 1
        if st.session is not None:
            st.session.last_client_seen()

        async def _until_disconnect() -> None:
            with contextlib.suppress(WebSocketDisconnect):
                while True:
                    await ws.receive()

        closed = asyncio.create_task(_until_disconnect())
        getter: asyncio.Task | None = None
        try:
            while True:
                getter = asyncio.ensure_future(queue.get())
                done, _ = await asyncio.wait({getter, closed}, return_when=asyncio.FIRST_COMPLETED)
                if closed in done:
                    return
                await ws.send_json(getter.result())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            st.clients -= 1
            st.fanout.unsubscribe(queue)
            closed.cancel()
            if getter is not None:
                getter.cancel()

    @app.get("/health")
    def health() -> dict:
        if st.session is None:
            return {
                "status": "idle",
                "session_id": None,
                "fps": 0,
                "camera": None,
                "model": None,
                "input_size": None,
                "device": None,
            }
        return st.session.health()

    @app.get("/cameras")
    def get_cameras() -> list[dict]:
        return [{"id": c.id, "name": c.name} for c in cameras()]

    @app.get("/config")
    def get_config() -> dict:
        return load_config(config_path).model_dump(mode="json")

    @app.put("/config", status_code=204)
    def put_config(cfg: ScoringConfig) -> None:
        save_config(cfg, config_path)

    @app.get("/sessions")
    def sessions() -> list[dict]:
        rows = []
        for path in logs_dir.glob("*.jsonl"):
            try:
                row = _summarise(path, st.live_peaks)
            except OSError:
                continue
            if row is not None:
                rows.append(row)
        return sorted(rows, key=lambda r: r["started_at"] or "", reverse=True)

    @app.get("/sessions/{session_id}/events")
    def session_events(session_id: uuid.UUID) -> list[dict]:
        path = logs_dir / f"{session_id}.jsonl"
        if not path.is_file():
            raise HTTPException(404, "No such session.")
        with open(path, "rb") as f:
            return [e for e in map(_read_line, f) if e is not None]

    app.mount("/", StaticFiles(directory=root / "web" / "dist", html=True, check_dir=False))
    return app
