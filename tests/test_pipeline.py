from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.alert_log import AlertLog
from src.pipeline import AlertTracker, FrameRisk, OnlineRiskEngine, parse_start_time
from src.risk_scoring.features import frame_features, track_features
from src.risk_scoring.risk import FACTORS, RiskConfig, alert_episodes, score
from src.risk_scoring.zones import Zone
from src.tracking.track import TrackedDetection

W, H, FPS = 200, 100, 10
ZONES = [Zone("runway", [(0.6, 0.0), (1.0, 0.0), (1.0, 1.0), (0.6, 1.0)])]
START = datetime(2021, 6, 28, 6, 0)


def _synthetic_tracks(n=80):
    """Two birds fly toward the zone, one appears late; birds leave after frame 60."""
    rows = []
    for i in range(n):
        if i < 60:
            rows.append(dict(frame_idx=i, track_id=1, cx=10 + 2 * i, cy=40))
            rows.append(dict(frame_idx=i, track_id=2, cx=15 + 2 * i, cy=45))
        if 20 <= i < 60:
            rows.append(dict(frame_idx=i, track_id=3, cx=190 - i, cy=80))
    df = pd.DataFrame(rows)
    df["time_s"] = df["frame_idx"] / FPS
    df["frame_w"], df["frame_h"] = W, H
    return df


def _as_tracked(rows):
    return [TrackedDetection(int(r.frame_idx), r.cx - 2, r.cy - 2, r.cx + 2, r.cy + 2, 0.9, 0, "bird",
                             track_id=int(r.track_id), time_s=r.time_s) for r in rows.itertuples()]


@pytest.fixture
def cfg():
    return RiskConfig.load("configs/risk.yaml")


def test_parse_start_time():
    assert parse_start_time("images_test_D02_20210628090856.mp4") == datetime(2021, 6, 28, 9, 8, 56)
    assert parse_start_time("data/videos/sample.mp4") is None


def test_online_engine_matches_batch(cfg):
    n = 80
    df = _synthetic_tracks(n)
    batch = score(frame_features(track_features(df, ZONES, window=5), n_frames=n, start_time=START), cfg)

    engine = OnlineRiskEngine(ZONES, cfg, window=5, start_time=START)
    for i in range(n):
        risk = engine.update(_as_tracked(df[df["frame_idx"] == i]), i, i / FPS, W, H)
        b = batch.iloc[i]
        assert risk.features["count"] == b["count"]
        assert risk.features["max_speed"] == pytest.approx(b["max_speed"])
        assert risk.raw == pytest.approx(b["risk_raw"])
        assert risk.score == pytest.approx(b["risk_score"])
        assert risk.level == b["risk_level"]


def test_alert_tracker_matches_batch_and_logs(cfg):
    n = 80
    df = _synthetic_tracks(n)
    batch = score(frame_features(track_features(df, ZONES), n_frames=n, start_time=START), cfg)
    expected = alert_episodes(batch, cfg)
    assert len(expected) >= 1  # the scenario must actually trigger an alert

    log = AlertLog(":memory:")
    tracker = AlertTracker(cfg, log, meta={"source": "test.mp4", "camera": "T1"}, start_time=START)
    for r in batch.itertuples():
        fr = FrameRisk({"count": r.count}, r.risk_score, r.risk_raw, r.risk_level, r.top_factor,
                       {f: getattr(r, f"c_{f}") for f in FACTORS})
        tracker.update(r.frame_idx, r.time_s, fr)
    tracker.finish()

    got = pd.DataFrame(tracker.closed)
    for col in ["start_frame", "end_frame", "peak_level", "top_factor", "max_count"]:
        assert list(got[col]) == list(expected[col])
    assert np.allclose(got["peak_score"], expected["peak_score"])

    logged = log.recent()
    assert len(logged) == len(expected)
    assert (logged["status"] == "closed").all() and (logged["camera"] == "T1").all()
    assert logged["started_at"].iloc[-1].startswith("2021-06-28T06:00")


def test_alert_not_active_before_min_duration(cfg):
    tracker = AlertTracker(cfg)  # min_duration_s = 1.0
    high = FrameRisk({"count": 5}, 0.8, 0.8, "High", "proximity", dict.fromkeys(FACTORS, 0.16))
    tracker.update(0, 0.0, high)
    tracker.update(5, 0.5, high)
    assert tracker.active is None
    tracker.update(10, 1.0, high)
    assert tracker.active["peak_level"] == "High"
