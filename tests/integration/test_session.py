import json
import threading

from demo.config import ScoringConfig, config_sha256
from demo.contracts import Detection, EventAdapter
from demo.testing import make_session, quiet_frame, quiet_frames
from demo.verify_log import verify

PERSON = (0.30, 0.20, 0.60, 0.90)
KNIFE = (0.42, 0.40, 0.52, 0.50)
# Left-bottom zone that contains PERSON's bottom-centre (0.45, 0.90).
ZONE = [(0.0, 0.5), (0.7, 0.5), (0.7, 1.0), (0.0, 1.0)]


def _holding_knife(frame):
    return [Detection("person", 0.9, PERSON), Detection("knife", 0.5, KNIFE)]


def _events(session) -> list[dict]:
    lines = session.log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    for e in events:
        EventAdapter.validate_python(e)  # every line matches the wire schema
    return events


def _person_updates(events):
    return [e for e in events if e["type"] == "track.updated" and e["track"]["class"] == "person"]


def test_first_line_session_started_with_config_hash(tmp_path):
    s = make_session(tmp_path, quiet_frames(5))
    s.run_to_end()
    first = _events(s)[0]
    cfg = ScoringConfig()
    assert first["type"] == "session.started"
    assert first["config"] == cfg.model_dump(mode="json")
    assert first["provenance"]["config_sha256"] == config_sha256(cfg)
    assert first["provenance"]["scorer_id"] == "rules-v1"
    assert first["threat_objects"] == ["knife"] and first["device"] == "cpu"
    assert first["provenance"]["prev_hash"] == "0" * 64


def test_knife_held_emits_link_and_high(tmp_path):
    s = make_session(tmp_path, quiet_frames(30), detector_script=_holding_knife)
    s.run_to_end()
    hits = [
        e
        for e in _person_updates(_events(s))
        if e["links"] and e["links"][0]["object_class"] == "knife" and e["threat"]["band"] == "high"
    ]
    assert hits
    # Event ts is wall clock; Frame.ts of the event = form time (0 + form_s 0.5) + linked_s.
    assert 0.5 + hits[0]["links"][0]["linked_s"] <= 2.0 + 1e-6
    assert s.detector.classes == ["person", "knife"]


def test_heartbeat_every_2s_above_low(tmp_path):
    s = make_session(tmp_path, quiet_frames(80), detector_script=_holding_knife)
    s.run_to_end()
    linked = [e["links"][0]["linked_s"] for e in _person_updates(_events(s)) if e["links"]]
    assert len(linked) >= 3
    gaps = [b - a for a, b in zip(linked, linked[1:])]
    assert all(abs(g - 2.0) < 1e-6 for g in gaps), gaps


def test_no_events_for_empty_scene(tmp_path):
    s = make_session(tmp_path, quiet_frames(40))
    s.run_to_end()
    assert [e["type"] for e in _events(s)] == ["session.started", "session.ended"]


def test_zone_dwell_and_loiter(tmp_path):
    s = make_session(
        tmp_path,
        quiet_frames(111),  # ts 0.0 .. 11.0
        detector_script=lambda f: [Detection("person", 0.9, PERSON)],
        zone=ZONE,
    )
    s.run_to_end()
    ups = _person_updates(_events(s))
    assert ups and all(e["raw"]["in_zone"] for e in ups)
    loiter = [e for e in ups if any(i["rule_id"] == "loiter" for i in e["threat"]["evidence"])]
    assert loiter and loiter[0]["raw"]["dwell_s"] >= 10.0


def test_stop_releases_source_and_writes_stopped(tmp_path):
    seen = threading.Event()

    def script(frame):
        if frame.index >= 3:
            seen.set()
        return [Detection("person", 0.9, PERSON)]

    s = make_session(tmp_path, quiet_frame, detector_script=script)  # endless source
    closed = []
    s.source.close = lambda: closed.append(True)
    s.start()
    assert seen.wait(10)
    assert s.health()["status"] == "running"
    assert set(s.health()) == {
        "status",
        "session_id",
        "fps",
        "camera",
        "model",
        "input_size",
        "device",
    }
    assert s.latest_jpeg()[:2] == b"\xff\xd8"
    s.stop("stopped")
    s.stop("stopped")  # idempotent
    events = _events(s)
    assert events[-1]["type"] == "session.ended" and events[-1]["reason"] == "stopped"
    assert [e["type"] for e in events].count("session.ended") == 1
    assert closed == [True]
    assert s.health()["status"] == "stopped"


def test_exception_in_stage_ends_with_error(tmp_path):
    def script(frame):
        if frame.index == 5:
            raise RuntimeError("boom")
        return []

    s = make_session(tmp_path, quiet_frames(20), detector_script=script)
    s.run_to_end()
    last = _events(s)[-1]
    assert last["type"] == "session.ended" and last["reason"] == "error"


def test_log_verifies_ok(tmp_path):
    s = make_session(tmp_path, quiet_frames(30), detector_script=_holding_knife)
    s.run_to_end()
    assert verify(s.log_path).message == "OK"


def test_source_lost_ends_camera_lost(tmp_path):
    s = make_session(tmp_path, quiet_frames(5))
    s.source.realtime = True
    s.run_to_end()
    last = _events(s)[-1]
    assert last["type"] == "session.ended" and last["reason"] == "camera_lost"
