"""Feature extraction from bird tracks (output of src.tracking.track --csv).

Third stage of the AviSense pipeline:
    ... -> Tracking -> Feature extraction -> Risk scoring -> ...

Distances and speeds are normalised by the frame diagonal ("diag"), so values
are resolution independent: speed 0.1 = moving 10% of the diagonal per second.

Per-track features (one row per bird per frame):
    speed, heading_deg, dist_to_zone, in_zone, approach_rate, track_age
Per-frame features (one row per frame, input to the risk score):
    count, flock_size, n_flocks, max_speed, mean_speed, min_dist_to_zone,
    n_in_zone, n_approaching, hour

Usage (from the project root):
    python -m src.risk_scoring.features --tracks data/processed/tracks.csv \
        --zones configs/zones/D02.json --out data/processed/frame_features.csv \
        --start-time 2021-06-28T09:08:56
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.risk_scoring.zones import Zone, distance_to_zones, load_zones


def track_features(tracks: pd.DataFrame, zones: list[Zone], window: int = 5) -> pd.DataFrame:
    """Add motion and zone features to each tracked detection.

    Motion is measured over the last `window` frames of the same track (or
    since the track started, if younger) to smooth out box jitter.
    """
    df = tracks.sort_values(["track_id", "frame_idx"]).reset_index(drop=True)
    diag = np.hypot(df["frame_w"], df["frame_h"])

    df["dist_to_zone"] = [
        distance_to_zones(x, y, zones, w, h)
        for x, y, w, h in zip(df["cx"], df["cy"], df["frame_w"], df["frame_h"])
    ] / diag
    df["in_zone"] = df["dist_to_zone"] == 0

    g = df.groupby("track_id")
    df["track_age"] = g.cumcount()  # frames since the track was first seen
    ref = {c: g[c].shift(window).fillna(g[c].transform("first"))
           for c in ("cx", "cy", "time_s", "dist_to_zone")}

    dt = df["time_s"] - ref["time_s"]
    dx = df["cx"] - ref["cx"]
    dy = df["cy"] - ref["cy"]
    moving = dt > 0

    df["speed"] = np.where(moving, np.hypot(dx, dy) / diag / dt.where(moving, 1), 0.0)
    # Image y points down; negate so 90 deg = moving up the frame.
    df["heading_deg"] = np.where(moving & ((dx != 0) | (dy != 0)),
                                 np.degrees(np.arctan2(-dy, dx)) % 360, np.nan)
    df["approach_rate"] = np.where(moving, (ref["dist_to_zone"] - df["dist_to_zone"]) / dt.where(moving, 1), 0.0)
    return df


def _flocks(points: np.ndarray, radius: float) -> tuple[int, int]:
    """(largest flock size, number of flocks) for points within `radius` of each other."""
    if len(points) == 0:
        return 0, 0
    adjacent = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1) <= radius
    unvisited = set(range(len(points)))
    sizes = []
    while unvisited:  # flood-fill each connected group of nearby birds
        stack = [unvisited.pop()]
        size = 0
        while stack:
            i = stack.pop()
            size += 1
            for j in np.flatnonzero(adjacent[i]):
                if j in unvisited:
                    unvisited.remove(j)
                    stack.append(j)
        sizes.append(size)
    return max(sizes), len(sizes)


FRAME_COLUMNS = ["frame_idx", "time_s", "count", "flock_size", "n_flocks", "max_speed",
                 "mean_speed", "min_dist_to_zone", "n_in_zone", "n_approaching"]


def aggregate_frame(f: pd.DataFrame, flock_radius: float = 0.05) -> dict:
    """Per-frame features from one frame's per-track feature rows (may be empty)."""
    if f.empty:
        return {"count": 0, "flock_size": 0, "n_flocks": 0, "max_speed": 0.0, "mean_speed": 0.0,
                "min_dist_to_zone": np.nan, "n_in_zone": 0, "n_approaching": 0}
    diag = float(np.hypot(f["frame_w"].iloc[0], f["frame_h"].iloc[0]))
    flock_size, n_flocks = _flocks(f[["cx", "cy"]].to_numpy() / diag, flock_radius)
    return {
        "count": len(f),
        "flock_size": flock_size,
        "n_flocks": n_flocks,
        "max_speed": float(f["speed"].max()),
        "mean_speed": float(f["speed"].mean()),
        "min_dist_to_zone": float(f["dist_to_zone"].min()),
        "n_in_zone": int(f["in_zone"].sum()),
        "n_approaching": int((f["approach_rate"] > 0).sum()),
    }


def hour_of_day(start_time: datetime, time_s: float) -> float:
    t = start_time + timedelta(seconds=float(time_s))
    return t.hour + t.minute / 60


def frame_features(
    tf: pd.DataFrame,
    flock_radius: float = 0.05,
    min_track_age: int = 0,
    start_time: datetime | None = None,
    n_frames: int | None = None,
) -> pd.DataFrame:
    """Aggregate per-track features into one row per frame.

    flock_radius: birds within this distance (fraction of diagonal) chain into one flock.
    min_track_age: ignore tracks seen for fewer frames than this (filters flicker).
    n_frames: total frames in the video, so trailing frames with no birds are included.
    """
    tf = tf[tf["track_age"] >= min_track_age]
    rows = [aggregate_frame(f, flock_radius) | {"frame_idx": frame_idx, "time_s": f["time_s"].iloc[0]}
            for frame_idx, f in tf.groupby("frame_idx")]
    ff = pd.DataFrame(rows, columns=FRAME_COLUMNS)

    # Include frames with no birds so the timeline has no gaps.
    last = (n_frames - 1) if n_frames else int(tf["frame_idx"].max()) if len(tf) else -1
    ff = ff.set_index("frame_idx").reindex(range(last + 1))
    ff[["count", "flock_size", "n_flocks", "n_in_zone", "n_approaching"]] = (
        ff[["count", "flock_size", "n_flocks", "n_in_zone", "n_approaching"]].fillna(0).astype(int))
    ff[["max_speed", "mean_speed"]] = ff[["max_speed", "mean_speed"]].fillna(0.0)
    # min_dist_to_zone stays NaN when there are no birds (no distance to measure).
    fps = _infer_fps(tf)
    ff["time_s"] = ff["time_s"].fillna(pd.Series(ff.index / fps, index=ff.index)) if fps else ff["time_s"]
    ff = ff.reset_index().rename(columns={"index": "frame_idx"})

    if start_time is not None:
        ff["hour"] = [hour_of_day(start_time, t) for t in ff["time_s"]]
    return ff


def _infer_fps(tf: pd.DataFrame) -> float | None:
    f = tf[tf["frame_idx"] > 0]
    if f.empty:
        return None
    r = (f["frame_idx"] / f["time_s"]).median()
    return float(r) if np.isfinite(r) and r > 0 else None


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="AviSense: extract risk features from a tracks CSV.")
    p.add_argument("--tracks", required=True, help="Tracks CSV from src.tracking.track --csv.")
    p.add_argument("--zones", required=True, help="Zones JSON from src.risk_scoring.zone_editor.")
    p.add_argument("--out", required=True, help="Output per-frame features CSV.")
    p.add_argument("--track-out", default=None, help="Optional per-track features CSV.")
    p.add_argument("--window", type=int, default=5, help="Frames used to measure motion.")
    p.add_argument("--flock-radius", type=float, default=0.05, help="Flock linking distance (fraction of diagonal).")
    p.add_argument("--min-track-age", type=int, default=0, help="Ignore tracks younger than this many frames.")
    p.add_argument("--start-time", default=None, help="Wall-clock time of frame 0, ISO format, for the hour feature.")
    args = p.parse_args(argv)

    _, zones = load_zones(args.zones)
    tracks = pd.read_csv(args.tracks)
    tf = track_features(tracks, zones, args.window)
    ff = frame_features(tf, args.flock_radius, args.min_track_age,
                        datetime.fromisoformat(args.start_time) if args.start_time else None)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    ff.to_csv(args.out, index=False)
    print(f"{len(tracks)} track rows -> {len(ff)} frames of features saved to {args.out}")
    if args.track_out:
        tf.to_csv(args.track_out, index=False)
        print(f"Per-track features saved to {args.track_out}")


if __name__ == "__main__":
    main()
