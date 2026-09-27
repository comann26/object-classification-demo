import pytest

from demo.config import ScoringConfig
from demo.contracts import BBox, Track
from demo.linker import Linker, overlap

PERSON = (0.4, 0.2, 0.6, 0.8)  # w=0.2, h=0.6


def _track(
    track_id: int,
    class_name: str,
    bbox: BBox,
    ts: float,
    visible: bool = True,
    restarted_from: int | None = None,
) -> Track:
    return Track(
        track_id=track_id,
        class_name=class_name,
        bbox=bbox,
        likelihood=0.9,
        first_ts=ts,
        ts=ts,
        detections=1,
        hit_ratio_1s=1.0,
        hit_ratio_2s=1.0,
        visible=visible,
        restarted_from=restarted_from,
    )


def _person(
    track_id: int,
    ts: float,
    bbox: BBox = PERSON,
    visible: bool = True,
    restarted_from: int | None = None,
) -> Track:
    return _track(track_id, "person", bbox, ts, visible, restarted_from)


def _knife(
    track_id: int,
    ts: float,
    bbox: BBox,
    visible: bool = True,
    restarted_from: int | None = None,
) -> Track:
    return _track(track_id, "knife", bbox, ts, visible, restarted_from)


def test_overlap_denominator_is_object_area():
    obj = (0.45, 0.3, 0.55, 0.5)  # fully inside PERSON
    assert overlap(obj, PERSON, 0.15, 0.15) == pytest.approx(1.0)


def test_raised_knife_above_head_links():
    # bottom of the knife sits 10% of the person's height above the box top.
    knife = (0.45, 0.10, 0.55, 0.14)
    ov = overlap(knife, PERSON, 0.15, 0.15)
    assert ov >= 0.30


def test_forms_after_form_s():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)  # fully inside PERSON -> overlap 1.0

    links = linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    assert links == []

    links = linker.update(0.4, [_person(1, 0.4)], [_knife(100, 0.4, knife_box)])
    assert links == []

    links = linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    assert len(links) == 1
    assert links[0].person_id == 1 and links[0].object_id == 100
    assert [e for e, _ in linker.events()] == ["formed"]


def test_largest_overlap_wins():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    # Person 1 fully covers the knife (overlap 1.0); person 2 barely qualifies.
    knife_box = (0.45, 0.3, 0.55, 0.5)
    person2 = (0.30, 0.10, 0.70, 0.90)  # much bigger box, weaker fractional overlap after expand
    # Craft person2 so the knife only just clears min_overlap against it.
    person2 = (0.44, 0.29, 0.56, 0.31)  # thin sliver overlapping knife's top edge only

    for ts in (0.0, 0.5):
        links = linker.update(
            ts,
            [_person(1, ts), _person(2, ts, person2)],
            [_knife(100, ts, knife_box)],
        )
    assert len(links) == 1
    assert links[0].person_id == 1


def test_transfer_needs_full_form_s():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)
    person_a = PERSON
    person_b = (0.44, 0.29, 0.56, 0.51)  # also fully overlapping the knife

    linker.update(0.0, [_person(1, 0.0, person_a)], [_knife(100, 0.0, knife_box)])
    links = linker.update(0.5, [_person(1, 0.5, person_a)], [_knife(100, 0.5, knife_box)])
    assert links[0].person_id == 1
    linker.events()

    # Person 2 (id=2) starts overlapping at ts=1.0.
    linker.update(
        1.0,
        [_person(1, 1.0, person_a), _person(2, 1.0, person_b)],
        [_knife(100, 1.0, knife_box)],
    )
    links = linker.update(
        1.4,
        [_person(1, 1.4, person_a), _person(2, 1.4, person_b)],
        [_knife(100, 1.4, knife_box)],
    )
    assert links[0].person_id == 1  # not yet transferred (0.4s < form_s)

    links = linker.update(
        1.5,
        [_person(1, 1.5, person_a), _person(2, 1.5, person_b)],
        [_knife(100, 1.5, knife_box)],
    )
    assert links[0].person_id == 2  # transferred after a full form_s
    kinds = [e for e, _ in linker.events()]
    assert kinds == ["broken", "formed"]


def test_breaks_when_visible_and_apart():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)
    apart_box = (0.0, 0.0, 0.01, 0.01)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    linker.events()

    linker.update(0.6, [_person(1, 0.6)], [_knife(100, 0.6, apart_box)])
    links = linker.update(1.5, [_person(1, 1.5)], [_knife(100, 1.5, apart_box)])
    assert len(links) == 1  # 0.9s apart < break_s

    links = linker.update(1.6, [_person(1, 1.6)], [_knife(100, 1.6, apart_box)])
    assert links == []
    assert [e for e, _ in linker.events()] == ["broken"]


def test_unattended_after_break():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)
    apart_box = (0.0, 0.0, 0.01, 0.01)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    assert linker.unattended_s(100, 0.5) is None  # currently linked

    linker.update(0.6, [_person(1, 0.6)], [_knife(100, 0.6, apart_box)])
    linker.update(1.6, [_person(1, 1.6)], [_knife(100, 1.6, apart_box)])  # breaks here

    assert linker.unattended_s(100, 3.6) == pytest.approx(2.0)


# Straddles the expanded person's right edge (0.63): 80% of the object's area
# falls inside, so overlap() == 0.8 every frame it is used.
KNIFE_OV_0_8: BBox = (0.59, 0.3, 0.64, 0.5)


def test_fade_holds_link_and_freezes_linked_s():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = KNIFE_OV_0_8

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    links = linker.update(1.5, [_person(1, 1.5)], [_knife(100, 1.5, knife_box)])
    pre = links[0]
    assert pre.linked_s == pytest.approx(1.0)
    assert pre.strength == pytest.approx(0.4)  # mean overlap 0.8 * min(1, 1.0/2.0)

    links = linker.update(3.0, [_person(1, 3.0)], [_knife(100, 3.0, knife_box, visible=False)])
    assert len(links) == 1
    assert links[0].linked_s == pytest.approx(pre.linked_s)
    assert links[0].out_of_view_s == pytest.approx(0.0)

    links = linker.update(4.5, [_person(1, 4.5)], [_knife(100, 4.5, knife_box, visible=False)])
    assert len(links) == 1
    assert links[0].linked_s == pytest.approx(pre.linked_s)
    assert links[0].out_of_view_s == pytest.approx(1.5)
    assert links[0].strength == pytest.approx(pre.strength * 0.5)


def test_resume_on_reappear():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    linker.update(1.0, [_person(1, 1.0)], [_knife(100, 1.0, knife_box)])
    linker.events()

    linker.update(1.2, [_person(1, 1.2)], [_knife(100, 1.2, knife_box, visible=False)])
    links = linker.update(2.0, [_person(1, 2.0)], [_knife(100, 2.0, knife_box, visible=False)])
    assert len(links) == 1  # still held, fade_s=3.0 not exceeded

    links = linker.update(2.5, [_person(1, 2.5)], [_knife(100, 2.5, knife_box, visible=True)])
    assert len(links) == 1
    assert links[0].out_of_view_s is None
    assert links[0].person_id == 1
    assert [e for e, _ in linker.events()] == []  # never broke


def test_break_after_fade():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    linker.events()

    linker.update(1.0, [_person(1, 1.0)], [_knife(100, 1.0, knife_box, visible=False)])
    links = linker.update(4.1, [_person(1, 4.1)], [_knife(100, 4.1, knife_box, visible=False)])
    assert links == []
    assert [e for e, _ in linker.events()] == ["broken"]


def test_strength_formula():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    ov = overlap(KNIFE_OV_0_8, PERSON, cfg.link.expand_side, cfg.link.expand_top)
    assert ov == pytest.approx(0.8)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, KNIFE_OV_0_8)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, KNIFE_OV_0_8)])
    links = linker.update(1.5, [_person(1, 1.5)], [_knife(100, 1.5, KNIFE_OV_0_8)])
    assert links[0].linked_s == pytest.approx(1.0)
    assert links[0].strength == pytest.approx(0.4)  # mean overlap 0.8 * min(1, 1.0/2.0)


def test_links_within_2s_at_8fps_half_hit_ratio():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)
    dt = 1.0 / 8.0
    formed_by = None
    ts = 0.0
    frame = 0
    while ts <= 2.0 + 1e-9:
        visible = frame % 2 == 0  # detected on alternate frames
        links = linker.update(ts, [_person(1, ts)], [_knife(100, ts, knife_box, visible=visible)])
        for kind, link in linker.events():
            if kind == "formed" and link.object_id == 100 and formed_by is None:
                formed_by = ts
        if links and formed_by is None:
            formed_by = ts
        frame += 1
        ts = round(ts + dt, 6)

    assert formed_by is not None
    assert formed_by <= 2.0


def test_reappear_apart_breaks_immediately():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)
    apart_box = (0.0, 0.0, 0.01, 0.01)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    linker.events()

    # Goes out of view still holding the object...
    linker.update(0.6, [_person(1, 0.6)], [_knife(100, 0.6, knife_box, visible=False)])
    # ...then reappears well within fade_s, but not overlapping its holder anymore.
    links = linker.update(1.0, [_person(1, 1.0)], [_knife(100, 1.0, apart_box, visible=True)])

    assert links == []  # broken immediately, no break_s grace period
    assert [e for e, _ in linker.events()] == ["broken"]


def test_overlap_drops_then_invisible_then_reappear_resumes():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)
    apart_box = (0.0, 0.0, 0.01, 0.01)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    linker.events()

    # Overlap drops below min while visible (starts a break_s countdown)...
    linker.update(0.6, [_person(1, 0.6)], [_knife(100, 0.6, apart_box, visible=True)])
    # ...then it goes out of view before break_s (1.0s) elapses...
    linker.update(0.7, [_person(1, 0.7)], [_knife(100, 0.7, apart_box, visible=False)])
    # ...and reappears overlapping its holder again: the stale below_since must not
    # cause a break, and out-of-view time must not have counted toward break_s either.
    links = linker.update(1.0, [_person(1, 1.0)], [_knife(100, 1.0, knife_box, visible=True)])

    assert len(links) == 1
    assert links[0].person_id == 1
    assert links[0].out_of_view_s is None
    assert [e for e, _ in linker.events()] == []  # never broke


def test_person_restart_carries_link():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    links = linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    assert links[0].person_id == 1 and links[0].linked_s == pytest.approx(0.0)
    linker.events()

    # Person 1's track is gone; a new track (2) arrives, restarted from 1.
    links = linker.update(
        1.0,
        [_person(2, 1.0, restarted_from=1)],
        [_knife(100, 1.0, knife_box)],
    )

    assert len(links) == 1
    assert links[0].person_id == 2
    assert links[0].linked_s == pytest.approx(0.5)  # continued, not reset
    assert linker.events() == []  # no broken/formed


def test_object_restart_carries_link():
    cfg = ScoringConfig()
    linker = Linker(cfg)
    knife_box = (0.45, 0.3, 0.55, 0.5)

    linker.update(0.0, [_person(1, 0.0)], [_knife(100, 0.0, knife_box)])
    links = linker.update(0.5, [_person(1, 0.5)], [_knife(100, 0.5, knife_box)])
    assert links[0].object_id == 100
    linker.events()

    # Knife track 100 is gone; a new track (101) arrives, restarted from 100.
    links = linker.update(
        1.0,
        [_person(1, 1.0)],
        [_knife(101, 1.0, knife_box, restarted_from=100)],
    )

    assert len(links) == 1
    assert links[0].object_id == 101
    assert links[0].person_id == 1
    assert links[0].linked_s == pytest.approx(0.5)  # continued, not reset
    assert linker.events() == []  # no broken/formed
