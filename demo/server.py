"""FastAPI routes: wraps the session engine in a local HTTP/WebSocket API.

Routes and behaviour follow docs/design.md §1 (routes table, Go / Apply zone /
Stop / Quit / Tab closed / History drawer), §2 (request shapes), §4 (camera
flow) and §4 "Local server security" (host allowlist, Origin check, launch
token — `SecurityMiddleware` below). `token` and `port` are kept on
`app.state` for tests and diagnostics.

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
import hmac
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote_to_bytes

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from demo.cameras import CameraError, CameraInfo, permission_status, request_permission
from demo.config import ScoringConfig, load_config, save_config
from demo.contracts import SessionRequest, ZoneRequest
from demo.events import Fanout
from demo.session import Session

_VIDEO_FPS = 15
_SEEN_EVERY_S = 1.0
_TAIL_CHUNK = 64 * 1024
_MAX_LINE = 1024 * 1024  # a longer first/last line is treated as corrupt


def _forbidden() -> JSONResponse:
    return JSONResponse(
        {"code": "forbidden", "message": "Missing or invalid token."}, status_code=403
    )


class SecurityMiddleware:
    """Origin check, then launch-token check (docs/design.md §4).

    Runs inside `TrustedHostMiddleware` (the host allowlist is checked first).
    Exempt from the token: `GET`/`HEAD /`, `GET`/`HEAD /favicon.svg` and
    `/assets/*`; the Origin check only applies to non-`GET`/`HEAD`/`OPTIONS`
    requests and the WebSocket handshake, and only when an `Origin` header is
    present (curl/tests may omit it — the token check still guards those).

    The token is compared as bytes, never `str`: `hmac.compare_digest` raises
    `TypeError` on a non-ASCII `str` (a `?t=%C3%A9` or a raw non-ASCII header
    byte would otherwise 500 the request, or leave the WS handshake exception
    uncaught, instead of the intended 403 / clean close).
    """

    def __init__(self, app: ASGIApp, *, token: str, port: int) -> None:
        self.app = app
        self.token = token.encode("utf-8")
        self.allowed_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        is_ws = scope["type"] == "websocket"
        method = scope.get("method", "GET").upper()
        headers = dict(scope["headers"])

        origin = headers.get(b"origin")
        checks_origin = is_ws or method not in ("GET", "HEAD", "OPTIONS")
        if checks_origin and origin is not None:
            if origin.decode("latin-1") not in self.allowed_origins:
                return await self._reject(scope, receive, send, is_ws)

        path = scope["path"]
        exempt = (
            not is_ws
            and method in ("GET", "HEAD")
            and (path in ("/", "/favicon.svg") or path.startswith("/assets/"))
        )
        if exempt:
            return await self.app(scope, receive, send)

        token = self._token_bytes(headers, scope)
        if token is None or not hmac.compare_digest(token, self.token):
            return await self._reject(scope, receive, send, is_ws)

        return await self.app(scope, receive, send)

    @staticmethod
    def _token_bytes(headers: dict[bytes, bytes], scope: Scope) -> bytes | None:
        """The launch token as raw bytes, from the header or the `?t=` query — never `str`."""
        header = headers.get(b"x-demo-token")
        if header is not None:
            return header
        for pair in scope.get("query_string", b"").split(b"&"):
            key, _, value = pair.partition(b"=")
            if key == b"t":
                try:
                    return unquote_to_bytes(value)
                except (ValueError, UnicodeDecodeError):
                    return None
        return None

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, is_ws: bool) -> None:
        if is_ws:
            await receive()  # the "websocket.connect" handshake message
            await send({"type": "websocket.close", "code": 1008})
            return
        await _forbidden()(scope, receive, send)


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


def _summarise(path: Path) -> dict | None:
    """One GET /sessions row from the first and last line only, or None if not our log.

    peak_band comes from `session.ended` (schema 1.1); a crashed or still
    running session has no such last line and is listed as "low".
    """
    with open(path, "rb") as f:
        first = _read_line(f.readline(_MAX_LINE))
        if first is None or first.get("type") != "session.started":
            return None
        last = _read_line(_last_line(f, path.stat().st_size)) or {}
    ended = last.get("type") == "session.ended"
    return {
        "session_id": first.get("session_id"),
        "started_at": first.get("ts"),
        "threat_objects": first.get("threat_objects", []),
        "peak_band": last.get("peak_band", "low") if ended else "low",
        "ended_normally": ended,
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

    st = State()
    lock = asyncio.Lock()  # one start/stop at a time

    async def _keep_alive() -> None:
        while True:
            await asyncio.sleep(_SEEN_EVERY_S)
            if st.clients and st.session is not None:
                st.session.last_client_seen()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        st.fanout = Fanout(asyncio.get_running_loop())
        keep_alive = asyncio.create_task(_keep_alive())
        try:
            yield
        finally:
            keep_alive.cancel()
            await run_in_threadpool(_stop, "quit")

    app = FastAPI(lifespan=lifespan)
    app.state.token, app.state.port = token, port
    # Middleware executes outermost-added-first: TrustedHost, then Origin+token.
    app.add_middleware(SecurityMiddleware, token=token, port=port)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"],
    )

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
        async def _quit() -> None:
            async with lock:  # a racing Go cannot install a session after this stop
                await run_in_threadpool(_stop, "quit")
            shutdown()

        # A JSON body: the web client parses every non-204 response.
        return JSONResponse({}, status_code=202, background=BackgroundTask(_quit))

    @app.get("/video")
    async def video() -> StreamingResponse:
        async def frames():
            # Follows st.session, so the stream survives Apply zone's stop/start
            # gap (the page keeps its <img>); ends with no session and no start.
            while st.session is not None or lock.locked():
                session = st.session
                if session is not None and not lock.locked():
                    if session.health()["status"] != "running":
                        return  # e.g. stopped itself (idle, camera lost)
                jpeg = await run_in_threadpool(session.latest_jpeg) if session else None
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
            while (await ws.receive())["type"] != "websocket.disconnect":
                pass

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
                row = _summarise(path)
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
