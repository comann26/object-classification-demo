"""Rules scorer: threat score, bands, confidence, plain-English templates.

All contributions are rounded half-up to integers before summing, and the
0-100 clamp is itself an evidence item, so `evidence[].contribution` always
sums exactly to `threat.score`. See docs/design.md §2 (`track.updated`
example) and §3 (Score, Bands).
"""

from __future__ import annotations

from dataclasses import dataclass

from demo.config import ScoringConfig
from demo.contracts import (
    Band,
    Confidence,
    ConfidenceDimensions,
    EvidenceItem,
    Link,
    Track,
    Unknown,
)

RULES = (
    "threat_object_link",
    "unattended",
    "in_zone",
    "loiter",
    "approach",
    "running",
    "moving_away",
    "leaving_zone",
    "clamp",
)
_RULE_VERSION = 1

_BAND_BOUNDS: dict[Band, tuple[int, int]] = {
    "low": (0, 24),
    "medium": (25, 49),
    "high": (50, 74),
    "critical": (75, 100),
}
_BAND_ORDER: tuple[Band, ...] = ("low", "medium", "high", "critical")


@dataclass
class Inputs:
    track: Track
    links: list[Link]
    motion_enabled: bool
    heading: float | None
    speed: float | None
    approach: float | None
    in_zone: bool
    left_zone: bool
    dwell_s: float
    unattended_s: float | None
    detector_conf: float
    track_stability: float
    image_quality: float
    unknowns: list[Unknown]


@dataclass
class Assessment:
    score: int
    raw_band: Band
    evidence: list[EvidenceItem]
    summary: str
    confidence: Confidence
    unknowns: list[Unknown]


def _round_half_up(x: float) -> int:
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def band_of(score: int) -> Band:
    for band, (lo, hi) in _BAND_BOUNDS.items():
        if lo <= score <= hi:
            return band
    raise ValueError(f"score out of range: {score}")


class BandTracker:
    """Per-track band with hysteresis (docs/design.md §3 Bands)."""

    def __init__(self, hysteresis: int) -> None:
        self._hysteresis = hysteresis
        self._current: dict[int, Band] = {}

    def update(self, track_id: int, score: int) -> Band:
        raw = band_of(score)
        cur = self._current.get(track_id)
        if cur is None:
            self._current[track_id] = raw
            return raw

        raw_idx = _BAND_ORDER.index(raw)
        cur_idx = _BAND_ORDER.index(cur)
        if raw_idx > cur_idx:
            lo, _hi = _BAND_BOUNDS[raw]
            new_band = raw if score >= lo + self._hysteresis else cur
        elif raw_idx < cur_idx:
            _lo, hi = _BAND_BOUNDS[raw]
            new_band = raw if score <= hi - self._hysteresis else cur
        else:
            new_band = cur

        self._current[track_id] = new_band
        return new_band

    def forget(self, track_id: int) -> None:
        self._current.pop(track_id, None)


def _link_item(link: Link, cfg: ScoringConfig) -> EvidenceItem:
    c = _round_half_up(float(cfg.weights.link))
    form_s = cfg.link.form_s
    return EvidenceItem(
        rule_id="threat_object_link",
        rule_version=_RULE_VERSION,
        type="supporting",
        observed=link.linked_s,
        threshold=form_s,
        contribution=c,
        text=f"Holding a {link.object_class} for {link.linked_s:.1f} s (needs {form_s:g} s): +{c}",
    )


def _unattended_item(inp: Inputs, cfg: ScoringConfig) -> EvidenceItem | None:
    if inp.track.class_name == "person" or inp.links:
        return None
    if inp.unattended_s is None or inp.unattended_s < cfg.weights.unattended_after_s:
        return None
    c = _round_half_up(float(cfg.weights.unattended))
    threshold = cfg.weights.unattended_after_s
    return EvidenceItem(
        rule_id="unattended",
        rule_version=_RULE_VERSION,
        type="supporting",
        observed=inp.unattended_s,
        threshold=threshold,
        contribution=c,
        text=f"Unattended for {inp.unattended_s:.1f} s (needs {threshold:g} s): +{c}",
    )


def _in_zone_item(inp: Inputs, cfg: ScoringConfig) -> EvidenceItem | None:
    if not inp.in_zone:
        return None
    c = _round_half_up(float(cfg.weights.in_zone))
    return EvidenceItem(
        rule_id="in_zone",
        rule_version=_RULE_VERSION,
        type="supporting",
        observed=1.0,
        threshold=1.0,
        contribution=c,
        text=f"Inside the zone: +{c}",
    )


def _loiter_item(inp: Inputs, cfg: ScoringConfig) -> EvidenceItem | None:
    if not inp.in_zone or inp.dwell_s < cfg.zone.loiter_s:
        return None
    c = _round_half_up(float(cfg.weights.loiter))
    return EvidenceItem(
        rule_id="loiter",
        rule_version=_RULE_VERSION,
        type="supporting",
        observed=inp.dwell_s,
        threshold=cfg.zone.loiter_s,
        contribution=c,
        text=f"Loitering for {inp.dwell_s:.1f} s (needs {cfg.zone.loiter_s:g} s): +{c}",
    )


def _motion_points(inp: Inputs, cfg: ScoringConfig) -> tuple[float, float, float]:
    """Returns (approach_pts, running_pts, growth) after the combined cap, pre-rounding."""
    w = cfg.weights
    growth = inp.approach if inp.approach is not None else 0.0
    speed = inp.speed if inp.speed is not None else 0.0

    approach_span = w.approach_max - w.approach_min
    approach_frac = _clamp01((growth - w.approach_min) / approach_span) if approach_span else 0.0
    approach_pts = w.motion_cap * approach_frac

    run_span = w.run_max - w.run_min
    run_frac = _clamp01((speed - w.run_min) / run_span) if run_span else 0.0
    running_pts = w.motion_cap * run_frac

    total = approach_pts + running_pts
    if total > w.motion_cap and total > 0:
        scale = w.motion_cap / total
        approach_pts *= scale
        running_pts *= scale

    return approach_pts, running_pts, growth


def _approach_running_items(
    inp: Inputs, cfg: ScoringConfig
) -> tuple[EvidenceItem | None, EvidenceItem | None]:
    approach_pts, running_pts, growth = _motion_points(inp, cfg)
    speed = inp.speed if inp.speed is not None else 0.0

    approach_c = _round_half_up(approach_pts)
    running_c = _round_half_up(running_pts)

    # Fix up rounding so the combined cap still holds exactly after rounding.
    cap = cfg.weights.motion_cap
    if approach_pts + running_pts >= cap and approach_c + running_c > cap:
        diff = (approach_c + running_c) - cap
        if approach_c >= running_c:
            approach_c -= diff
        else:
            running_c -= diff

    approach_item = None
    if approach_c > 0:
        w = cfg.weights
        approach_item = EvidenceItem(
            rule_id="approach",
            rule_version=_RULE_VERSION,
            type="supporting",
            observed=growth,
            threshold=w.approach_min,
            contribution=approach_c,
            text=(
                f"Moving closer: box grew {growth * 100:.0f}% wider in 2 s "
                f"(needs {w.approach_min * 100:.0f}%): +{approach_c}"
            ),
        )

    running_item = None
    if running_c > 0:
        w = cfg.weights
        running_item = EvidenceItem(
            rule_id="running",
            rule_version=_RULE_VERSION,
            type="supporting",
            observed=speed,
            threshold=w.run_min,
            contribution=running_c,
            text=f"Running: {speed:.1f} body heights/s (needs {w.run_min:g}): +{running_c}",
        )

    return approach_item, running_item


def _moving_away_item(inp: Inputs, cfg: ScoringConfig) -> EvidenceItem | None:
    if inp.approach is None or inp.approach > -cfg.weights.moving_away_shrink:
        return None
    c = -_round_half_up(float(cfg.weights.contradictory))
    shrink_pct = -inp.approach * 100
    threshold_pct = cfg.weights.moving_away_shrink * 100
    return EvidenceItem(
        rule_id="moving_away",
        rule_version=_RULE_VERSION,
        type="contradictory",
        observed=inp.approach,
        threshold=-cfg.weights.moving_away_shrink,
        contribution=c,
        text=f"Moving away: box shrank {shrink_pct:.0f}% in 2 s (needs {threshold_pct:.0f}%): {c}",
    )


def _leaving_zone_item(inp: Inputs, cfg: ScoringConfig) -> EvidenceItem | None:
    if not inp.left_zone:
        return None
    c = -_round_half_up(float(cfg.weights.contradictory))
    return EvidenceItem(
        rule_id="leaving_zone",
        rule_version=_RULE_VERSION,
        type="contradictory",
        observed=1.0,
        threshold=0.0,
        contribution=c,
        text=f"Left the zone: {c}",
    )


def _clamp_item(raw: int, clamped: int) -> EvidenceItem:
    delta = clamped - raw
    return EvidenceItem(
        rule_id="clamp",
        rule_version=_RULE_VERSION,
        type="contradictory" if clamped < raw else "supporting",
        observed=float(raw),
        threshold=100.0 if clamped < raw else 0.0,
        contribution=delta,
        text=f"Capped at {clamped}: {delta:+d}",
    )


def _summary(
    inp: Inputs,
    in_zone_fired: bool,
    approach_fired: bool,
    running_fired: bool,
    unattended_fired: bool,
) -> str:
    track = inp.track
    if track.class_name == "person":
        fragments = []
        if in_zone_fired:
            fragments.append(" inside the zone")
        if approach_fired:
            fragments.append(" and moving closer")
        if running_fired:
            fragments.append(" and running")

        if inp.links:
            objs = " and ".join(link.object_class for link in inp.links)
            ctx = "".join(fragments)
            return f"Person {track.track_id} is holding a {objs}{ctx}."

        if not fragments:
            return f"Person {track.track_id} is in view."

        first = fragments[0]
        if first.startswith(" and "):
            first = " " + first[len(" and "):]
        ctx = " is" + first + "".join(fragments[1:])
        return f"Person {track.track_id}{ctx}."

    if unattended_fired:
        return f"Unattended {track.class_name} (object {track.track_id})."
    name = track.class_name
    cls = name[:1].upper() + name[1:] if name else name
    return f"{cls} (object {track.track_id})."


def score(inp: Inputs, cfg: ScoringConfig) -> Assessment:
    items: list[EvidenceItem] = []

    for link in inp.links:
        items.append(_link_item(link, cfg))

    unattended_item = _unattended_item(inp, cfg)
    if unattended_item is not None:
        items.append(unattended_item)

    in_zone_item = _in_zone_item(inp, cfg)
    if in_zone_item is not None:
        items.append(in_zone_item)

    loiter_item = _loiter_item(inp, cfg)
    if loiter_item is not None:
        items.append(loiter_item)

    approach_item = running_item = None
    if inp.motion_enabled:
        approach_item, running_item = _approach_running_items(inp, cfg)
        if approach_item is not None:
            items.append(approach_item)
        if running_item is not None:
            items.append(running_item)

        moving_away_item = _moving_away_item(inp, cfg)
        if moving_away_item is not None:
            items.append(moving_away_item)

    leaving_zone_item = _leaving_zone_item(inp, cfg)
    if leaving_zone_item is not None:
        items.append(leaving_zone_item)

    raw = sum(item.contribution for item in items)
    clamped = max(0, min(100, raw))
    if clamped != raw:
        items.append(_clamp_item(raw, clamped))

    summary = _summary(
        inp,
        in_zone_fired=in_zone_item is not None,
        approach_fired=approach_item is not None,
        running_fired=running_item is not None,
        unattended_fired=unattended_item is not None,
    )

    mean = (inp.detector_conf + inp.track_stability + inp.image_quality) / 3.0
    confidence = Confidence(
        score=round(mean, 2),
        dimensions=ConfidenceDimensions(
            detector=inp.detector_conf,
            track_stability=inp.track_stability,
            image_quality=inp.image_quality,
        ),
    )

    return Assessment(
        score=clamped,
        raw_band=band_of(clamped),
        evidence=items,
        summary=summary,
        confidence=confidence,
        unknowns=inp.unknowns,
    )
