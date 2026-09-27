import pytest
from pydantic import TypeAdapter, ValidationError

from demo.contracts import (
    Confidence,
    ConfidenceDimensions,
    Event,
    PipelineChanged,
    Provenance,
    Raw,
    SessionEnded,
    SessionRequest,
    SessionStarted,
    SourceHealth,
    Threat,
    TrackEnded,
    TrackOut,
    TrackUpdated,
    ZoneRequest,
)


def _provenance(**overrides):
    data = dict(
        scorer_id="rules-v1",
        config_sha256="c" * 64,
        model_sha256="m" * 64,
        input_size=640,
        prev_hash="0" * 64,
        hash="h" * 64,
    )
    data.update(overrides)
    return Provenance(**data)


def _envelope(event_type, **payload):
    return dict(
        schema_version="1.0",
        event_id="11111111-1111-1111-1111-111111111111",
        session_id="22222222-2222-2222-2222-222222222222",
        source_id="cam-1",
        ts="2026-09-26T18:04:11.231Z",
        type=event_type,
        provenance=_provenance(),
        **payload,
    )


def test_threat_words_normalised():
    r = SessionRequest(threat_objects=["Knife", " knife ", "", "\U0001f52a"], source="cam-1")
    assert r.threat_objects == ["knife", "\U0001f52a"]


@pytest.mark.parametrize(
    "words",
    [[], ["a" * 51], ["a", "b", "c", "d", "e", "f"], ["person"], ["Women"], ["kids"]],
)
def test_threat_words_rejected(words):
    with pytest.raises(ValidationError):
        SessionRequest(threat_objects=words, source="cam-1")


def test_person_word_message():
    message = "People are always tracked — type an object instead."
    with pytest.raises(ValidationError, match=message):
        SessionRequest(threat_objects=["person"], source="cam-1")


@pytest.mark.parametrize(
    "zone",
    [
        [(0, 0), (1, 0)],
        [(0, 0)] * 21,
        [(0, 0), (1.2, 0), (1, 1)],
        [(0, 0), (1, 1), (1, 0), (0, 1)],
    ],
)
def test_zone_rejected(zone):
    with pytest.raises(ValidationError):
        ZoneRequest(zone=zone)


def test_zone_none_clears():
    assert ZoneRequest(zone=None).zone is None


def test_event_union_roundtrip():
    events = [
        SessionStarted(
            **_envelope(
                "session.started",
                threat_objects=["knife"],
                zone=None,
                source="cam-1",
                camera_name="Webcam",
                device="cpu",
                model="yolov8s-worldv2",
                model_sha256="a" * 64,
                input_size=640,
                save_stills=False,
                config={},
                app_version="0.1.0",
            )
        ),
        PipelineChanged(
            **_envelope(
                "pipeline.changed",
                model="yolov8s-worldv2",
                model_sha256="a" * 64,
                input_size=480,
                reason="fps_below_floor",
            )
        ),
        TrackUpdated(
            **_envelope(
                "track.updated",
                track=TrackOut(
                    track_id=7,
                    **{"class": "person"},
                    bbox=(0.31, 0.22, 0.48, 0.91),
                    likelihood=0.91,
                    camera_mode="fixed",
                ),
                links=[],
                summary="Person 7 is idle.",
                threat=Threat(score=0, band="low", evidence=[]),
                confidence=Confidence(
                    score=0.8,
                    dimensions=ConfidenceDimensions(
                        detector=0.91, track_stability=0.8, image_quality=0.7
                    ),
                ),
                unknowns=[],
                raw=Raw(in_zone=False, dwell_s=0, approach=0.0, truncated=False),
            )
        ),
        TrackEnded(
            **_envelope(
                "track.ended",
                track_id=7,
                **{"class": "person"},
                duration_s=12.5,
                peak_score=58,
                peak_band="high",
            )
        ),
        SourceHealth(
            **_envelope("source.health", code="fps_low", value=4.2, detail="fps below floor")
        ),
        SessionEnded(**_envelope("session.ended", reason="stopped", detail=None)),
    ]

    adapter = TypeAdapter(Event)
    for event in events:
        dumped = event.model_dump_json(by_alias=True)
        parsed = adapter.validate_json(dumped)
        assert type(parsed) is type(event)
        assert parsed == event
