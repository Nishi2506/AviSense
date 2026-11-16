import sqlite3

import numpy as np
import pytest
from starlette.testclient import TestClient

from src.alert_log import EXTRA_COLUMNS, AlertLog
from src.api import results as res
from src.api.server import app
from src.api.session import RunParams, RunSession, clean
from src.pipeline import AlertTracker, FrameRisk
from src.risk_scoring.risk import FACTORS, RiskConfig


@pytest.fixture
def client():
    return TestClient(app)


def _params(**kw):
    return RunParams(source="data/videos/x.mp4", zones="D02.json", weights="models/x.pt", **kw)


def test_risk_config_normalises_weights_and_applies_overrides():
    cfg = _params(risk_weights={"proximity": 70, "count": 30, "speed": 0, "flock_size": 0, "time_of_day": 0},
                  medium=0.25, high=0.55, min_duration_s=2.0, merge_gap_s=0.5).risk_config()
    assert sum(cfg.weights.values()) == pytest.approx(1.0)
    assert cfg.weights["proximity"] == pytest.approx(0.7)
    assert cfg.levels == {"medium": 0.25, "high": 0.55}
    assert cfg.alerts["min_duration_s"] == 2.0 and cfg.alerts["merge_gap_s"] == 0.5
    assert RiskConfig.load("configs/risk.yaml").alerts["merge_gap_s"] != 0.5  # file defaults untouched


@pytest.mark.parametrize("kw", [{"medium": 0.7, "high": 0.6}, {"risk_weights": dict.fromkeys(FACTORS, 0)}])
def test_risk_config_rejects_bad_values(kw):
    with pytest.raises(ValueError):
        _params(**kw).risk_config()


def test_alert_episode_records_peak_contributions_speed_and_distance():
    cfg = RiskConfig.load("configs/risk.yaml")
    log = AlertLog(":memory:")
    tracker = AlertTracker(cfg, log)
    contrib_a = dict.fromkeys(FACTORS, 0.1)
    contrib_b = {**dict.fromkeys(FACTORS, 0.05), "proximity": 0.35}
    frames = [  # (time, score, contributions, max_speed, min_dist)
        (0.0, 0.40, contrib_a, 0.10, 0.20),
        (0.5, 0.55, contrib_b, 0.30, 0.00),  # the peak
        (1.2, 0.45, contrib_a, 0.05, np.nan),  # no birds measured: distance stays at the minimum seen
    ]
    for i, (t, s, c, v, d) in enumerate(frames):
        tracker.update(i, t, FrameRisk({"count": 2, "max_speed": v, "min_dist_to_zone": d}, s, s, "Medium", "proximity", c))
    tracker.finish()

    ep = tracker.closed[0]
    assert ep["c_proximity"] == pytest.approx(0.35) and ep["c_count"] == pytest.approx(0.05)
    assert ep["max_speed"] == pytest.approx(0.30)
    assert ep["min_dist"] == 0.0
    row = log.recent().iloc[0]
    assert row["c_proximity"] == pytest.approx(0.35) and row["min_dist"] == 0.0


def test_alert_log_adds_new_columns_to_old_database(tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, peak_level TEXT)")
    conn.execute("INSERT INTO alerts (source, peak_level) VALUES ('old.mp4', 'Medium')")
    conn.commit()
    conn.close()

    log = AlertLog(db)
    cols = {r[1] for r in log.conn.execute("PRAGMA table_info(alerts)")}
    assert set(EXTRA_COLUMNS) <= cols
    old = log.recent().iloc[0]
    assert old["source"] == "old.mp4" and old["c_proximity"] is None
    assert log.count() == 1
    log.close()


def test_clean_makes_json_safe():
    assert clean({"a": float("nan"), "b": [np.float32(1.5), np.int64(2)], "c": float("inf")}) == {"a": None, "b": [1.5, 2], "c": None}


def test_session_snapshot_idle_and_frame_buffer(tmp_path):
    s = RunSession(tmp_path / "a.db")
    snap = s.snapshot()
    assert snap["status"] == "idle" and snap["history"] == [] and s.frame_jpeg() is None
    s._frames[3] = np.zeros((40, 60, 3), np.uint8)
    jpg = s.frame_jpeg(3)
    assert jpg[:2] == b"\xff\xd8"  # JPEG
    assert s.frame_jpeg(99) == jpg  # unknown seq falls back to the newest frame


def test_config_lists_known_files(client):
    c = client.get("/api/config").json()
    assert "D02.json" in c["zones"]
    assert all(v["path"].startswith("data/videos/") for v in c["videos"])
    assert set(c["risk"]["weights"]) == set(FACTORS)


@pytest.mark.parametrize("path", ["../README.md", "data/videos/../../configs/risk.yaml", "configs/zones/D02.json"])
def test_video_frame_rejects_paths_outside_video_dir(client, path):
    assert client.get("/api/videos/frame", params={"path": path}).status_code == 404


def test_run_validates_inputs(client):
    assert client.post("/api/run", json={"source": "data/videos/missing.mp4"}).status_code == 404
    videos = client.get("/api/config").json()["videos"]
    if videos:
        body = {"source": videos[0]["path"], "zones": "nope.json", "weights": "models/x.pt"}
        assert client.post("/api/run", json=body).status_code == 400


def test_results_and_unknown_routes(client):
    r = client.get("/api/results").json()
    assert r["detector"]["map50"] == res.DETECTOR["map50"]
    assert any(m.get("current") for m in r["models"])
    assert client.get("/api/results/image/../../README.md").status_code == 404
    assert client.get("/api/nothing-here").status_code == 404
