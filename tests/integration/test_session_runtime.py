"""Task 10: automatic step-down, idle auto-stop, and per-session stills.

See docs/design.md §3 "Model, device, input size" (step-down order), §1
"Tab closed" (idle 30 s) and §4 "Privacy" (stills).
"""

import hashlib
import json
from pathlib import Path

from demo.config import ScoringConfig
from demo.contracts import Detection, EventAdapter
from demo.stepdown import StepDown
from demo.testing import make_session, quiet_frames

PERSON = (0.30, 0.20, 0.60, 0.90)
KNIFE = (0.42, 0.40, 0.52, 0.50)


def _holding_knife(frame):
    return [Detection("person", 0.9, PERSON), Detection("knife", 0.5, KNIFE)]


def _events(session) -> list[dict]:
    lines = session.log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    for e in events:
        EventAdapter.validate_python(e)  # every line matches the wire schema
    return events


# -- StepDown (pure logic) -------------------------------------------------


def test_stepdown_order():
    cfg = ScoringConfig()  # fps_floor=10, stepdown_after_s=5.0
    sd = StepDown(cfg, large_available=True)
    assert sd.observe(0.0, 5.0) is None
    assert sd.observe(4.9, 5.0) is None
    assert sd.observe(5.0, 5.0) == ("small", 640)
    assert sd.observe(9.9, 5.0) is None
    assert sd.observe(10.0, 5.0) == ("small", 480)
    assert sd.observe(14.9, 5.0) is None
    assert sd.observe(15.0, 5.0) == ("small", 320)
    assert sd.observe(20.0, 5.0) is None  # no more steps


def test_stepdown_disabled_for_non_realtime(tmp_path):
    s = make_session(tmp_path, quiet_frames(40), fps=5)  # SyntheticSource: realtime=False
    s.run_to_end()
    events = _events(s)
    assert not any(e["type"] == "pipeline.changed" for e in events)
    assert all(e["provenance"]["input_size"] == 640 for e in events)


def test_pipeline_changed_event_emitted(tmp_path):
    s = make_session(tmp_path, quiet_frames(40), fps=5, realtime=True)
    s.run_to_end()
    events = _events(s)
    changed = [e for e in events if e["type"] == "pipeline.changed"]
    assert changed and changed[0]["reason"] == "fps_below_floor"
    assert changed[0]["model"] == "small" and changed[0]["input_size"] == 480
    after = events[events.index(changed[0]) + 1 :]
    assert after and all(e["provenance"]["input_size"] == 480 for e in after)
    assert s.health()["input_size"] == 480 and s.health()["model"] == "small"


# -- Idle auto-stop ----------------------------------------------------------


def test_idle_stop_after_30s(tmp_path):
    # fps=1 so Frame.ts steps 1 s per frame: 40 frames cross the 30 s idle_stop_s
    # default quickly, with no wall-clock wait (run_to_end has no sleeps).
    s = make_session(tmp_path, quiet_frames(40), fps=1)
    s.run_to_end()  # last_client_seen is never called: idle counts from session start
    last = _events(s)[-1]
    assert last["type"] == "session.ended" and last["reason"] == "idle"


# -- Stills --------------------------------------------------------------


def test_stills_off_by_default(tmp_path):
    s = make_session(tmp_path, quiet_frames(30), detector_script=_holding_knife)
    s.run_to_end()
    updates = [e for e in _events(s) if e["type"] == "track.updated"]
    assert updates and all(e.get("snapshot") is None for e in updates)
    assert not (Path(tmp_path) / "logs" / s.id).exists()


def test_still_saved_with_hash_on_high(tmp_path):
    s = make_session(tmp_path, quiet_frames(30), detector_script=_holding_knife, save_stills=True)
    s.run_to_end()
    snaps = [
        e["snapshot"] for e in _events(s) if e["type"] == "track.updated" and e.get("snapshot")
    ]
    assert snaps
    snap = snaps[0]
    still_path = Path(tmp_path) / "logs" / snap["path"]
    assert still_path.exists()
    assert hashlib.sha256(still_path.read_bytes()).hexdigest() == snap["sha256"]
