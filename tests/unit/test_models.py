"""Task 15: pinned model manifest, verify/ensure and model selection (docs/design.md §4)."""

import hashlib
import json
import urllib.error
from pathlib import Path

import pytest

from demo import models
from demo.models import SetupError, ensure, select_model, verify


def _root(tmp_path: Path, payload: bytes, url: str = "https://example.invalid/w.pt") -> Path:
    (tmp_path / "models").mkdir(parents=True)
    entry = {
        "name": "w.pt",
        "url": url,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    (tmp_path / "models" / "manifest.json").write_text(json.dumps([entry]), encoding="utf-8")
    return tmp_path


def test_verify_detects_corrupt_file(tmp_path):
    root = _root(tmp_path, b"good weights")
    assert verify(root) == {"w.pt": False}  # missing
    (root / "models" / "w.pt").write_bytes(b"bad weights!")  # same size, wrong hash
    assert verify(root) == {"w.pt": False}
    (root / "models" / "w.pt").write_bytes(b"good weights")
    assert verify(root) == {"w.pt": True}


def test_ensure_offline_message(tmp_path, monkeypatch):
    root = _root(tmp_path, b"good weights")

    def no_network(*a, **k):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(models.urllib.request, "urlopen", no_network)
    with pytest.raises(SetupError, match=r"^First-time setup needs internet once\.$"):
        ensure(root, ["w.pt"])
    assert list((root / "models").iterdir()) == [root / "models" / "manifest.json"]


def test_ensure_downloads_verifies_and_renames(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"good weights")
    root = _root(tmp_path / "demo", b"good weights", url=src.as_uri())
    ensure(root, ["w.pt"])
    assert (root / "models" / "w.pt").read_bytes() == b"good weights"
    assert not (root / "models" / "w.pt.part").exists()
    ensure(root, ["w.pt"])  # already valid: no-op


def test_ensure_rejects_checksum_mismatch(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"tampered!!!!")
    root = _root(tmp_path / "demo", b"good weights", url=src.as_uri())
    with pytest.raises(SetupError, match="checksum"):
        ensure(root, ["w.pt"])
    assert not (root / "models" / "w.pt").exists()
    assert not (root / "models" / "w.pt.part").exists()


def test_select_model():
    assert select_model("auto", "cpu") == "small"
    assert select_model("auto", "cuda") == "large"
    assert select_model("auto", "mps") == "large"
    assert select_model("small", "cuda") == "small"
    assert select_model("large", "cpu") == "large"


def test_committed_manifest_pins_all_three_files():
    entries = models.manifest(Path(__file__).resolve().parents[2])
    assert set(entries) == {models.SMALL, models.LARGE, models.CLIP}
    for e in entries.values():
        assert e["url"].startswith("https://") and len(e["sha256"]) == 64 and e["size"] > 0
