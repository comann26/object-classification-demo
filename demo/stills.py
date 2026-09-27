"""Per-session still capture: write an annotated JPEG and hash it.

See docs/design.md §4 "Privacy": stills are only saved when `save_stills` is
on, one file per session under `logs/<session_id>/`, and the SHA-256 of the
saved bytes travels in the event that saved it (`TrackUpdated.snapshot`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from demo.contracts import Snapshot


def save_still(logs_dir: Path, session_id: str, event_id: str, image: np.ndarray) -> Snapshot:
    """Write `image` as `<logs_dir>/<session_id>/<event_id>.jpg`; return its Snapshot."""
    ok, buf = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError("failed to encode still")
    data = buf.tobytes()
    path = Path(logs_dir) / session_id / f"{event_id}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return Snapshot(path=f"{session_id}/{event_id}.jpg", sha256=hashlib.sha256(data).hexdigest())
