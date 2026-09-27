import numpy as np

from demo.config import ScoringConfig
from demo.contracts import Detection, Frame
from demo.tracker import Tracker, object_eligible, person_eligible

_IMG = np.zeros((48, 64, 3), np.uint8)
_A = (0.40, 0.3, 0.46, 0.8)
_B = (0.48, 0.3, 0.54, 0.8)  # no overlap with _A; bottom-centre 0.08 away


def _frame(i: int, fps: int = 10) -> Frame:
    return Frame(i, i / fps, _IMG)


def test_low_likelihood_object_becomes_track():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=10)
    for i in range(5):
        people, objects = tr.update(_frame(i), [Detection("knife", 0.18, (0.1, 0.1, 0.2, 0.3))])
    assert people == []
    assert len(objects) == 1
    t = objects[0]
    assert t.class_name == "knife" and t.visible and t.detections == 5
    assert object_eligible(t, cfg)


def test_borderline_person_becomes_track():
    # Raw ByteTrack would need 0.45 (activation + 0.1) to start this track.
    tr = Tracker(ScoringConfig(), frame_rate=10)
    for i in range(3):
        people, _ = tr.update(_frame(i + 5), [Detection("person", 0.36, _A)])
    assert len(people) == 1 and people[0].visible and people[0].likelihood == 0.36


def test_person_eligibility_seconds():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=10)
    seen = {}
    for i in range(11):
        people, _ = tr.update(_frame(i), [Detection("person", 0.9, _A)])
        seen[i] = people[0]
    assert seen[9].ts == 0.9 and not person_eligible(seen[9], cfg)
    assert seen[10].ts == 1.0 and person_eligible(seen[10], cfg)
    assert seen[10].hit_ratio_1s == 1.0


def test_hit_ratio_drops_when_unmatched():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=10)
    for i in range(20):
        dets = [Detection("person", 0.9, _A)] if i < 15 else []
        people, _ = tr.update(_frame(i), dets)
    t = people[0]
    assert not t.visible and t.bbox == _A
    assert t.hit_ratio_1s == 0.5 and t.hit_ratio_2s == 0.75
    assert not person_eligible(t, cfg)


def test_object_takes_latest_class():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=10)
    box = (0.1, 0.1, 0.2, 0.3)
    for i in range(4):
        _, objects = tr.update(_frame(i), [Detection("knife" if i < 3 else "gun", 0.5, box)])
    assert [t.class_name for t in objects] == ["gun"]


def test_restart_links_to_lost_track():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=10)
    for i in range(5):
        people, _ = tr.update(_frame(i), [Detection("person", 0.9, _A)])
    old = people[0].track_id
    for i in range(5, 8):
        people, _ = tr.update(_frame(i), [Detection("person", 0.9, _B)])
    new = [t for t in people if t.visible]
    assert len(new) == 1
    assert new[0].track_id != old
    assert new[0].restarted_from == old


def test_far_new_track_is_not_restart():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=10)
    for i in range(5):
        tr.update(_frame(i), [Detection("person", 0.9, _A)])
    for i in range(5, 8):
        people, _ = tr.update(_frame(i), [Detection("person", 0.9, (0.8, 0.3, 0.86, 0.8))])
    assert [t.restarted_from for t in people if t.visible] == [None]


def test_lost_track_ends_once():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=10)
    for i in range(3):
        tr.update(_frame(i), [Detection("person", 0.9, _A)])
    ended = []
    for i in range(3, 30):
        people, _ = tr.update(_frame(i), [])
        ended += tr.ended()
    assert people == []
    assert [t.class_name for t in ended] == ["person"]


def test_history_is_bounded():
    cfg = ScoringConfig()
    tr = Tracker(cfg, frame_rate=30)
    for i in range(60 * 30):
        people, _ = tr.update(_frame(i, 30), [Detection("person", 0.9, _A)])
    hist = tr.history(people[0].track_id)
    assert len(hist) <= 300
    assert hist[-1] == (people[0].ts, _A)
