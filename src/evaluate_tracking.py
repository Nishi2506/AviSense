"""Score detector + tracker output against AirBirds ground truth on a frame sequence.

Runs the same BirdTracker the pipeline uses over consecutive labelled frames, then
matches tracked boxes to ground-truth boxes per frame (centre distance <= --max-dist px;
birds are too small for IoU matching) and reports, for each combination of detection
confidence, minimum track age and minimum movement (the pipeline's --conf,
min_track_age and --min-motion knobs):

    precision        tracked boxes that are real birds
    recall           ground-truth birds that are tracked
    false-alarm frames   frames with at least one tracked box that is not a bird
    missed frames    frames with birds but no correct track

Usage (from the project root):
    python -m src.evaluate_tracking --images data/raw/airbirds/images/test --labels data/raw/airbirds/labels/test \
        --prefix D02_20210628090856 --weights models/airbirds_tiles_yolo11n_640.pt --imgsz 1920 \
        --tracks-csv data/processed/D02_20210628090856_eval_tracks.csv
The tracks CSV is reused on later runs, so changing only the thresholds is instant.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from src.detection.detect import BirdDetector
from src.frames_to_video import find_sequence
from src.tracking.track import DEFAULT_ASSOC_SIZE, DEFAULT_TRACK_CONF, BirdTracker


def collect_tracks(frames: list[tuple[int, Path]], weights: str, imgsz: int, conf: float,
                   assoc_size: float, device: str | None = None) -> pd.DataFrame:
    # min_motion=0: keep every track; the motion filter is applied afterwards in score()
    tracker = BirdTracker(BirdDetector(weights, conf, imgsz, device), assoc_size=assoc_size, min_motion=0)
    rows = []
    for i, (n, path) in enumerate(frames):
        for t in tracker.track(cv2.imread(str(path)), n):
            rows.append(dict(frame=n, track_id=t.track_id, confidence=t.confidence,
                             cx=t.center[0], cy=t.center[1]))
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(frames)} frames")
    return add_track_state(pd.DataFrame(rows, columns=["frame", "track_id", "confidence", "cx", "cy"]))


def add_track_state(df: pd.DataFrame) -> pd.DataFrame:
    """Per row: frames since the track was first seen, and its largest distance so far from where it started."""
    df = df.sort_values(["track_id", "frame"])
    g = df.groupby("track_id")
    df["age"] = df["frame"] - g["frame"].transform("min")
    dist = np.hypot(df["cx"] - g["cx"].transform("first"), df["cy"] - g["cy"].transform("first"))
    df["motion"] = dist.groupby(df["track_id"]).cummax()
    return df.sort_values(["frame", "track_id"]).reset_index(drop=True)


def load_gt(frames: list[tuple[int, Path]], labels: Path, frame_w: int, frame_h: int) -> dict[int, np.ndarray]:
    """Ground-truth box centres (pixels) per frame number."""
    gt = {}
    for n, path in frames:
        f = labels / f"{path.stem}.txt"
        vals = [list(map(float, l.split()[1:3])) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
        gt[n] = np.array(vals, dtype=float).reshape(-1, 2) * [frame_w, frame_h]
    return gt


def match_frame(pred: np.ndarray, gt: np.ndarray, max_dist: float) -> int:
    """Greedy one-to-one matching by centre distance; returns the number of matches."""
    if len(pred) == 0 or len(gt) == 0:
        return 0
    d = np.linalg.norm(pred[:, None, :] - gt[None, :, :], axis=2)
    matched = 0
    while True:
        i, j = np.unravel_index(np.argmin(d), d.shape)
        if d[i, j] > max_dist:
            return matched
        matched += 1
        d[i, :] = np.inf
        d[:, j] = np.inf


def score(tracks: pd.DataFrame, gt: dict[int, np.ndarray], min_conf: float, min_age: int,
          max_dist: float, min_motion: float = 0.0) -> dict:
    kept = tracks[(tracks["confidence"] >= min_conf) & (tracks["age"] >= min_age)
                  & (tracks["motion"] >= min_motion)]
    by_frame = {n: g[["cx", "cy"]].to_numpy() for n, g in kept.groupby("frame")}
    tp = n_pred = n_gt = fa_frames = miss_frames = bird_frames = 0
    for n, g in gt.items():
        p = by_frame.get(n, np.empty((0, 2)))
        m = match_frame(p, g, max_dist)
        tp, n_pred, n_gt = tp + m, n_pred + len(p), n_gt + len(g)
        fa_frames += len(p) > m
        if len(g):
            bird_frames += 1
            miss_frames += m == 0
    return dict(min_conf=min_conf, min_age=min_age, min_motion=min_motion, precision=tp / max(n_pred, 1), recall=tp / max(n_gt, 1),
                false_alarm_frames=fa_frames / len(gt), missed_bird_frames=miss_frames / max(bird_frames, 1),
                tracked=n_pred)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Evaluate detection + tracking against AirBirds labels.")
    p.add_argument("--images", required=True, help="Folder of frames.")
    p.add_argument("--labels", required=True, help="Folder of YOLO label files.")
    p.add_argument("--prefix", required=True, help="Sequence prefix before _<frame number>.")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--count", type=int, default=None)
    p.add_argument("--weights", default="models/airbirds_tiles_yolo11n_640.pt")
    p.add_argument("--imgsz", type=int, default=1920)
    p.add_argument("--conf", type=float, default=DEFAULT_TRACK_CONF, help="Detector confidence while tracking.")
    p.add_argument("--assoc-size", type=float, default=DEFAULT_ASSOC_SIZE)
    p.add_argument("--device", default=None)
    p.add_argument("--tracks-csv", default=None, help="Cache of tracker output (read if it exists, else written).")
    p.add_argument("--max-dist", type=float, default=15.0, help="Match radius in pixels.")
    p.add_argument("--min-conf", type=float, nargs="+", default=[0.1, 0.2, 0.3, 0.4, 0.5])
    p.add_argument("--min-age", type=int, nargs="+", default=[0, 3, 5, 10, 20])
    p.add_argument("--min-motion", type=float, nargs="+", default=[0.0],
                   help="Minimum movement (px) from where a track started.")
    p.add_argument("--out", default=None, help="Write the results table to this CSV.")
    args = p.parse_args(argv)

    frames = [(n, f) for n, f in find_sequence(Path(args.images), args.prefix) if n >= args.start]
    frames = frames[:args.count] if args.count else frames
    h, w = cv2.imread(str(frames[0][1])).shape[:2]

    if args.tracks_csv and Path(args.tracks_csv).exists():
        tracks = add_track_state(pd.read_csv(args.tracks_csv))
        print(f"Loaded {len(tracks)} tracked boxes from {args.tracks_csv}")
    else:
        print(f"Tracking {len(frames)} frames ...")
        tracks = collect_tracks(frames, args.weights, args.imgsz, args.conf, args.assoc_size, args.device)
        if args.tracks_csv:
            Path(args.tracks_csv).parent.mkdir(parents=True, exist_ok=True)
            tracks.to_csv(args.tracks_csv, index=False)
    gt = load_gt(frames, Path(args.labels), w, h)

    res = pd.DataFrame([score(tracks, gt, c, a, args.max_dist, m)
                        for m in args.min_motion for c in args.min_conf for a in args.min_age])
    print(f"\n{len(frames)} frames, {sum(len(g) for g in gt.values())} ground-truth birds, "
          f"{sum(1 for g in gt.values() if len(g))} frames with birds")
    print(res.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    if args.out:
        res.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
