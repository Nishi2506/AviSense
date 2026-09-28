import numpy as np
import pandas as pd

from src.evaluate_tracking import match_frame, score


def test_match_frame_is_one_to_one_within_radius():
    pred = np.array([[100, 100], [104, 100], [500, 500]], dtype=float)
    gt = np.array([[102, 100], [300, 300]], dtype=float)
    assert match_frame(pred, gt, 15) == 1  # two predictions near one bird count once
    assert match_frame(pred, np.empty((0, 2)), 15) == 0


def test_score_filters_by_confidence_and_age():
    tracks = pd.DataFrame({
        "frame":      [0, 1, 1, 2],
        "track_id":   [1, 1, 2, 1],
        "confidence": [0.9, 0.9, 0.15, 0.9],
        "cx":         [10.0, 12.0, 400.0, 14.0],
        "cy":         [10.0, 10.0, 400.0, 10.0],
        "age":        [0, 1, 0, 2],
        "motion":     [0.0, 2.0, 0.0, 4.0],
    })
    gt = {0: np.array([[10.0, 10.0]]), 1: np.array([[12.0, 10.0]]), 2: np.empty((0, 2))}

    all_ = score(tracks, gt, min_conf=0.1, min_age=0, max_dist=15)
    assert all_["recall"] == 1.0 and all_["precision"] == 2 / 4
    assert all_["false_alarm_frames"] == 2 / 3  # frame 1 (track 2) and frame 2 (bird gone)

    strict = score(tracks, gt, min_conf=0.5, min_age=1, max_dist=15)
    assert strict["recall"] == 0.5 and strict["precision"] == 1 / 2
    assert strict["missed_bird_frames"] == 0.5


def test_add_track_state_age_and_running_max_motion():
    from src.evaluate_tracking import add_track_state
    df = add_track_state(pd.DataFrame({"frame": [0, 1, 2, 5], "track_id": [3, 3, 3, 3],
                                       "confidence": [0.5] * 4, "cx": [0.0, 3.0, 1.0, 0.0], "cy": [0.0, 4.0, 0.0, 0.0]}))
    assert df["age"].tolist() == [0, 1, 2, 5]
    assert df["motion"].tolist() == [0.0, 5.0, 5.0, 5.0]  # running max: stays 5 after returning
