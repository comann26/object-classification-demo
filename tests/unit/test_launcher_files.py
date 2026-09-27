"""Task 16: double-click launchers, pinned uv and the torch-variant lock (docs/design.md §4)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BAT = ROOT / "Start Demo.bat"
COMMAND = ROOT / "Start Demo.command"
GUARD = "Extract the zip first, then open the extracted folder."


@pytest.mark.parametrize(("path", "sha_check"), [(BAT, "certutil"), (COMMAND, "shasum -a 256")])
def test_launchers_have_zip_guard_and_pinned_uv(path, sha_check):
    text = path.read_text(encoding="utf-8")
    assert GUARD in text
    assert "UV_PYTHON_PREFERENCE=only-managed" in text
    assert "UV_NO_MODIFY_PATH=1" in text
    assert sha_check in text
    assert "uv.version" in text  # version + hashes come from the committed pin file


def test_uv_version_pins_every_platform():
    pins = dict(
        line.split("=", 1) for line in (ROOT / "bin" / "uv.version").read_text().split() if line
    )
    assert set(pins) == {
        "DEMO_UV_VERSION",
        "DEMO_UV_SHA256_WINDOWS_X86_64",
        "DEMO_UV_SHA256_MACOS_AARCH64",
        "DEMO_UV_SHA256_MACOS_X86_64",
    }
    for key, value in pins.items():
        if key.startswith("DEMO_UV_SHA256"):
            assert len(value) == 64 and int(value, 16) >= 0


def test_command_file_is_executable_in_git():
    out = subprocess.run(
        ["git", "ls-files", "-s", "Start Demo.command"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out.startswith("100755")


@pytest.mark.skipif(sys.platform != "win32", reason="runs the .bat")
def test_bat_refuses_to_run_from_temp(tmp_path):
    # pytest's tmp_path is under %TEMP% (…\AppData\Local\Temp\…), like a zip opened in Explorer.
    folder = tmp_path / "demo.zip" / "demo"
    folder.mkdir(parents=True)
    shutil.copy(BAT, folder)
    r = subprocess.run(
        ["cmd", "/c", str(folder / BAT.name)],
        input="\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert GUARD in r.stdout
    assert r.returncode != 0
    assert not (folder / "bin").exists()  # refused before downloading anything


def _uv() -> str:
    local = ROOT / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")
    return str(local) if local.exists() else (shutil.which("uv") or pytest.skip("no uv"))


def test_lock_resolves_all_variants():
    r = subprocess.run([_uv(), "lock", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
