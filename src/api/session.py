"""One monitoring run at a time: drives src.pipeline.Pipeline in a background thread and keeps the
latest state (risk, tracks, timeline, frames) for the web UI to poll."""

from __future__ import annotations

import math
import threading
import time
import traceback
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from src.alert_log import AlertLog
from src.detection.detect import iter_frames, source_fps
from src.pipeline import Pipeline
from src.risk_scoring.risk import DEFAULT_CONFIG, FACTORS, RiskConfig
from src.risk_scoring.zones import load_zones

ROOT = Path(__file__).resolve().parents[2]
STREAM_MAX_W = 1280      # frames are sent to the browser at most this wide
JPEG_QUALITY = 85
FRAME_BUFFER = 8         # recent raw frames kept, so the browser can fetch the one matching the state it has
HISTORY_MAX = 20_000     # risk timeline points kept (~13 min at 25 fps)
TRAIL_POINTS = 20


@dataclass
class RunParams:
    source: str                         # path relative to ROOT, or a webcam index such as "0"
    zones: str                          # file name in configs/zones/
    weights: str                        # path relative to ROOT
    imgsz: int = 1920
    conf: float = 0.1
    min_motion: float = 20.0
    min_track_age: int = 3
    start_time: datetime | None = None  # wall-clock time of frame 0 (time-of-day factor)
    risk_weights: dict[str, float] | None = None  # any positive scale; normalised to sum to 1
    medium: float | None = None
    high: float | None = None
    min_duration_s: float | None = None
    merge_gap_s: float | None = None

    def risk_config(self) -> RiskConfig:
        cfg = RiskConfig.load(ROOT / DEFAULT_CONFIG)
        if self.risk_weights:
            total = sum(max(0.0, float(self.risk_weights.get(f, 0))) for f in FACTORS)
            if total <= 0:
                raise ValueError("At least one risk weight must be above 0")
            cfg.weights = {f: max(0.0, float(self.risk_weights.get(f, 0))) / total for f in FACTORS}
        if self.medium is not None:
            cfg.levels["medium"] = float(self.medium)
        if self.high is not None:
            cfg.levels["high"] = float(self.high)
        if not 0 <= cfg.levels["medium"] < cfg.levels["high"] <= 1:
            raise ValueError("Thresholds must satisfy 0 <= medium < high <= 1")
        cfg.alerts = dict(cfg.alerts)
        if self.min_duration_s is not None:
            cfg.alerts["min_duration_s"] = float(self.min_duration_s)
        if self.merge_gap_s is not None:
            cfg.alerts["merge_gap_s"] = float(self.merge_gap_s)
        return cfg


def clean(v):
    """JSON-safe copy: NaN/inf become None, numpy scalars become Python numbers."""
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


@dataclass
class _State:
    status: str = "idle"        # idle | loading | running | finished | stopped | error
    step: str = ""
    error: str = ""
    run_id: int = 0
    params: dict = field(default_factory=dict)
    source: dict = field(default_factory=dict)
    zones: list = field(default_factory=list)
    config: dict = field(default_factory=dict)
    frame: dict = field(default_factory=dict)
    proc_fps: float = 0.0
    risk: dict | None = None
    tracks: list = field(default_factory=list)
    alert: dict | None = None
    alerts_closed: int = 0
    started: float = 0.0
    ended: float = 0.0


class RunSession:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = _State()
        self._history: deque[dict] = deque(maxlen=HISTORY_MAX)
        self._history_base = 0  # index of the first point still kept
        self._frames: OrderedDict[int, np.ndarray] = OrderedDict()  # raw frames; encoded on request
        self._jpeg: tuple[int, bytes] | None = None  # last encoded frame (several tabs may ask for it)

    # ---- control ----
    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, params: RunParams) -> int:
        cfg = params.risk_config()  # validate before starting the thread
        with self._lock:
            if self.busy:
                raise RuntimeError("A run is already in progress; stop it first")
            run_id = self._state.run_id + 1
            self._state = _State(status="loading", step="Loading detector weights", run_id=run_id,
                                 params=clean(_params_dict(params)), started=time.time())
            self._history.clear()
            self._history_base = 0
            self._frames.clear()
            self._jpeg = None
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, args=(params, cfg), daemon=True)
            self._thread.start()
            return run_id

    def stop(self) -> None:
        self._stop.set()

    # ---- read ----
    def snapshot(self, since: int = 0) -> dict:
        with self._lock:
            s = self._state
            first = max(since, self._history_base)
            hist = list(self._history)[first - self._history_base:] if first < self._history_base + len(self._history) else []
            return clean({
                "status": s.status, "step": s.step, "error": s.error, "run_id": s.run_id,
                "params": s.params, "source": s.source, "zones": s.zones, "config": s.config,
                "frame": s.frame, "proc_fps": s.proc_fps, "risk": s.risk, "tracks": s.tracks,
                "alert": s.alert, "alerts_closed": s.alerts_closed,
                "elapsed_s": (s.ended or time.time()) - s.started if s.started else 0.0,
                "history_start": first, "history_len": self._history_base + len(self._history),
                "history": hist,
            })

    def frame_jpeg(self, seq: int | None = None) -> bytes | None:
        """JPEG of frame `seq` if still buffered, else of the newest frame; encoded here, off the worker."""
        with self._lock:
            if not self._frames:
                return None
            if seq is None or seq not in self._frames:
                seq = next(reversed(self._frames))
            if self._jpeg and self._jpeg[0] == seq:
                return self._jpeg[1]
            frame = self._frames[seq]
        h, w = frame.shape[:2]
        scale = min(1.0, STREAM_MAX_W / w)
        if scale < 1:
            frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            return None
        data = jpg.tobytes()
        with self._lock:
            self._jpeg = (seq, data)
        return data

    # ---- worker ----
    def _set(self, **kw) -> None:
        with self._lock:
            for k, v in kw.items():
                setattr(self._state, k, v)

    def _run(self, p: RunParams, cfg: RiskConfig) -> None:
        log = None
        try:
            camera, zones = load_zones(ROOT / "configs" / "zones" / p.zones)
            src = p.source if p.source.isdigit() else str(ROOT / p.source)
            if not p.source.isdigit() and not Path(src).exists():
                raise FileNotFoundError(f"Video not found: {p.source}")
            # A bare name that isn't on disk (e.g. 'yolo11n.pt') is downloaded by Ultralytics.
            weights = str(ROOT / p.weights) if (ROOT / p.weights).exists() else p.weights
            log = AlertLog(self.db_path)
            pipe = Pipeline(zones, cfg, weights, conf=p.conf, imgsz=p.imgsz, alert_log=log,
                            start_time=p.start_time, meta={"source": p.source, "camera": camera},
                            min_track_age=p.min_track_age, min_motion=p.min_motion)

            self._set(step="Opening video source")
            fps = source_fps(src, fallback=25.0)
            cap = cv2.VideoCapture(int(src) if src.isdigit() else src)
            n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if not src.isdigit() else 0
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            self._set(source={"name": Path(p.source).name if not p.source.isdigit() else f"Webcam {p.source}",
                              "path": p.source, "camera": camera, "width": w, "height": h, "fps": fps,
                              "frames": n_frames, "webcam": p.source.isdigit()},
                      zones=[{"name": z.name, "polygon": [list(pt) for pt in z.polygon]} for z in zones],
                      config={"weights": cfg.weights, "levels": cfg.levels, "alerts": cfg.alerts,
                              "smoothing_frames": cfg.smoothing_frames},
                      step="Running detector on the first frames")

            ema, last = 0.0, time.perf_counter()
            for idx, frame in iter_frames(src):
                if self._stop.is_set():
                    break
                t = idx / fps
                res = pipe.process(frame, idx, t)
                now = time.perf_counter()
                inst = 1.0 / max(now - last, 1e-6)
                ema = inst if ema == 0 else 0.9 * ema + 0.1 * inst
                last = now
                self._publish(idx, t, frame, res, pipe, p.start_time, ema)
            pipe.alerts.finish()
            self._set(status="stopped" if self._stop.is_set() else "finished", step="", alert=None,
                      alerts_closed=len(pipe.alerts.closed), ended=time.time())
        except Exception as e:  # surface any failure to the UI instead of dying silently
            traceback.print_exc()
            self._set(status="error", error=f"{type(e).__name__}: {e}", step="", ended=time.time())
        finally:
            if log is not None:
                log.close()

    def _publish(self, idx, t, frame, res, pipe, start_time, fps) -> None:
        h, w = frame.shape[:2]
        r = res.risk
        tracks = []
        for tr in res.tracks:
            trail = [[x / w, y / h] for _, x, y in pipe.history.points(tr.track_id)[-TRAIL_POINTS:]]
            tracks.append({"id": tr.track_id, "conf": tr.confidence,
                           "box": [tr.x1 / w, tr.y1 / h, tr.x2 / w, tr.y2 / h], "trail": trail})
        wall = (start_time + timedelta(seconds=t)).isoformat(timespec="seconds") if start_time else None
        point = {"t": round(t, 3), "s": round(r.score, 4), "l": r.level, "n": int(r.features["count"])}
        with self._lock:
            self._frames[idx] = frame  # iter_frames yields a new array per frame, nothing writes to it
            while len(self._frames) > FRAME_BUFFER:
                self._frames.popitem(last=False)
            if len(self._history) == self._history.maxlen:
                self._history_base += 1
            self._history.append(point)
            s = self._state
            s.status, s.step, s.proc_fps = "running", "", fps
            s.frame = {"seq": idx, "idx": idx, "t": t, "wallclock": wall}
            s.risk = {"score": r.score, "raw": r.raw, "level": r.level, "top_factor": r.top_factor,
                      "contributions": r.contributions,
                      "features": {k: r.features.get(k) for k in ("count", "flock_size", "n_flocks", "max_speed",
                                                                  "mean_speed", "min_dist_to_zone", "n_in_zone",
                                                                  "n_approaching")}}
            s.tracks = tracks
            s.alert = res.alert
            s.alerts_closed = len(pipe.alerts.closed)


def _params_dict(p: RunParams) -> dict:
    d = dict(p.__dict__)
    d["start_time"] = p.start_time.isoformat() if p.start_time else None
    return d
