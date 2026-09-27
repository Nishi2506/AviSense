"""End-to-end AviSense pipeline, frame by frame (used by the dashboard).

    Video -> Detection -> Tracking -> Features -> Risk score -> Level -> Alerts

Usage (from the project root):
    python -m src.pipeline --source data/videos/sample.mp4 --zones configs/zones/cam1.json --show
    python -m src.pipeline --source data/videos/sample.mp4 --zones configs/zones/cam1.json \
        --save outputs/pipeline.mp4 --db outputs/alerts.db --start-time 2021-06-28T09:08:56
"""

from __future__ import annotations

import argparse
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
import pandas as pd

from src.alert_log import AlertLog
from src.detection.detect import DEFAULT_WEIGHTS, BirdDetector, iter_frames, source_fps
from src.risk_scoring.features import aggregate_frame, hour_of_day, track_features
from src.risk_scoring.risk import DEFAULT_CONFIG, FACTORS, LEVELS, RiskConfig, classify, score
from src.risk_scoring.zones import Zone, draw_zones, load_zones
from src.tracking.track import DEFAULT_TRACK_CONF, BirdTracker, TrackedDetection, TrackHistory, draw_tracks

LEVEL_COLORS = {"Low": (80, 175, 76), "Medium": (0, 165, 255), "High": (40, 40, 220)}  # BGR


def parse_start_time(source: str) -> datetime | None:
    """Wall-clock start from a YYYYMMDDhhmmss stamp in the filename (AirBirds style)."""
    m = re.search(r"(\d{14})", Path(str(source)).stem)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    except ValueError:
        return None


@dataclass
class FrameRisk:
    features: dict
    score: float           # smoothed
    raw: float             # this frame only
    level: str
    top_factor: str
    contributions: dict[str, float]


class OnlineRiskEngine:
    """Computes features and risk for each new frame from a short sliding window of tracks."""

    def __init__(self, zones: list[Zone], cfg: RiskConfig, window: int = 5, flock_radius: float = 0.05,
                 min_track_age: int = 0, start_time: datetime | None = None) -> None:
        self.zones, self.cfg = zones, cfg
        self.window, self.flock_radius, self.min_track_age = window, flock_radius, min_track_age
        self.start_time = start_time
        self._frames: deque[list[dict]] = deque(maxlen=window + 1)
        self._first_seen: dict[int, int] = {}
        self._last_seen: dict[int, int] = {}
        self._scores: deque[float] = deque(maxlen=max(1, cfg.smoothing_frames))

    def update(self, tracks: list[TrackedDetection], frame_idx: int, time_s: float,
               frame_w: int, frame_h: int) -> FrameRisk:
        rows = [dict(frame_idx=frame_idx, time_s=time_s, track_id=t.track_id,
                     cx=t.center[0], cy=t.center[1], frame_w=frame_w, frame_h=frame_h) for t in tracks]
        self._frames.append(rows)
        for t in tracks:
            self._first_seen.setdefault(t.track_id, frame_idx)
            self._last_seen[t.track_id] = frame_idx
        self._prune(frame_idx)

        if rows:
            tf = track_features(pd.DataFrame([r for f in self._frames for r in f]), self.zones, self.window)
            cur = tf[tf["frame_idx"] == frame_idx].copy()
            cur["track_age"] = [frame_idx - self._first_seen[t] for t in cur["track_id"]]
            feats = aggregate_frame(cur[cur["track_age"] >= self.min_track_age], self.flock_radius)
        else:
            feats = aggregate_frame(pd.DataFrame())
        feats.update(frame_idx=frame_idx, time_s=time_s)
        if self.start_time is not None:
            feats["hour"] = hour_of_day(self.start_time, time_s)

        r = score(pd.DataFrame([feats]), self.cfg).iloc[0]  # one row: rolling mean == raw
        self._scores.append(float(r["risk_raw"]))
        smoothed = float(np.mean(self._scores))
        return FrameRisk(feats, smoothed, float(r["risk_raw"]), classify(smoothed, self.cfg),
                         r["top_factor"], {f: float(r[f"c_{f}"]) for f in FACTORS})

    def _prune(self, frame_idx: int, keep_frames: int = 300) -> None:
        stale = [t for t, last in self._last_seen.items() if frame_idx - last > keep_frames]
        for t in stale:
            del self._first_seen[t], self._last_seen[t]


@dataclass
class _Episode:
    start_s: float
    start_frame: int
    end_s: float = 0.0
    end_frame: int = 0
    peak_score: float = 0.0
    peak_level: str = "Low"
    max_count: int = 0
    contrib: dict[str, float] = field(default_factory=lambda: dict.fromkeys(FACTORS, 0.0))
    alert_id: int | None = None

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def as_record(self, status: str) -> dict:
        return dict(start_s=self.start_s, end_s=self.end_s, duration_s=self.duration_s,
                    start_frame=self.start_frame, end_frame=self.end_frame, peak_score=self.peak_score,
                    peak_level=self.peak_level, top_factor=max(self.contrib, key=self.contrib.get),
                    max_count=self.max_count, status=status)


class AlertTracker:
    """Online version of risk.alert_episodes: same min level, merge gap and min duration rules."""

    def __init__(self, cfg: RiskConfig, log: AlertLog | None = None, meta: dict | None = None,
                 start_time: datetime | None = None) -> None:
        a = cfg.alerts
        self.min_rank = LEVELS.index(a.get("min_level", "Medium"))
        self.merge_gap = a.get("merge_gap_s", 0.0)
        self.min_duration = a.get("min_duration_s", 0.0)
        self.log, self.meta, self.start_time = log, meta or {}, start_time
        self.current: _Episode | None = None
        self.closed: list[dict] = []

    @property
    def active(self) -> dict | None:
        """The current episode once it has lasted min_duration_s, else None."""
        ep = self.current
        return ep.as_record("active") if ep and ep.duration_s >= self.min_duration else None

    def update(self, frame_idx: int, time_s: float, risk: FrameRisk) -> None:
        ep = self.current
        if ep and time_s - ep.end_s > self.merge_gap:
            self._close()
            ep = None
        if LEVELS.index(risk.level) < self.min_rank:
            return
        if ep is None:
            ep = self.current = _Episode(start_s=time_s, start_frame=frame_idx)
        ep.end_s, ep.end_frame = time_s, frame_idx
        if risk.score > ep.peak_score:
            ep.peak_score, ep.peak_level = risk.score, risk.level
        ep.max_count = max(ep.max_count, risk.features["count"])
        for f, c in risk.contributions.items():
            ep.contrib[f] += c
        if ep.duration_s >= self.min_duration:
            self._write(ep, "active")

    def finish(self) -> None:
        if self.current:
            self._close()

    def _close(self) -> None:
        ep, self.current = self.current, None
        if ep.duration_s >= self.min_duration:
            self.closed.append(self._write(ep, "closed"))

    def _write(self, ep: _Episode, status: str) -> dict:
        rec = ep.as_record(status) | self.meta
        if self.start_time is not None:
            rec["started_at"] = (self.start_time + timedelta(seconds=float(ep.start_s))).isoformat()
        if self.log is not None:
            ep.alert_id = self.log.upsert(rec, ep.alert_id)
        return rec


@dataclass
class FrameResult:
    frame_idx: int
    time_s: float
    tracks: list[TrackedDetection]
    risk: FrameRisk
    alert: dict | None
    annotated: np.ndarray


class Pipeline:
    def __init__(self, zones: list[Zone], cfg: RiskConfig, weights: str = DEFAULT_WEIGHTS,
                 conf: float = DEFAULT_TRACK_CONF, imgsz: int = 640, device: str | None = None,
                 tracker_cfg: str = "bytetrack.yaml", alert_log: AlertLog | None = None,
                 start_time: datetime | None = None, meta: dict | None = None,
                 birds_only: bool = True, min_track_age: int = 0) -> None:
        self.zones = zones
        self.tracker = BirdTracker(BirdDetector(weights, conf, imgsz, device, birds_only), tracker_cfg)
        self.history = TrackHistory()
        self.engine = OnlineRiskEngine(zones, cfg, start_time=start_time, min_track_age=min_track_age)
        self.alerts = AlertTracker(cfg, alert_log, meta, start_time)

    def process(self, frame: np.ndarray, frame_idx: int, time_s: float) -> FrameResult:
        h, w = frame.shape[:2]
        tracks = self.tracker.track(frame, frame_idx, time_s)
        self.history.update(tracks)
        risk = self.engine.update(tracks, frame_idx, time_s, w, h)
        self.alerts.update(frame_idx, time_s, risk)
        alert = self.alerts.active

        annotated = draw_zones(frame, self.zones)
        annotated = draw_tracks(annotated, tracks, self.history)
        draw_risk_banner(annotated, risk, alert is not None)
        return FrameResult(frame_idx, time_s, tracks, risk, alert, annotated)

    def run(self, source: str) -> Iterator[FrameResult]:
        fps = source_fps(source)
        try:
            for idx, frame in iter_frames(source):
                yield self.process(frame, idx, idx / fps)
        finally:
            self.alerts.finish()


def draw_risk_banner(frame: np.ndarray, risk: FrameRisk, alerting: bool) -> None:
    color = LEVEL_COLORS[risk.level]
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), color, -1)
    why = f" - {risk.top_factor}" if risk.top_factor else ""
    text = f"{'ALERT  ' if alerting else ''}RISK {risk.level.upper()} {risk.score:.2f}{why}   birds: {risk.features['count']}"
    cv2.putText(frame, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="AviSense end-to-end pipeline.")
    p.add_argument("--source", required=True, help="Video file path, or webcam index.")
    p.add_argument("--zones", required=True, help="Zones JSON (src.risk_scoring.zone_editor).")
    p.add_argument("--config", default=DEFAULT_CONFIG, help="Risk config YAML.")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS, help="YOLO weights (.pt).")
    p.add_argument("--conf", type=float, default=DEFAULT_TRACK_CONF, help="Detector confidence threshold.")
    p.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    p.add_argument("--device", default=None, help="'0' for first GPU, 'cpu', or omit for auto.")
    p.add_argument("--start-time", default=None,
                   help="Wall-clock time of frame 0 (ISO). Default: parsed from filename if present.")
    p.add_argument("--db", default=None, help="SQLite file to log alerts to (e.g. outputs/alerts.db).")
    p.add_argument("--all-classes", action="store_true", help="Do not filter to bird class.")
    p.add_argument("--show", action="store_true", help="Show a live preview window.")
    p.add_argument("--save", default=None, help="Path to save annotated .mp4.")
    args = p.parse_args(argv)

    camera, zones = load_zones(args.zones)
    start = datetime.fromisoformat(args.start_time) if args.start_time else parse_start_time(args.source)
    log = AlertLog(args.db) if args.db else None
    pipe = Pipeline(zones, RiskConfig.load(args.config), args.weights, args.conf, args.imgsz, args.device,
                    alert_log=log, start_time=start, meta={"source": str(args.source), "camera": camera},
                    birds_only=not args.all_classes)

    writer = None
    counts = dict.fromkeys(LEVELS, 0)
    t0 = time.perf_counter()
    n = 0
    try:
        for res in pipe.run(args.source):
            n += 1
            counts[res.risk.level] += 1
            if args.save:
                if writer is None:
                    Path(args.save).parent.mkdir(parents=True, exist_ok=True)
                    h, w = res.annotated.shape[:2]
                    writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), source_fps(args.source), (w, h))
                writer.write(res.annotated)
            if args.show:
                cv2.imshow("AviSense (q to quit)", res.annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        pipe.alerts.finish()  # close any open episode, also when quitting early
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

    elapsed = time.perf_counter() - t0
    print(f"Processed {n} frames in {elapsed:.1f}s ({n / max(elapsed, 1e-6):.1f} FPS). Levels: {counts}")
    print(f"{len(pipe.alerts.closed)} alert episode(s)" + (f", logged to {args.db}" if args.db else ""))
    for a in pipe.alerts.closed:
        print(f"  {a['start_s']:.1f}-{a['end_s']:.1f}s  peak {a['peak_level']} {a['peak_score']:.2f}  "
              f"driver: {a['top_factor']}  max birds: {a['max_count']}")
    if log:
        log.close()


if __name__ == "__main__":
    main()
