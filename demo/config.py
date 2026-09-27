"""Versioned scoring config: every tunable number the pipeline reads.

Loaded from `config/scoring.json`, editable via the server sliders, reset
from `config/scoring.default.json`. `config_sha256` uses the same
canonicalisation as the event log (`demo.events.canonical_json`) so a
`Provenance.config_sha256` faithfully identifies the exact numbers used.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from demo.events import canonical_json


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DetectConfig(_Section):
    person_min: float = Field(default=0.35, ge=0.0, le=1.0)
    object_min: float = Field(default=0.15, ge=0.0, le=1.0)
    threat_nms_iou: float = Field(default=0.5, ge=0.0, le=1.0)


class TrackerConfig(_Section):
    person_activation: float = Field(default=0.35, ge=0.0, le=1.0)
    object_activation: float = Field(default=0.15, ge=0.0, le=1.0)
    lost_track_buffer: int = Field(default=30, ge=1, le=300)
    minimum_matching_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class EligibilityConfig(_Section):
    person_min_age_s: float = Field(default=1.0, ge=0.0, le=60.0)
    person_min_hit_ratio: float = Field(default=0.6, ge=0.0, le=1.0)
    object_min_detections: int = Field(default=3, ge=1, le=30)


class MotionConfig(_Section):
    smoothing_s: float = Field(default=1.0, ge=0.0, le=60.0)
    approach_window_s: float = Field(default=2.0, ge=0.0, le=60.0)
    truncation_margin: float = Field(default=0.01, ge=0.0, le=1.0)
    camera_flow_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    camera_moving_s: float = Field(default=1.0, ge=0.0, le=60.0)


class RestartConfig(_Section):
    window_s: float = Field(default=1.0, ge=0.0, le=60.0)
    max_distance: float = Field(default=0.1, ge=0.0, le=1.0)


class LinkConfig(_Section):
    expand_side: float = Field(default=0.15, ge=0.0, le=1.0)
    expand_top: float = Field(default=0.15, ge=0.0, le=1.0)
    min_overlap: float = Field(default=0.30, ge=0.0, le=1.0)
    form_s: float = Field(default=0.5, ge=0.0, le=60.0)
    break_s: float = Field(default=1.0, ge=0.0, le=60.0)
    fade_s: float = Field(default=3.0, ge=0.0, le=60.0)
    strength_full_s: float = Field(default=2.0, ge=0.0, le=60.0)


class ZoneConfig(_Section):
    dwell_gap_s: float = Field(default=1.0, ge=0.0, le=60.0)
    loiter_s: float = Field(default=10.0, ge=0.0, le=120.0)


class WeightsConfig(_Section):
    link: int = Field(default=55, ge=0, le=100)
    unattended: int = Field(default=30, ge=0, le=100)
    unattended_after_s: float = Field(default=2.0, ge=0.0, le=60.0)
    in_zone: int = Field(default=25, ge=0, le=100)
    loiter: int = Field(default=15, ge=0, le=100)
    motion_cap: int = Field(default=20, ge=0, le=100)
    approach_min: float = Field(default=0.05, ge=0.0, le=1.0)
    approach_max: float = Field(default=0.25, ge=0.0, le=1.0)
    run_min: float = Field(default=1.0, ge=0.0, le=10.0)
    run_max: float = Field(default=2.0, ge=0.0, le=10.0)
    moving_away_shrink: float = Field(default=0.05, ge=0.0, le=1.0)
    contradictory: int = Field(default=5, ge=0, le=100)


class BandsConfig(_Section):
    hysteresis: int = Field(default=5, ge=0, le=20)


class ConfidenceConfig(_Section):
    sharp_ref: float = Field(default=100.0, gt=0.0, le=10000.0)
    luma_lo: int = Field(default=60, ge=0, le=255)
    luma_hi: int = Field(default=200, ge=0, le=255)

    @model_validator(mode="after")
    def _check_luma_order(self) -> ConfidenceConfig:
        if self.luma_lo >= self.luma_hi:
            raise ValueError("luma_lo must be < luma_hi")
        return self


class HealthConfig(_Section):
    black_luma: int = Field(default=10, ge=0, le=255)
    frozen_diff: float = Field(default=1.0, gt=0.0, le=10000.0)
    frozen_s: float = Field(default=2.0, ge=0.0, le=60.0)
    blur_var: float = Field(default=20.0, gt=0.0, le=10000.0)
    scene_change_diff: float = Field(default=60.0, gt=0.0, le=10000.0)


class EmitConfig(_Section):
    heartbeat_s: float = Field(default=2.0, ge=0.0, le=60.0)


class RuntimeConfig(_Section):
    model: Literal["auto", "small", "large"] = "auto"
    fps_floor: int = Field(default=10, ge=1, le=60)
    stepdown_after_s: float = Field(default=5.0, ge=0.0, le=60.0)
    idle_stop_s: float = Field(default=30.0, ge=5.0, le=60.0)


class ScoringConfig(_Section):
    detect: DetectConfig = Field(default_factory=DetectConfig)
    tracker: TrackerConfig = Field(default_factory=TrackerConfig)
    eligibility: EligibilityConfig = Field(default_factory=EligibilityConfig)
    motion: MotionConfig = Field(default_factory=MotionConfig)
    restart: RestartConfig = Field(default_factory=RestartConfig)
    link: LinkConfig = Field(default_factory=LinkConfig)
    zone: ZoneConfig = Field(default_factory=ZoneConfig)
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    bands: BandsConfig = Field(default_factory=BandsConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    emit: EmitConfig = Field(default_factory=EmitConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


def load_config(path: Path) -> ScoringConfig:
    with open(path, encoding="utf-8") as f:
        return ScoringConfig.model_validate(json.load(f))


def save_config(cfg: ScoringConfig, path: Path) -> None:
    text = json.dumps(cfg.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def config_sha256(cfg: ScoringConfig) -> str:
    return hashlib.sha256(canonical_json(cfg.model_dump(mode="json"))).hexdigest()


def reset_to_defaults(config_dir: Path) -> ScoringConfig:
    shutil.copyfile(config_dir / "scoring.default.json", config_dir / "scoring.json")
    return load_config(config_dir / "scoring.json")
