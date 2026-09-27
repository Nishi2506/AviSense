from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.risk_scoring.features import _flocks, frame_features, track_features
from src.risk_scoring.zones import Zone, distance_to_zones, load_zones, save_zones

W = H = 100
DIAG = np.hypot(W, H)
FPS = 10
RIGHT_HALF = [Zone("runway", [(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)])]


def _tracks():
    rows = []
    for i in range(8):
        # bird 1 flies right toward the zone at 5 px/frame = 50 px/s
        rows.append(dict(frame_idx=i, time_s=i / FPS, track_id=1, cx=10 + 5 * i, cy=50))
        # bird 2 sits still inside the zone
        rows.append(dict(frame_idx=i, time_s=i / FPS, track_id=2, cx=80, cy=50))
    df = pd.DataFrame(rows)
    df["frame_w"], df["frame_h"] = W, H
    return df


def test_distance_to_zone_outside_and_inside():
    assert distance_to_zones(30, 50, RIGHT_HALF, W, H) == pytest.approx(20)
    assert distance_to_zones(80, 50, RIGHT_HALF, W, H) == 0


def test_zones_roundtrip(tmp_path):
    p = tmp_path / "zones.json"
    save_zones(p, RIGHT_HALF, camera="D02")
    camera, zones = load_zones(p)
    assert camera == "D02"
    assert zones[0].name == "runway" and zones[0].polygon == RIGHT_HALF[0].polygon


def test_track_features_motion_and_zone():
    tf = track_features(_tracks(), RIGHT_HALF, window=3).set_index(["track_id", "frame_idx"])
    b1 = tf.loc[1].loc[7]
    assert b1["speed"] == pytest.approx(50 / DIAG)
    assert b1["heading_deg"] == pytest.approx(0)          # moving right
    assert b1["approach_rate"] == pytest.approx(50 / DIAG)  # closing at full speed
    assert b1["dist_to_zone"] == pytest.approx((50 - 45) / DIAG)
    assert not b1["in_zone"]

    b2 = tf.loc[2].loc[7]
    assert b2["speed"] == 0 and b2["in_zone"] and np.isnan(b2["heading_deg"])
    assert tf.loc[1].loc[0]["track_age"] == 0 and b1["track_age"] == 7


def test_heading_up_is_90_degrees():
    df = pd.DataFrame(dict(frame_idx=[0, 1], time_s=[0, 0.1], track_id=[1, 1],
                           cx=[20, 20], cy=[50, 40], frame_w=W, frame_h=H))
    assert track_features(df, RIGHT_HALF, window=1)["heading_deg"].iloc[1] == pytest.approx(90)


def test_flocks():
    pts = np.array([[0.10, 0.10], [0.12, 0.10], [0.14, 0.11], [0.80, 0.80]])
    assert _flocks(pts, radius=0.05) == (3, 2)
    assert _flocks(np.empty((0, 2)), radius=0.05) == (0, 0)


def test_frame_features_aggregates_and_fills_gaps():
    tf = track_features(_tracks(), RIGHT_HALF, window=3)
    ff = frame_features(tf, n_frames=10, start_time=datetime(2021, 6, 28, 9, 30))
    assert list(ff["frame_idx"]) == list(range(10))

    f7 = ff.iloc[7]
    assert f7["count"] == 2 and f7["n_in_zone"] == 1 and f7["n_approaching"] == 1
    assert f7["min_dist_to_zone"] == 0
    assert f7["hour"] == pytest.approx(9.5)

    empty = ff.iloc[9]  # no birds in the last two frames
    assert empty["count"] == 0 and empty["max_speed"] == 0
    assert np.isnan(empty["min_dist_to_zone"])
    assert empty["time_s"] == pytest.approx(0.9)


def test_min_track_age_filters_young_tracks():
    tf = track_features(_tracks(), RIGHT_HALF)
    ff = frame_features(tf, min_track_age=3)
    assert ff.iloc[0]["count"] == 0 and ff.iloc[3]["count"] == 2
