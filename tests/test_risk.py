import numpy as np
import pandas as pd
import pytest

from src.risk_scoring.risk import (FACTORS, RiskConfig, alert_episodes, classify, normalise,
                                   score, time_of_day_value)


@pytest.fixture
def cfg():
    return RiskConfig.load("configs/risk.yaml")


def _ff(**cols):
    n = len(next(iter(cols.values())))
    base = dict(frame_idx=range(n), time_s=[i / 10 for i in range(n)], count=[0] * n,
                max_speed=[0.0] * n, min_dist_to_zone=[np.nan] * n, flock_size=[0] * n)
    base.update(cols)
    return pd.DataFrame(base)


def test_config_weights_sum_to_one(cfg):
    assert sum(cfg.weights[f] for f in FACTORS) == pytest.approx(1.0)


def test_bad_weights_rejected(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("weights: {count: 0.5, speed: 0.5, proximity: 0.5, flock_size: 0, time_of_day: 0}\n"
                 "normalise: {}\n")
    with pytest.raises(ValueError, match="sum to 1"):
        RiskConfig.load(p)


def test_classify_thresholds(cfg):
    assert classify(0.29, cfg) == "Low"
    assert classify(0.30, cfg) == "Medium"
    assert classify(0.60, cfg) == "High"


def test_time_of_day(cfg):
    assert time_of_day_value(6.5, cfg) == 1.0   # dawn
    assert time_of_day_value(12.0, cfg) == 0.4  # midday default
    assert time_of_day_value(np.nan, cfg) == 0.5


def test_no_birds_means_no_risk(cfg):
    out = score(_ff(count=[0, 0], hour=[6.0, 6.0]), cfg)
    assert (out["risk_raw"] == 0).all() and (out["risk_level"] == "Low").all()
    assert (out["top_factor"] == "").all()


def test_normalise_caps_and_proximity(cfg):
    t = normalise(_ff(count=[40, 10], max_speed=[1.0, 0.25], min_dist_to_zone=[0.0, 0.15],
                      flock_size=[3, 20]), cfg)
    assert list(t["count"]) == [1.0, 0.5]
    assert list(t["speed"]) == [1.0, 0.5]
    assert list(t["proximity"]) == pytest.approx([1.0, 0.5])
    assert list(t["flock_size"]) == [0.3, 1.0]


def test_score_is_weighted_sum_with_explanation(cfg):
    cfg.smoothing_frames = 1
    out = score(_ff(count=[10], max_speed=[0.25], min_dist_to_zone=[0.0], flock_size=[5], hour=[12.0]), cfg)
    expected = 0.20 * 0.5 + 0.15 * 0.5 + 0.35 * 1.0 + 0.15 * 0.5 + 0.15 * 0.4
    assert out["risk_raw"].iloc[0] == pytest.approx(expected)
    assert out["risk_level"].iloc[0] == "High"
    assert out["top_factor"].iloc[0] == "proximity"


def test_alert_episodes_merge_and_filter(cfg):
    cfg.smoothing_frames = 1
    # 0-1.9 s birds in zone (alert), 2.0-2.4 s clear, 2.5-3.9 s alert again,
    # 5.0-5.4 s a short blip, then clear. Frames are 0.1 s apart.
    n = 60
    in_zone = np.zeros(n, bool)
    in_zone[0:20] = in_zone[25:40] = in_zone[50:55] = True
    ff = _ff(count=np.where(in_zone, 10, 0), max_speed=[0.25] * n,
             min_dist_to_zone=np.where(in_zone, 0.0, np.nan), flock_size=np.where(in_zone, 5, 0),
             hour=[12.0] * n)
    eps = alert_episodes(score(ff, cfg), cfg)
    # First two merge (gap 0.6 s < 2 s); blip at 5.0 s merges too (gap 1.1 s).
    assert len(eps) == 1
    assert eps.iloc[0]["start_s"] == 0 and eps.iloc[0]["end_s"] == pytest.approx(5.4)

    cfg.alerts["merge_gap_s"] = 0.3
    eps = alert_episodes(score(ff, cfg), cfg)
    # Now three separate runs; the 0.4 s blip is dropped by min_duration_s = 1.0.
    assert list(eps["start_frame"]) == [0, 25]
    assert (eps["top_factor"] == "proximity").all()
    assert (eps["peak_level"] == "High").all()


def test_no_alerts_returns_empty_frame(cfg):
    eps = alert_episodes(score(_ff(count=[0, 0]), cfg), cfg)
    assert eps.empty and "peak_score" in eps.columns
