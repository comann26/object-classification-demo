"""Event log: canonical JSON, hash-chained append-only log, and WebSocket fan-out.

See docs/design.md §2 "Hash chain" and §4 "Tamper check".
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def canonical_json(obj: dict) -> bytes:
    """Deterministic JSON bytes: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def event_hash(event: dict) -> str:
    """SHA-256 hex digest of `event`'s canonical JSON with `provenance.hash` removed."""
    provenance = {k: v for k, v in event["provenance"].items() if k != "hash"}
    body = {**event, "provenance": provenance}
    return hashlib.sha256(canonical_json(body)).hexdigest()


class EventLog:
    """Appends events to a hash-chained JSONL file.

    One file per session, written fresh (opening an existing file to resume
    is not supported). Does not validate against the Pydantic `Event` model
    — callers are responsible for producing valid events; this stays fast
    and schema-agnostic.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("wb")
        self._prev_hash = GENESIS

    def append(self, event: dict) -> dict:
        """Fill in `provenance.prev_hash`/`hash`, write one line, flush, return it sealed."""
        event["provenance"]["prev_hash"] = self._prev_hash
        event["provenance"]["hash"] = event_hash(event)
        self._file.write(canonical_json(event) + b"\n")
        self._file.flush()
        self._prev_hash = event["provenance"]["hash"]
        return event

    def close(self) -> None:
        self._file.close()


class Fanout:
    """Fans out events to WebSocket subscriber queues.

    Threading contract: the session engine runs its own asyncio loop in a
    background thread and calls `publish` from there. Construct `Fanout`
    with that `loop`; `publish` then hops onto it via `call_soon_threadsafe`
    so the queues are only ever touched from their own loop's thread, and
    `publish` itself never blocks the calling thread. With `loop=None`,
    `publish` assumes it is already running on the right thread (e.g. in
    tests, or when called from inside that same loop) and updates the
    queues directly.

    A full subscriber queue never blocks `publish`: the oldest queued item
    is dropped to make room for the new one.
    """

    MAXSIZE = 256

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        self._loop = loop
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.MAXSIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._publish_now, event)
        else:
            self._publish_now(event)

    def _publish_now(self, event: dict) -> None:
        for queue in self._subscribers:
            if queue.full():
                try:
                    queue.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
