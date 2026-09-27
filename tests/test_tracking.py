from src.tracking.track import TrackedDetection, TrackHistory


def _t(track_id, frame_idx, cx, cy, size=4.0):
    h = size / 2
    return TrackedDetection(frame_idx, cx - h, cy - h, cx + h, cy + h, 0.9, 0, "bird",
                            track_id=track_id, time_s=frame_idx / 10)


def test_history_records_centers_in_order():
    hist = TrackHistory()
    hist.update([_t(1, 0, 10, 20)])
    hist.update([_t(1, 1, 15, 22)])
    assert hist.points(1) == [(0.0, 10.0, 20.0), (0.1, 15.0, 22.0)]


def test_history_keeps_ids_separate():
    hist = TrackHistory()
    hist.update([_t(1, 0, 10, 10), _t(2, 0, 50, 50)])
    assert sorted(hist.active_ids()) == [1, 2]
    assert hist.points(2) == [(0.0, 50.0, 50.0)]


def test_history_is_bounded():
    hist = TrackHistory(maxlen=3)
    for i in range(10):
        hist.update([_t(7, i, i, 0)])
    assert [p[1] for p in hist.points(7)] == [7.0, 8.0, 9.0]


def test_unknown_id_returns_empty():
    assert TrackHistory().points(99) == []
