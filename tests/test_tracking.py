import numpy as np
from ultralytics.engine.results import Boxes

from src.tracking.track import TrackedDetection, TrackHistory, enlarge_boxes


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


def test_enlarge_boxes_grows_small_boxes_around_center_only():
    data = np.array([[100, 100, 106, 108, 0.9, 0], [0, 0, 60, 50, 0.5, 0]], dtype=np.float32)
    out = enlarge_boxes(data, 40)
    assert out[0, :4].tolist() == [83, 84, 123, 124]  # 6x8 box -> 40x40 around (103, 104)
    assert out[1, :4].tolist() == [0, 0, 60, 50]      # already larger: unchanged
    assert (out[:, 4:] == data[:, 4:]).all()


def test_tracker_links_tiny_fast_bird(monkeypatch):
    """A 6 px bird moving 8 px/frame has zero IoU frame to frame; it must still get one track ID."""
    import torch
    from src.tracking.track import BirdTracker

    class FakeResult:
        def __init__(self, x):
            rows = [] if x is None else [[x, 100, x + 6, 106, 0.9, 0]]
            self.boxes = Boxes(torch.tensor(rows, dtype=torch.float32).reshape(-1, 6), (1080, 1920))
            self.orig_shape = (1080, 1920)

    class FakeModel:
        x = 100
        def predict(self, frame, **kw):
            FakeModel.x += 8
            if FakeModel.x in (116, 164):  # frames where the detector misses the bird
                return [FakeResult(None)]
            return [FakeResult(FakeModel.x)]

    class FakeDetector:
        model, conf, imgsz, device, classes, names = FakeModel(), 0.1, 640, None, None, {0: "bird"}

    tracker = BirdTracker(FakeDetector())
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    ids = set()
    for i in range(10):
        ids.update(t.track_id for t in tracker.track(frame, i))
    assert len(ids) == 1


def test_static_detection_is_not_reported_until_it_moves():
    import torch
    from src.tracking.track import BirdTracker

    xs = [500] * 8 + [505, 512, 520]  # sits still for 8 frames, then flies off

    class FakeModel:
        i = -1
        def predict(self, frame, **kw):
            FakeModel.i += 1
            x = xs[FakeModel.i]
            r = type("R", (), {})()
            r.boxes = Boxes(torch.tensor([[x, 300, x + 6, 306, 0.9, 0]], dtype=torch.float32), (1080, 1920))
            r.orig_shape = (1080, 1920)
            return [r]

    class FakeDetector:
        model, conf, imgsz, device, classes, names = FakeModel(), 0.1, 640, None, None, {0: "bird"}

    tracker = BirdTracker(FakeDetector(), min_motion=10)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    reported = [len(tracker.track(frame, i)) for i in range(len(xs))]
    assert reported == [0] * 9 + [1, 1]  # first reported once 12 px from where it started
