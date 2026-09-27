import hashlib
import json
import time

from demo.events import GENESIS, EventLog, Fanout, canonical_json
from demo.verify_log import verify


def test_canonical_json_sorted_compact_utf8():
    assert canonical_json({"b": 1, "a": "café"}) == '{"a":"café","b":1}'.encode()


def _event(event_type="track.updated", **overrides):
    event = {
        "schema_version": "1.1",
        "event_id": "e1",
        "session_id": "s1",
        "source_id": "src1",
        "type": event_type,
        "ts": "2026-09-26T18:04:11.231Z",
        "provenance": {
            "scorer_id": "v1",
            "config_sha256": "abc",
            "model_sha256": "def",
            "input_size": 640,
        },
    }
    event.update(overrides)
    return event


def test_hash_excludes_own_hash_field(tmp_path):
    log = EventLog(tmp_path / "s.jsonl")
    sealed = log.append(_event())
    log.close()

    check = dict(sealed)
    check["provenance"] = {k: v for k, v in sealed["provenance"].items() if k != "hash"}
    expected = hashlib.sha256(canonical_json(check)).hexdigest()
    assert sealed["provenance"]["hash"] == expected


def test_first_prev_hash_is_genesis(tmp_path):
    log = EventLog(tmp_path / "s.jsonl")
    sealed = log.append(_event())
    log.close()
    assert sealed["provenance"]["prev_hash"] == GENESIS


def test_chain_verifies_ok(tmp_path):
    path = tmp_path / "s.jsonl"
    log = EventLog(path)
    log.append(_event(event_type="session.started"))
    log.append(_event(event_type="session.ended"))
    log.close()

    result = verify(path)
    assert result.ok
    assert result.message == "OK"


def test_verify_detects_edit(tmp_path):
    path = tmp_path / "s.jsonl"
    log = EventLog(path)
    log.append(_event(event_type="session.started"))
    log.append(_event(event_type="session.ended"))
    log.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["ts"] = "2099-01-01T00:00:00.000Z"
    lines[1] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify(path)
    assert not result.ok
    assert result.first_broken_line == 2


def test_verify_detects_deleted_line(tmp_path):
    path = tmp_path / "s.jsonl"
    log = EventLog(path)
    log.append(_event(event_type="session.started"))
    log.append(_event(event_type="track.updated"))
    log.append(_event(event_type="session.ended"))
    log.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify(path)
    assert not result.ok
    assert result.first_broken_line == 2


def test_verify_detects_reordered_lines(tmp_path):
    path = tmp_path / "s.jsonl"
    log = EventLog(path)
    log.append(_event(event_type="session.started"))
    log.append(_event(event_type="track.updated"))
    log.append(_event(event_type="session.ended"))
    log.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify(path)
    assert not result.ok
    assert result.first_broken_line == 2


def test_verify_missing_session_ended_is_truncated(tmp_path):
    path = tmp_path / "s.jsonl"
    log = EventLog(path)
    log.append(_event(event_type="session.started"))
    log.append(_event(event_type="track.updated"))
    log.close()

    result = verify(path)
    assert not result.ok
    assert result.truncated
    assert "truncated or crashed" in result.message


def test_verify_log_partial_last_line(tmp_path):
    path = tmp_path / "s.jsonl"
    log = EventLog(path)
    log.append(_event(event_type="session.started"))
    log.close()

    with path.open("ab") as f:
        f.write(b'{"type": "session.end')  # cut mid-write, no trailing newline

    result = verify(path)
    assert not result.ok
    assert result.truncated


def test_fanout_never_blocks_on_stalled_subscriber():
    fanout = Fanout()
    stalled = fanout.subscribe()

    start = time.perf_counter()
    for i in range(10_000):
        fanout.publish({"i": i})
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0
    assert stalled.qsize() <= 256
