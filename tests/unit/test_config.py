import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from demo.config import ScoringConfig, config_sha256, load_config, reset_to_defaults, save_config

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_defaults_load_and_match_file():
    defaults = ScoringConfig()
    with open(CONFIG_DIR / "scoring.default.json", encoding="utf-8") as f:
        on_disk = json.load(f)
    assert defaults.model_dump(mode="json") == on_disk


def test_out_of_range_rejected():
    with pytest.raises(ValidationError):
        ScoringConfig(weights={**ScoringConfig().weights.model_dump(), "link": 500})


def test_hash_stable_and_changes():
    a = ScoringConfig()
    b = ScoringConfig()
    assert config_sha256(a) == config_sha256(b)

    c = ScoringConfig(weights={**ScoringConfig().weights.model_dump(), "link": 60})
    assert config_sha256(a) != config_sha256(c)


def test_reset_copies_default(tmp_path):
    save_config(ScoringConfig(), tmp_path / "scoring.default.json")
    modified = ScoringConfig(weights={**ScoringConfig().weights.model_dump(), "link": 60})
    save_config(modified, tmp_path / "scoring.json")

    reset = reset_to_defaults(tmp_path)

    assert config_sha256(reset) == config_sha256(ScoringConfig())
    assert config_sha256(load_config(tmp_path / "scoring.json")) == config_sha256(ScoringConfig())


def test_idle_stop_has_a_floor():
    # 0 would idle out every Go immediately (final review #4).
    with pytest.raises(ValidationError):
        ScoringConfig(runtime={"idle_stop_s": 0})
    assert ScoringConfig(runtime={"idle_stop_s": 5}).runtime.idle_stop_s == 5
