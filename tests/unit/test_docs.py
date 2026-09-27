"""Task 22: docs/setup-guide.md must carry every user-facing message verbatim, and
CLAUDE.md must point at AGENTS.md (docs/design.md §6). Reads the real constants and
launcher files so the docs cannot silently drift from the code.
"""

from __future__ import annotations

import re
from pathlib import Path

from demo.cameras import MESSAGES
from demo.models import OFFLINE_MESSAGE
from demo.setup import NO_GPU_MESSAGE

ROOT = Path(__file__).resolve().parents[2]
ZIP_GUARD = "Extract the zip first, then open the extracted folder."
SETUP_GUIDE = ROOT / "docs" / "setup-guide.md"


def _bat_messages() -> list[str]:
    text = (ROOT / "Start Demo.bat").read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        m = re.match(r"^echo (.+)$", line.strip())
        if m and "%" not in m.group(1) and m.group(1) != ".":
            out.append(m.group(1))
    return out


def _command_messages() -> list[str]:
    text = (ROOT / "Start Demo.command").read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        out.extend(re.findall(r'(?:fail|echo) "([^"$]+)"', line))
    return out


def test_every_camera_message_in_troubleshooting():
    guide = SETUP_GUIDE.read_text(encoding="utf-8")
    for message in MESSAGES.values():
        assert message in guide, message


def test_offline_and_gpu_messages_in_troubleshooting():
    guide = SETUP_GUIDE.read_text(encoding="utf-8")
    assert OFFLINE_MESSAGE in guide
    assert NO_GPU_MESSAGE in guide


def test_zip_guard_in_troubleshooting():
    assert ZIP_GUARD in SETUP_GUIDE.read_text(encoding="utf-8")


def test_every_launcher_message_in_troubleshooting():
    guide = SETUP_GUIDE.read_text(encoding="utf-8")
    messages = _bat_messages() + _command_messages()
    assert messages  # sanity: extraction actually found lines
    for message in messages:
        assert message in guide, message


def test_model_damage_and_checksum_wording_in_troubleshooting():
    guide = SETUP_GUIDE.read_text(encoding="utf-8")
    assert "is missing or damaged. Run setup again." in guide
    assert "failed its checksum. Run setup again." in guide


def test_claude_md_points_to_agents():
    assert (ROOT / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
