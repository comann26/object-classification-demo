import json
import threading
import time

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
    now = {}  # Frame.ts of the frame being processed, and of the first knife

    def script(frame):
        now["ts"] = frame.ts
        dets = [Detection("person", 0.9, PERSON)]
        if frame.ts >= 2.0 - 1e-9:  # knife appears at ts 2.0, not at the start
            now.setdefault("knife", frame.ts)
            dets.append(Detection("knife", 0.5, KNIFE))
        return dets

    s = make_session(tmp_path, quiet_frames(50), detector_script=script)
    published = []
    publish = s.fanout.publish
    s.fanout.publish = lambda e: (published.append((now.get("ts"), e)), publish(e))
    s.run_to_end()
    high = [
        ts
        for ts, e in published
        if e["type"] == "track.updated"
        and e["track"]["class"] == "person"
        and e["links"]
        and e["links"][0]["object_class"] == "knife"
        and e["threat"]["band"] == "high"
    ]
    assert high and high[0] <= now["knife"] + 2.0 + 1e-9
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
    events = _events(s)
    assert [e["type"] for e in events] == ["session.started", "session.ended"]
    assert events[-1]["peak_band"] == "low"


def test_session_ended_carries_peak_band(tmp_path):
    s = make_session(tmp_path, quiet_frames(80), detector_script=_holding_knife)
    s.run_to_end()
    events = _events(s)
    bands = {e["threat"]["band"] for e in events if e["type"] == "track.updated"}
    order = ["low", "medium", "high", "critical"]
    assert events[-1]["peak_band"] == max(bands, key=order.index) != "low"


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
        s.last_client_seen()  # endless source: keep idle auto-stop from firing mid-test
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
    assert last["detail"] == "RuntimeError: boom"  # the log records why (final review #9)


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


def test_active_health_code_adds_poor_image(tmp_path):
    # 5 fps is below runtime.fps_floor (10): fps_low stays active once measured.
    s = make_session(
        tmp_path,
        quiet_frames(15),
        fps=5,
        detector_script=lambda f: [Detection("person", 0.9, PERSON)],
    )
    s.run_to_end()
    events = _events(s)
    assert any(e["type"] == "source.health" and e["code"] == "fps_low" for e in events)
    ups = _person_updates(events)
    assert ups
    poor = [u for u in ups[0]["unknowns"] if u["code"] == "poor_image"]
    assert poor and "fps_low" in poor[0]["detail"]


def test_unattended_object_in_zone_scores_30_not_55(tmp_path):
    knife_in_zone = (0.20, 0.70, 0.30, 0.80)  # bottom-centre (0.25, 0.80) is inside ZONE
    s = make_session(
        tmp_path,
        quiet_frames(40),
        detector_script=lambda f: [Detection("knife", 0.5, knife_in_zone)],
        zone=ZONE,
    )
    s.run_to_end()
    ups = [e for e in _events(s) if e["type"] == "track.updated"]
    assert max(e["threat"]["score"] for e in ups) == 30
    assert all(not e["raw"]["in_zone"] for e in ups)
    rules = {i["rule_id"] for e in ups for i in e["threat"]["evidence"]}
    assert rules == {"unattended"}


def test_stop_flushes_track_ended_before_session_ended(tmp_path):
    s = make_session(tmp_path, quiet_frames(30), detector_script=_holding_knife)
    s.run_to_end()  # the tracks are still live when the source ends
    events = _events(s)
    ended = [e for e in events if e["type"] == "track.ended"]
    person = [e for e in ended if e["class"] == "person"]
    assert person and person[0]["peak_band"] == "high" and person[0]["peak_score"] == 55
    assert person[0]["duration_s"] > 2.0
    assert {e["class"] for e in ended} == {"person", "knife"}
    assert events[-1]["type"] == "session.ended"
    assert all(i < len(events) - 1 for i, e in enumerate(events) if e["type"] == "track.ended")


def test_concurrent_stop_waits_for_first(tmp_path):
    seen, closing = threading.Event(), threading.Event()

    def script(frame):
        s.last_client_seen()  # endless source: keep idle auto-stop from firing mid-test
        seen.set()
        return []

    s = make_session(tmp_path, quiet_frame, detector_script=script)

    def slow_close():
        closing.set()
        time.sleep(0.3)

    s.source.close = slow_close
    s.start()
    assert seen.wait(10)
    first = threading.Thread(target=s.stop, args=("error",))
    first.start()
    assert closing.wait(10)
    s.stop("stopped")  # arrives while the first stop is still releasing the source
    events = _events(s)  # the first stop has finished: session.ended written, log closed
    assert events[-1]["type"] == "session.ended" and events[-1]["reason"] == "error"
    assert [e["type"] for e in events].count("session.ended") == 1
    first.join(10)
