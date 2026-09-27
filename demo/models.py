"""Pinned model files: manifest, checksum verify, one-time download, model choice.

See docs/design.md §3 "Model, device, input size" and §4 "Model and offline".
`models/manifest.json` is a list of `{name, url, sha256, size}`; the files
themselves live next to it in `models/` (git-ignored). No torch/ultralytics
imports here: the launcher uses this before the heavy stack exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

SMALL = "yolov8s-worldv2.pt"
LARGE = "yolov8l-worldv2.pt"
CLIP = "ViT-B-32.pt"  # the openai CLIP ViT-B/32 weights YOLO-World's set_classes uses
MODEL_FILES = {"small": SMALL, "large": LARGE}

OFFLINE_MESSAGE = "First-time setup needs internet once."
DAMAGED_MESSAGE = "Model file {file} is missing or damaged. Run setup again."


class SetupError(RuntimeError):
    """A plain-English setup problem, shown to the user as-is (never a stack trace).

    `code`/`message` mirror `CameraError`; the server maps it to 503 `{code, message}`.
    """

    code = "setup"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def models_dir(root: Path) -> Path:
    return Path(root) / "models"


def manifest(root: Path) -> dict[str, dict]:
    entries = json.loads((models_dir(root) / "manifest.json").read_text(encoding="utf-8"))
    return {e["name"]: e for e in entries}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ok(path: Path, entry: dict) -> bool:
    try:
        return path.stat().st_size == entry["size"] and sha256(path) == entry["sha256"]
    except OSError:
        return False


def verify(root: Path, names: list[str] | None = None) -> dict[str, bool]:
    """name -> file present with the pinned size and SHA-256 (all manifest files by default)."""
    entries = manifest(root)
    return {n: _ok(models_dir(root) / n, entries[n]) for n in (names or entries)}


def ensure(root: Path, names: list[str]) -> None:
    """Download each missing/corrupt file to `<name>.part`, check it, then rename it into place."""
    entries = manifest(root)
    for name in names:
        entry, dest = entries[name], models_dir(root) / name
        if _ok(dest, entry):
            continue
        part = dest.with_name(name + ".part")
        try:
            with urllib.request.urlopen(entry["url"], timeout=30) as resp, open(part, "wb") as f:
                shutil.copyfileobj(resp, f, 1 << 20)
        except (urllib.error.URLError, OSError) as exc:  # URLError covers DNS/refused/offline
            part.unlink(missing_ok=True)
            raise SetupError(OFFLINE_MESSAGE) from exc
        if not _ok(part, entry):
            part.unlink(missing_ok=True)
            raise SetupError(f"Downloaded {name} failed its checksum. Run setup again.")
        os.replace(part, dest)


def select_model(cfg_model: str, device: str) -> str:
    """`auto` -> large on cuda/mps, small on cpu; `small`/`large` are honored as given."""
    if cfg_model != "auto":
        return cfg_model
    return "large" if device in ("cuda", "mps") else "small"
