"""Multi-object bird tracking with ByteTrack (Ultralytics BYTETracker).

Second stage of the AviSense pipeline:
    Video -> Detection (YOLO) -> Tracking (ByteTrack) -> Feature extraction -> ...

Each bird gets a persistent track ID across frames. Per-frame tracks can be
exported to CSV (one row per bird per frame) as input to feature extraction.

ByteTrack links detections across frames by box overlap (IoU). AirBirds birds are
~7 px and move ~6-10 px per frame, so a bird's boxes in consecutive frames barely
overlap (median IoU ~0.03) and plain ByteTrack never confirms their tracks. The
tracker therefore sees each box enlarged to at least --assoc-size px around its
centre; the reported boxes are the detector's originals. Larger values keep tracks
together in dense flocks and for fast birds, at the cost of more false tracks
(40 px: fewer false alarms; 80 px: higher recall; see README).

Most false detections are static specks (sky texture, horizon clutter) that the
tracker happily follows for hundreds of frames without them moving. A track is
therefore only reported once it has moved --min-motion px from where it was first
seen (it stays reported afterwards, e.g. if the bird lands). This also hides a bird
that never moves at all, such as one standing still the whole time.

Usage (from the project root):
    python -m src.tracking.track --source data/videos/sample.mp4 --show
    python -m src.tracking.track --source data/videos/sample.mp4 \
        --save outputs/tracked.mp4 --csv data/processed/tracks.csv
"""

from __future__ import annotations

import argparse
import csv
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.utils import YAML, IterableSimpleNamespace
from ultralytics.utils.checks import check_yaml

from src.detection.detect import DEFAULT_WEIGHTS, BirdDetector, Detection, iter_frames, source_fps

# ByteTrack keeps low-score detections to extend existing tracks, so the
# detector threshold is lower than for plain detection (Ultralytics default).
DEFAULT_TRACK_CONF = 0.1
# Minimum box side (px) the tracker associates on; see module docstring.
DEFAULT_ASSOC_SIZE = 60.0
# A track is reported only after moving this far (px) from its first position; see module docstring.
DEFAULT_MIN_MOTION = 20.0


@dataclass
class TrackedDetection(Detection):
    track_id: int = -1
    time_s: float = 0.0


class TrackHistory:
    """Recent center points per track ID, for trails and motion features."""

    def __init__(self, maxlen: int = 30) -> None:
        self._points: dict[int, deque[tuple[float, float, float]]] = defaultdict(
            lambda: deque(maxlen=maxlen)
        )

    def update(self, tracks: list[TrackedDetection]) -> None:
        for t in tracks:
            self._points[t.track_id].append((t.time_s, *t.center))

    def points(self, track_id: int) -> list[tuple[float, float, float]]:
        """List of (time_s, cx, cy), oldest first."""
        return list(self._points.get(track_id, ()))

    def active_ids(self) -> list[int]:
        return list(self._points)


def enlarge_boxes(data: np.ndarray, min_size: float) -> np.ndarray:
    """Copy of Boxes data (x1, y1, x2, y2, conf, cls) with each side grown to >= min_size around its centre."""
    out = data.copy()
    c = (data[:, 0:2] + data[:, 2:4]) / 2
    half = np.maximum(data[:, 2:4] - data[:, 0:2], min_size) / 2
    out[:, 0:2], out[:, 2:4] = c - half, c + half
    return out


class BirdTracker:
    """Runs a BirdDetector's YOLO model and links detections with ByteTrack for persistent IDs."""

    def __init__(self, detector: BirdDetector, tracker_cfg: str = "bytetrack.yaml",
                 assoc_size: float = DEFAULT_ASSOC_SIZE, min_motion: float = DEFAULT_MIN_MOTION) -> None:
        self.detector = detector
        self.assoc_size, self.min_motion = assoc_size, min_motion
        self._origin: dict[int, tuple[float, float]] = {}  # first centre of each track not yet moving
        self._moving: set[int] = set()
        cfg = IterableSimpleNamespace(**YAML.load(check_yaml(tracker_cfg)))
        if cfg.tracker_type != "bytetrack":
            raise ValueError(f"Only bytetrack configs are supported, got {cfg.tracker_type!r}")
        self.tracker = BYTETracker(args=cfg)

    def track(self, frame: np.ndarray, frame_idx: int = 0, time_s: float = 0.0) -> list[TrackedDetection]:
        d = self.detector
        result = d.model.predict(d.prepare(frame), conf=d.conf, imgsz=d.imgsz, device=d.device,
                                 classes=d.classes, verbose=False)[0]
        data = result.boxes.data.cpu().numpy()
        out = self.tracker.update(Boxes(enlarge_boxes(data, self.assoc_size), result.orig_shape), frame)
        if len(out) == 0:  # no confirmed tracks (an empty 1-D array)
            return []

        tracks = []
        for tid, det_idx in zip(out[:, 4].astype(int), out[:, -1].astype(int)):  # confirmed tracks only
            x1, y1, x2, y2, conf, cls = data[det_idx]
            if not self._has_moved(int(tid), (x1 + x2) / 2, (y1 + y2) / 2):
                continue
            tracks.append(
                TrackedDetection(frame_idx, float(x1), float(y1), float(x2), float(y2),
                                 float(conf), int(cls), d.names[int(cls)],
                                 track_id=int(tid), time_s=time_s)
            )
        return tracks

    def _has_moved(self, tid: int, cx: float, cy: float) -> bool:
        if tid in self._moving:
            return True
        x0, y0 = self._origin.setdefault(tid, (cx, cy))
        if np.hypot(cx - x0, cy - y0) < self.min_motion:
            return False
        self._moving.add(tid)
        del self._origin[tid]
        return True


def _color_for(track_id: int) -> tuple[int, int, int]:
    rng = np.random.default_rng(track_id)
    return tuple(int(c) for c in rng.integers(64, 256, size=3))


def draw_tracks(frame: np.ndarray, tracks: list[TrackedDetection], history: TrackHistory) -> np.ndarray:
    for t in tracks:
        color = _color_for(t.track_id)
        p1, p2 = (int(t.x1), int(t.y1)), (int(t.x2), int(t.y2))
        cv2.rectangle(frame, p1, p2, color, 2)
        cv2.putText(frame, f"#{t.track_id} {t.confidence:.2f}", (p1[0], max(p1[1] - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        trail = np.array([(x, y) for _, x, y in history.points(t.track_id)], dtype=np.int32)
        if len(trail) > 1:
            cv2.polylines(frame, [trail.reshape(-1, 1, 2)], False, color, 2)
    return frame


CSV_FIELDS = ["frame_idx", "time_s", "track_id", "class_id", "class_name", "confidence",
              "x1", "y1", "x2", "y2", "cx", "cy", "frame_w", "frame_h"]


def run(args: argparse.Namespace) -> None:
    detector = BirdDetector(args.weights, args.conf, args.imgsz, args.device,
                            birds_only=not args.all_classes)
    tracker = BirdTracker(detector, args.tracker, args.assoc_size, args.min_motion)
    history = TrackHistory(maxlen=args.trail)
    fps_src = source_fps(args.source)

    writer = None
    csv_file = csv_writer = None
    if args.csv:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        csv_file = open(args.csv, "w", newline="")
        csv_writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        csv_writer.writeheader()

    all_ids: set[int] = set()
    start = time.perf_counter()
    idx = -1
    try:
        for idx, frame in iter_frames(args.source):
            h, w = frame.shape[:2]
            tracks = tracker.track(frame, idx, time_s=idx / fps_src)
            history.update(tracks)
            all_ids.update(t.track_id for t in tracks)

            if csv_writer:
                for t in tracks:
                    row = {k: v for k, v in asdict(t).items() if k in CSV_FIELDS}
                    row.update(cx=t.center[0], cy=t.center[1], frame_w=w, frame_h=h)
                    csv_writer.writerow(row)

            if args.show or args.save:
                annotated = draw_tracks(frame, tracks, history)
                cv2.putText(annotated, f"tracks: {len(tracks)}  ids seen: {len(all_ids)}", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                if args.save:
                    if writer is None:
                        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
                        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps_src, (w, h))
                    writer.write(annotated)
                if args.show:
                    cv2.imshow("AviSense - tracking (q to quit)", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    finally:
        if writer is not None:
            writer.release()
        if csv_file is not None:
            csv_file.close()
        cv2.destroyAllWindows()

    n_frames = idx + 1
    elapsed = time.perf_counter() - start
    print(f"Processed {n_frames} frames in {elapsed:.1f}s "
          f"({n_frames / max(elapsed, 1e-6):.1f} FPS), {len(all_ids)} unique track IDs.")
    if args.save:
        print(f"Annotated video saved to {args.save}")
    if args.csv:
        print(f"Tracks CSV saved to {args.csv}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AviSense: ByteTrack bird tracking on video.")
    p.add_argument("--source", required=True, help="Video file path, or webcam index (e.g. 0).")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS, help="YOLO weights (.pt).")
    p.add_argument("--conf", type=float, default=DEFAULT_TRACK_CONF, help="Detector confidence threshold.")
    p.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    p.add_argument("--device", default=None, help="'0' for first GPU, 'cpu', or omit for auto.")
    p.add_argument("--tracker", default="bytetrack.yaml", help="ByteTrack config YAML.")
    p.add_argument("--assoc-size", type=float, default=DEFAULT_ASSOC_SIZE,
                   help="Minimum box side (px) used for frame-to-frame matching of tiny birds.")
    p.add_argument("--min-motion", type=float, default=DEFAULT_MIN_MOTION,
                   help="Report a track only after it has moved this many px (0 = report all).")
    p.add_argument("--trail", type=int, default=30, help="Trail length in frames.")
    p.add_argument("--all-classes", action="store_true", help="Do not filter to bird class.")
    p.add_argument("--show", action="store_true", help="Show a live preview window.")
    p.add_argument("--save", default=None, help="Path to save annotated .mp4.")
    p.add_argument("--csv", default=None, help="Path to save per-frame tracks CSV.")
    return p.parse_args(argv)


if __name__ == "__main__":
    run(parse_args())
