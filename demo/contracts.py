"""Wire and internal data contracts for the demo pipeline.

Internal types (used inside the process, between stages) are plain frozen
dataclasses — `Frame` carries a numpy array, which Pydantic does not validate
well. Wire types (HTTP requests, events) are Pydantic v2 models.

Field names and enums follow `docs/design.md` §2 (Data format) verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

SCHEMA_VERSION = "1.1"

# Normalized (x1, y1, x2, y2).
BBox = tuple[float, float, float, float]

# Normalized (x, y).
_Point = tuple[float, float]

Band = Literal["low", "medium", "high", "critical"]

UnknownCode = Literal[
    "object_out_of_view",
    "track_restarted",
    "poor_image",
    "camera_moving",
    "truncated",
]

Direction = Literal[
    "up", "up-right", "right", "down-right",
    "down", "down-left", "left", "up-left",
]

PERSON_WORDS: frozenset[str] = frozenset(
    {
        "person", "persons", "people",
        "human", "humans",
        "man", "men",
        "woman", "women",
        "child", "children",
        "kid", "kids",
        "boy", "boys",
        "girl", "girls",
    }
)

_MAX_THREAT_WORDS = 5
_MAX_WORD_LEN = 50
_MIN_ZONE_POINTS = 3
_MAX_ZONE_POINTS = 20


# --------------------------------------------------------------------------
# Internal (in-process) types — plain frozen dataclasses.
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Frame:
    """A single captured frame."""

    index: int
    ts: float
    image: np.ndarray

    @property
    def height(self) -> int:
        return int(self.image.shape[0])

    @property
    def width(self) -> int:
        return int(self.image.shape[1])


@dataclass(frozen=True, slots=True)
class Detection:
    class_name: str
    likelihood: float
    bbox: BBox


@dataclass(frozen=True, slots=True)
class Track:
    track_id: int
    class_name: str
    bbox: BBox
    likelihood: float
    first_ts: float
    ts: float
    detections: int
    hit_ratio_1s: float
    hit_ratio_2s: float
    visible: bool
    restarted_from: int | None


@dataclass(frozen=True, slots=True)
class Link:
    person_id: int
    object_id: int
    object_class: str
    object_likelihood: float
    linked_s: float
    strength: float
    out_of_view_s: float | None


# --------------------------------------------------------------------------
# Wire requests
# --------------------------------------------------------------------------


class SessionRequest(BaseModel):
    threat_objects: list[str] = Field(
        description=(
            "1-5 object class words to treat as threats, besides people "
            "(people are always tracked)."
        )
    )
    source: str = Field(description="A camera id from GET /cameras.")
    save_stills: bool = False

    @field_validator("threat_objects")
    @classmethod
    def _normalise_threat_objects(cls, value: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for raw in value:
            word = raw.strip()
            if not word:
                continue
            if len(word) > _MAX_WORD_LEN:
                raise ValueError(
                    f"threat object word too long (max {_MAX_WORD_LEN} chars): {word!r}"
                )
            key = word.lower()
            if key in PERSON_WORDS:
                raise ValueError("People are always tracked — type an object instead.")
            seen.setdefault(key, None)
        words = list(seen.keys())
        if not 1 <= len(words) <= _MAX_THREAT_WORDS:
            raise ValueError(
                f"threat_objects must have 1-{_MAX_THREAT_WORDS} words, got {len(words)}"
            )
        return words


def _ccw(a: _Point, b: _Point, c: _Point) -> bool:
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0]) > 0


def _segments_cross(a: _Point, b: _Point, c: _Point, d: _Point) -> bool:
    return _ccw(a, c, d) != _ccw(b, c, d) and _ccw(a, b, c) != _ccw(a, b, d)


def _has_self_intersection(points: list[_Point]) -> bool:
    n = len(points)
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # adjacent edges share an endpoint
            if _segments_cross(*edges[i], *edges[j]):
                return True
    return False


class ZoneRequest(BaseModel):
    zone: list[_Point] | None = Field(
        default=None,
        description=(
            "Polygon of 3-20 normalized (x, y) points with no self-intersection; "
            "null clears the zone."
        ),
    )

    @field_validator("zone")
    @classmethod
    def _validate_zone(cls, value: list[_Point] | None) -> list[_Point] | None:
        if value is None:
            return None
        if not _MIN_ZONE_POINTS <= len(value) <= _MAX_ZONE_POINTS:
            raise ValueError(
                f"zone must have {_MIN_ZONE_POINTS}-{_MAX_ZONE_POINTS} points, got {len(value)}"
            )
        for x, y in value:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"zone points must be normalized 0-1, got ({x}, {y})")
        if _has_self_intersection(value):
            raise ValueError("zone polygon must not self-intersect")
        return value


# --------------------------------------------------------------------------
# Wire event parts
# --------------------------------------------------------------------------


class Provenance(BaseModel):
    """Which scorer, config, model and input size produced the event, plus the hash chain."""

    scorer_id: str
    config_sha256: str
    model_sha256: str
    input_size: int
    prev_hash: str
    hash: str


class TrackOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    track_id: int
    class_name: str = Field(alias="class")
    bbox: BBox = Field(description="Normalized [x1, y1, x2, y2].")
    likelihood: float = Field(description="The detector's probability for this class.")
    heading_deg: float | None = Field(
        default=None,
        description=(
            "Direction on screen, 0° = toward the top of the frame, measured clockwise. "
            "Not a compass bearing. Suspended when truncated or the camera is moving."
        ),
    )
    direction: Direction | None = Field(
        default=None, description="The 8-way label for heading_deg."
    )
    speed_body_heights_per_s: float | None = Field(
        default=None,
        description="Distance per second in multiples of the object's own box height.",
    )
    camera_mode: Literal["fixed", "moving"]


class LinkOut(BaseModel):
    object_track_id: int
    object_class: str
    object_likelihood: float = Field(description="The detector's probability for this detection.")
    linked_s: float
    strength: float = Field(
        description="0-1, describing the link (mean overlap, duration and fade factor)."
    )
    out_of_view_s: float | None = Field(
        default=None, description="Seconds since the object went out of view, while held."
    )


class EvidenceItem(BaseModel):
    rule_id: str
    rule_version: int
    type: Literal["supporting", "contradictory"]
    observed: float
    threshold: float
    contribution: int = Field(
        description="Integer; all evidence contributions sum exactly to threat.score."
    )
    text: str = Field(description="One plain-English sentence from a fixed template.")


class Threat(BaseModel):
    score: int
    band: Band
    evidence: list[EvidenceItem]


class ConfidenceDimensions(BaseModel):
    detector: float = Field(description="The track's likelihood, smoothed over the last 1 s.")
    track_stability: float = Field(description="The hit ratio over the last 2 s.")
    image_quality: float = Field(
        description="The mean of a brightness term and a sharpness term."
    )


class Confidence(BaseModel):
    score: float = Field(
        description=(
            "The mean of the three dimensions, rounded to 2 decimals. "
            "Never changes the threat score."
        )
    )
    dimensions: ConfidenceDimensions


class Unknown(BaseModel):
    code: UnknownCode
    detail: str


class Raw(BaseModel):
    in_zone: bool
    dwell_s: float = Field(
        description=(
            "Continuous seconds inside the zone, tolerating gaps up to 1 s (config), "
            "carried across track_restarted."
        )
    )
    approach: float
    truncated: bool


class Snapshot(BaseModel):
    path: str
    sha256: str


# --------------------------------------------------------------------------
# Wire events
# --------------------------------------------------------------------------


class _EventBase(BaseModel):
    schema_version: str = SCHEMA_VERSION
    event_id: str
    session_id: str
    source_id: str
    ts: str = Field(
        description="ISO-8601 UTC timestamp with milliseconds, e.g. 2026-09-26T18:04:11.231Z."
    )
    provenance: Provenance


class SessionStarted(_EventBase):
    """Always the first line of a log."""

    type: Literal["session.started"] = "session.started"
    threat_objects: list[str]
    zone: list[_Point] | None
    source: str
    camera_name: str
    device: Literal["cpu", "cuda", "mps"]
    model: str
    model_sha256: str
    input_size: int
    save_stills: bool
    config: dict
    app_version: str


class PipelineChanged(_EventBase):
    type: Literal["pipeline.changed"] = "pipeline.changed"
    model: str
    model_sha256: str
    input_size: int
    reason: Literal["fps_below_floor"]


class TrackUpdated(_EventBase):
    type: Literal["track.updated"] = "track.updated"
    track: TrackOut
    links: list[LinkOut] = Field(
        description="Every threat object currently linked to this person; empty if none."
    )
    summary: str = Field(
        description="One plain-English sentence from a fixed template (like Guardian's hypothesis)."
    )
    threat: Threat
    confidence: Confidence
    unknowns: list[Unknown]
    raw: Raw
    snapshot: Snapshot | None = None


class TrackEnded(_EventBase):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["track.ended"] = "track.ended"
    track_id: int
    class_name: str = Field(alias="class")
    duration_s: float
    peak_score: int
    peak_band: Band


class SourceHealth(_EventBase):
    type: Literal["source.health"] = "source.health"
    code: Literal["fps_low", "frozen_frame", "black_frame", "blur", "scene_change"]
    value: float
    detail: str


class SessionEnded(_EventBase):
    """Always the last line of a log that ended normally."""

    type: Literal["session.ended"] = "session.ended"
    reason: Literal["stopped", "quit", "error", "camera_lost", "idle"]
    detail: str | None = None
    peak_band: Band = Field(
        description="The highest band any track reached this session; low if none (added in 1.1)."
    )


Event = Annotated[
    SessionStarted | PipelineChanged | TrackUpdated | TrackEnded | SourceHealth | SessionEnded,
    Field(discriminator="type"),
]

EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)
