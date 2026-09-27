"""Task 22: docs/setup-guide.md must carry every user-facing message verbatim, and
CLAUDE.md must point at AGENTS.md (docs/design.md §6). Reads the real constants and
launcher files so the docs cannot silently drift from the code.
"""

from __future__ import annotations

import re
from pathlib import Path

from demo.cameras import MESSAGES
from demo.contracts import PERSON_WORD_MESSAGE
from demo.models import OFFLINE_MESSAGE
from demo.server import (
    ALREADY_STARTING_MESSAGE,
    CONFIG_DAMAGED_MESSAGE,
    FORBIDDEN_MESSAGE,
    RESTART_MESSAGE,
)
from demo.setup import NO_GPU_MESSAGE

ROOT = Path(__file__).resolve().parents[2]
ZIP_GUARD = "Extract the zip first, then open the extracted folder."
SETUP_GUIDE = ROOT / "docs" / "setup-guide.md"
APP_TSX = ROOT / "web" / "src" / "App.tsx"
THREAT_WORDS_TS = ROOT / "web" / "src" / "lib" / "threatWords.ts"
_PERSON_WORD_TS_PATTERN = (
    r"PERSON_WORDS\.has\(key\)\) \{\s*return \{ words: \[\], error: '([^']+)' \}"
)


def _extract(path: Path, pattern: str) -> str:
    """The first captured group of `pattern` in `path` — fails loudly (not silently) if the
    source has moved or been reworded, so a rename can't quietly stop being checked."""
    text = path.read_text(encoding="utf-8")
    m = re.search(pattern, text)
    assert m, f"could not find {pattern!r} in {path} — did the source move or get reworded?"
    return m.group(1)


def _web_messages() -> list[str]:
    end_block = _extract(APP_TSX, r"const END_MESSAGES[^{]*\{([^}]+)\}")
    end_messages = re.findall(r"\w+: '([^']+)'", end_block)
    assert len(end_messages) == 3, end_messages  # error, camera_lost, idle
    return [
        *end_messages,
        _extract(APP_TSX, r'<p className="font-heading text-xl">([^<]+)</p>'),
        _extract(THREAT_WORDS_TS, _PERSON_WORD_TS_PATTERN),
    ]


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


def test_server_messages_in_troubleshooting():
    guide = SETUP_GUIDE.read_text(encoding="utf-8")
    assert FORBIDDEN_MESSAGE in guide
    assert ALREADY_STARTING_MESSAGE in guide
    assert RESTART_MESSAGE in guide
    assert CONFIG_DAMAGED_MESSAGE in guide
    assert "run/demo.lock" in guide  # stale-lock escape hatch (final review #5)


def test_web_messages_in_troubleshooting():
    guide = SETUP_GUIDE.read_text(encoding="utf-8")
    for message in _web_messages():
        assert message in guide, message


def test_person_word_message_matches_between_python_and_web():
    # demo/contracts.py and web/src/lib/threatWords.ts each reject person words on their own
    # side (server validation vs. client-side check); they must say exactly the same thing.
    assert PERSON_WORD_MESSAGE == _extract(THREAT_WORDS_TS, _PERSON_WORD_TS_PATTERN)


def test_claude_md_points_to_agents():
    assert (ROOT / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
