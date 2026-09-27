import random

from demo.config import ScoringConfig
from demo.contracts import BBox, Link, Track
from demo.scorer import RULES, BandTracker, Inputs, band_of, score

CFG = ScoringConfig()


def _track(
    track_id: int = 1, class_name: str = "person", bbox: BBox = (0.3, 0.2, 0.5, 0.9)
) -> Track:
    return Track(
        track_id=track_id,
        class_name=class_name,
        bbox=bbox,
        likelihood=0.9,
        first_ts=0.0,
        ts=1.0,
        detections=5,
        hit_ratio_1s=1.0,
        hit_ratio_2s=1.0,
        visible=True,
        restarted_from=None,
    )


def _link(
    person_id: int = 1,
    object_id: int = 12,
    object_class: str = "knife",
    linked_s: float = 1.8,
    strength: float = 0.62,
    object_likelihood: float = 0.55,
) -> Link:
    return Link(
        person_id=person_id,
        object_id=object_id,
        object_class=object_class,
        object_likelihood=object_likelihood,
        linked_s=linked_s,
        strength=strength,
        out_of_view_s=None,
    )


def _base_kwargs() -> dict:
    return dict(
        track=_track(),
        links=[],
        motion_enabled=False,
        heading=None,
        speed=None,
        approach=None,
        in_zone=False,
        left_zone=False,
        dwell_s=0.0,
        unattended_s=None,
        detector_conf=0.9,
        track_stability=0.9,
        image_quality=0.9,
        unknowns=[],
    )


def _inputs(**overrides) -> Inputs:
    kwargs = _base_kwargs()
    kwargs.update(overrides)
    return Inputs(**kwargs)


def test_single_link_scores_55_high():
    inp = _inputs(links=[_link()])
    a = score(inp, CFG)
    assert a.score == 55
    assert a.raw_band == "high"
    assert [e.contribution for e in a.evidence] == [55]
    assert a.summary == "Person 1 is holding a knife."


def test_two_links_clamped_to_100_with_clamp_item():
    inp = _inputs(links=[_link(object_class="knife"), _link(object_id=13, object_class="gun")])
    a = score(inp, CFG)
    assert [e.contribution for e in a.evidence] == [55, 55, -10]
    assert a.evidence[-1].rule_id == "clamp"
    assert a.score == 100
    assert sum(e.contribution for e in a.evidence) == a.score
    assert "knife and gun" in a.summary


def test_lone_contradictory_clamps_to_zero():
    inp = _inputs(left_zone=True)
    a = score(inp, CFG)
    assert [e.contribution for e in a.evidence] == [-5, 5]
    assert a.evidence[-1].rule_id == "clamp"
    assert a.score == 0


def test_contributions_are_ints_and_sum_to_score():
    rng = random.Random(42)
    for _ in range(200):
        n_links = rng.randint(0, 3)
        links = [_link(object_id=100 + i, linked_s=rng.uniform(0, 5)) for i in range(n_links)]
        is_person = n_links > 0 or rng.random() < 0.5
        inp = _inputs(
            track=_track(class_name="person" if is_person else "knife"),
            links=links,
            motion_enabled=rng.random() < 0.5,
            speed=rng.uniform(0, 3),
            approach=rng.uniform(-0.3, 0.3),
            in_zone=rng.random() < 0.5,
            left_zone=rng.random() < 0.5,
            dwell_s=rng.uniform(0, 20),
            unattended_s=rng.uniform(0, 5) if not is_person else None,
        )
        a = score(inp, CFG)
        for item in a.evidence:
            assert isinstance(item.contribution, int)
        assert sum(item.contribution for item in a.evidence) == a.score
        assert 0 <= a.score <= 100


def test_approach_linear():
    a1 = score(_inputs(motion_enabled=True, approach=0.08), CFG)
    approach_items = [e for e in a1.evidence if e.rule_id == "approach"]
    assert [e.contribution for e in approach_items] == [3]

    a2 = score(_inputs(motion_enabled=True, approach=0.25), CFG)
    approach_items2 = [e for e in a2.evidence if e.rule_id == "approach"]
    assert [e.contribution for e in approach_items2] == [20]
    assert CFG.weights.motion_cap == 20


def test_running_linear():
    a = score(_inputs(motion_enabled=True, speed=1.5), CFG)
    running_items = [e for e in a.evidence if e.rule_id == "running"]
    assert [e.contribution for e in running_items] == [10]


def test_motion_suspended_gives_no_motion_items():
    inp = _inputs(motion_enabled=False, approach=0.5, speed=5.0)
    a = score(inp, CFG)
    rule_ids = {e.rule_id for e in a.evidence}
    assert "approach" not in rule_ids
    assert "running" not in rule_ids
    assert "moving_away" not in rule_ids


def test_loiter_needs_dwell_10s():
    below = score(_inputs(in_zone=True, dwell_s=9.9), CFG)
    assert "loiter" not in {e.rule_id for e in below.evidence}

    at = score(_inputs(in_zone=True, dwell_s=10.0), CFG)
    loiter_items = [e for e in at.evidence if e.rule_id == "loiter"]
    assert [e.contribution for e in loiter_items] == [15]


def test_unattended_after_2s():
    obj_track = _track(class_name="knife")
    below = score(_inputs(track=obj_track, unattended_s=1.9), CFG)
    assert "unattended" not in {e.rule_id for e in below.evidence}

    at = score(_inputs(track=obj_track, unattended_s=2.0), CFG)
    unattended_items = [e for e in at.evidence if e.rule_id == "unattended"]
    assert [e.contribution for e in unattended_items] == [30]
    assert at.summary == "Unattended knife (object 1)."


def test_band_hysteresis_sequence():
    tracker = BandTracker(5)
    bands = [tracker.update(1, s) for s in (49, 55, 52, 44)]
    assert bands == ["medium", "high", "high", "medium"]


def test_band_tracker_forget_resets_to_raw():
    tracker = BandTracker(5)
    assert tracker.update(1, 55) == "high"
    tracker.forget(1)
    assert tracker.update(1, 44) == "medium"


def test_confidence_mean():
    inp = _inputs(detector_conf=0.91, track_stability=0.8, image_quality=0.7)
    a = score(inp, CFG)
    assert a.confidence.score == 0.80
    assert a.confidence.dimensions.detector == 0.91
    assert a.confidence.dimensions.track_stability == 0.8
    assert a.confidence.dimensions.image_quality == 0.7


def test_templates_render_for_every_rule():
    scenarios = {
        "threat_object_link": _inputs(links=[_link()]),
        "unattended": _inputs(track=_track(class_name="knife"), unattended_s=3.0),
        "in_zone": _inputs(in_zone=True),
        "loiter": _inputs(in_zone=True, dwell_s=15.0),
        "approach": _inputs(motion_enabled=True, approach=0.08),
        "running": _inputs(motion_enabled=True, speed=1.5),
        "moving_away": _inputs(motion_enabled=True, approach=-0.06),
        "leaving_zone": _inputs(left_zone=True),
        "clamp": _inputs(links=[_link(), _link(object_id=13, object_class="gun")]),
    }
    assert set(scenarios) == set(RULES)

    for rule_id, inp in scenarios.items():
        a = score(inp, CFG)
        items = [e for e in a.evidence if e.rule_id == rule_id]
        assert items, f"rule {rule_id} did not fire"
        assert items[0].text
        assert items[0].rule_version == 1

    link_evidence = score(_inputs(links=[_link()]), CFG).evidence
    link_item = next(e for e in link_evidence if e.rule_id == "threat_object_link")
    assert link_item.text == "Holding a knife for 1.8 s (needs 0.5 s): +55"

    approach_evidence = score(_inputs(motion_enabled=True, approach=0.08), CFG).evidence
    approach_item = next(e for e in approach_evidence if e.rule_id == "approach")
    assert approach_item.text == "Moving closer: box grew 8% wider in 2 s (needs 5%): +3"


def test_example_event_matches_spec():
    """Reproduces docs/design.md §2's track.updated example."""
    inp = _inputs(
        track=_track(track_id=7, class_name="person"),
        links=[_link(person_id=7, object_id=12, object_class="knife", linked_s=1.8, strength=0.62)],
        motion_enabled=True,
        approach=0.08,
        detector_conf=0.91,
        track_stability=0.8,
        image_quality=0.7,
    )
    a = score(inp, CFG)

    assert [e.contribution for e in a.evidence] == [55, 3]
    assert a.score == 58
    assert a.raw_band == "high"
    assert a.confidence.score == 0.80
    assert a.summary == "Person 7 is holding a knife and moving closer."
    assert a.evidence[0].text == "Holding a knife for 1.8 s (needs 0.5 s): +55"
    assert a.evidence[1].text == "Moving closer: box grew 8% wider in 2 s (needs 5%): +3"


def test_band_of_bounds():
    assert band_of(0) == "low"
    assert band_of(24) == "low"
    assert band_of(25) == "medium"
    assert band_of(49) == "medium"
    assert band_of(50) == "high"
    assert band_of(74) == "high"
    assert band_of(75) == "critical"
    assert band_of(100) == "critical"


def test_no_signal_scores_zero():
    a = score(_inputs(), CFG)
    assert a.score == 0
    assert a.evidence == []
