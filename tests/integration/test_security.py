"""Task 13: host allowlist, Origin check, launch token (docs/design.md §4).

Other pages open in the same browser could otherwise reach the local server
(CSRF / DNS rebinding); every route but `GET /` and `/assets/*` must refuse a
request that lacks the launch token, and non-GET requests / the WebSocket
handshake must refuse a foreign `Origin`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from starlette.routing import Route

import demo.server as server
from demo.cameras import CameraInfo

REPO = Path(__file__).resolve().parents[2]
PORT = 8000
BASE_URL = f"http://127.0.0.1:{PORT}"
TOKEN = "tok"
CAMS = [CameraInfo(id="cam-0", name="Test Cam", index=0, backend=0)]
_SESSION_ID = "11111111-1111-1111-1111-111111111111"


def _make_app(root: Path):
    return server.create_app(
        root=root,
        token=TOKEN,
        port=PORT,
        session_factory=lambda *a, **k: None,  # unused: every test rejects before a session_factory call
        cameras=lambda: CAMS,
        shutdown=lambda: None,
    )


def _protected_routes(app) -> list[tuple[str, str]]:
    """(method, concrete path) for every route but `GET /` and the `/assets` mount.

    Derived from the live app's routes (not a hand-kept list), so a new route
    is covered automatically. `Route`/`APIRoute` covers plain HTTP routes; the
    `/assets` StaticFiles `Mount` and the `/events` `APIWebSocketRoute` are not
    `Route` subclasses and so are excluded here on purpose (assets are exempt;
    the websocket is checked separately, since it fails a different way).
    """
    out = []
    for r in app.routes:
        if not isinstance(r, Route) or r.path == "/":
            continue
        path = r.path.replace("{session_id}", _SESSION_ID)
        for method in (r.methods or set()) - {"HEAD", "OPTIONS"}:
            out.append((method, path))
    return out


# Built once, at import time, purely from routing metadata (no app state touched).
PROTECTED_ROUTES = _protected_routes(_make_app(REPO))


@pytest.fixture
def root(tmp_path):
    shutil.copytree(REPO / "config", tmp_path / "config")
    (tmp_path / "web" / "dist" / "assets").mkdir(parents=True)
    (tmp_path / "web" / "dist" / "index.html").write_text("<title>demo</title>")
    (tmp_path / "web" / "dist" / "assets" / "app.js").write_text("x")
    (tmp_path / "web" / "dist" / "favicon.svg").write_text("<svg></svg>")
    return tmp_path


@pytest.fixture
def app(root):
    return _make_app(root)


@pytest.fixture
def anon(app):
    """What a foreign page (or curl) sends: right host, no token, no origin."""
    with TestClient(app, base_url=BASE_URL, headers={"Host": f"127.0.0.1:{PORT}"}) as c:
        yield c


@pytest.fixture
def client(app):
    """The demo's own page: right host, valid token."""
    headers = {"X-Demo-Token": TOKEN, "Host": f"127.0.0.1:{PORT}"}
    with TestClient(app, base_url=BASE_URL, headers=headers) as c:
        yield c


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES, ids=[f"{m} {p}" for m, p in PROTECTED_ROUTES])
def test_missing_token_403(anon, method, path):
    r = anon.request(method, path)
    assert r.status_code == 403
    assert r.json() == {"code": "forbidden", "message": "Missing or invalid token."}


def test_wrong_token_403(anon):
    r = anon.get("/health", headers={"X-Demo-Token": "wrong"})
    assert r.status_code == 403
    assert r.json() == {"code": "forbidden", "message": "Missing or invalid token."}


def test_foreign_origin_on_post_403(client):
    r = client.post("/quit", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_foreign_origin_on_ws_rejected(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/events?t=tok", headers={"Origin": "https://evil.example"}):
            pass


def test_foreign_host_400(client):
    r = client.get("/health", headers={"Host": "evil.example:8000"})
    assert r.status_code == 400


def test_non_uuid_session_id_422(client):
    # "not-a-uuid" is one path segment: it reaches the handler and fails uuid
    # parsing -- the 422 that guarantees session_id can't become a file path.
    assert client.get("/sessions/not-a-uuid/events").status_code == 422
    # "..%2F..%2Fetc" decodes to "../../etc" *before* routing, so it never
    # matches the single-segment {session_id} route at all: Starlette's router
    # itself blocks the traversal attempt with a 404 rather than the UUID
    # parser -- the file is never touched either way.
    r = client.get("/sessions/..%2F..%2Fetc/events")
    assert r.status_code == 404


def test_index_served_without_token(anon):
    r = anon.get("/")
    assert "demo" in r.text


def test_assets_served_without_token(anon):
    r = anon.get("/assets/app.js")
    assert r.status_code == 200
    assert r.text == "x"


def test_favicon_served_without_token(anon):
    r = anon.get("/favicon.svg")
    assert r.status_code == 200
    assert r.text == "<svg></svg>"


def test_non_ascii_token_header_403(anon):
    # hmac.compare_digest raises TypeError on a non-ASCII str; the token must
    # be compared as bytes so this 403s instead of 500ing.
    r = anon.get("/health", headers={"X-Demo-Token": b"\xff"})
    assert r.status_code == 403
    assert r.json() == {"code": "forbidden", "message": "Missing or invalid token."}


def test_non_ascii_token_query_403(anon):
    r = anon.get("/health?t=%C3%A9")  # decodes to a non-ASCII "é"
    assert r.status_code == 403
    assert r.json() == {"code": "forbidden", "message": "Missing or invalid token."}


def test_non_ascii_token_ws_rejected(anon):
    with pytest.raises(WebSocketDisconnect):
        with anon.websocket_connect("/events?t=%C3%A9"):
            pass
