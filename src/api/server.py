"""AviSense web API + UI server.

Run from the project root:
    python -m src.api.server                 # http://127.0.0.1:8000 (serves frontend/dist if built)
    python -m src.api.server --port 8080

The React UI lives in frontend/ (npm run dev for development, npm run build to produce frontend/dist).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import cv2
import yaml
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from src.alert_log import DEFAULT_DB, AlertLog
from src.api import results as res
from src.api.session import ROOT, RunParams, RunSession, clean
from src.pipeline import parse_start_time
from src.risk_scoring.risk import DEFAULT_CONFIG
from src.tracking.track import DEFAULT_ASSOC_SIZE, DEFAULT_MIN_MOTION, DEFAULT_TRACK_CONF

VIDEO_DIR = ROOT / "data" / "videos"
ZONES_DIR = ROOT / "configs" / "zones"
MODELS_DIR = ROOT / "models"
DIST = ROOT / "frontend" / "dist"
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}
DB = ROOT / DEFAULT_DB

session = RunSession(DB)


# ---------- helpers ----------
def list_videos() -> list[str]:
    return sorted(p.relative_to(ROOT).as_posix() for p in VIDEO_DIR.rglob("*") if p.suffix.lower() in VIDEO_EXTS)


def list_zones() -> list[str]:
    return sorted(p.name for p in ZONES_DIR.glob("*.json"))


def list_weights() -> list[str]:
    found = sorted(p.relative_to(ROOT).as_posix() for p in MODELS_DIR.glob("*.pt"))
    return found + (["yolo11n.pt"] if (ROOT / "yolo11n.pt").exists() else [])


def video_path(rel: str) -> Path:
    p = (ROOT / rel).resolve()
    if p.suffix.lower() not in VIDEO_EXTS or VIDEO_DIR.resolve() not in p.parents or not p.exists():
        raise HTTPException(404, f"Unknown video: {rel}")
    return p


def suggest_zones(video: str, zones: list[str]) -> str | None:
    """Zones file whose camera name appears in the video file name (e.g. D02 -> D02.json)."""
    stem = Path(video).stem.lower()
    for z in zones:
        if Path(z).stem.lower() in stem:
            return z
    return None


@lru_cache(maxsize=1)
def system_info() -> dict:
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:  # torch missing or blocked: report CPU
        gpu = None
    return {"gpu": gpu, "device": "CUDA" if gpu else "CPU"}


def video_meta(p: Path) -> dict:
    cap = cv2.VideoCapture(str(p))
    meta = {"width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": cap.get(cv2.CAP_PROP_FPS) or None, "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}
    cap.release()
    return meta


# ---------- routes ----------
async def config(request: Request) -> JSONResponse:
    videos, zones = list_videos(), list_zones()
    risk_cfg = yaml.safe_load((ROOT / DEFAULT_CONFIG).read_text())
    weights = list_weights()
    return JSONResponse(clean({
        "videos": [{"path": v, "name": Path(v).name, "zones": suggest_zones(v, zones),
                    "start_time": (t.isoformat() if (t := parse_start_time(v)) else None), **video_meta(ROOT / v)}
                   for v in videos],
        "zones": zones,
        "weights": weights,
        "defaults": {"weights": res.BEST_WEIGHTS if res.BEST_WEIGHTS in weights else (weights[0] if weights else None),
                     "imgsz": 1920, "conf": DEFAULT_TRACK_CONF, "min_motion": DEFAULT_MIN_MOTION, "min_track_age": 3},
        "risk": risk_cfg,
        "tracker": {"assoc_size": DEFAULT_ASSOC_SIZE, "min_motion": DEFAULT_MIN_MOTION, "conf": DEFAULT_TRACK_CONF},
        "system": system_info(),
    }))


async def zone_file(request: Request) -> JSONResponse:
    name = request.path_params["name"]
    if name not in list_zones():
        raise HTTPException(404, f"Unknown zones file: {name}")
    return JSONResponse(json.loads((ZONES_DIR / name).read_text()))


async def video_frame(request: Request) -> Response:
    """One frame of a video as JPEG (for the zone viewer)."""
    p = video_path(request.query_params.get("path", ""))
    cap = cv2.VideoCapture(str(p))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(request.query_params.get("frame", 0)))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise HTTPException(404, "Could not read a frame from this video")
    ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return Response(jpg.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


async def upload_video(request: Request) -> JSONResponse:
    form = await request.form()
    f = form.get("file")
    if f is None or not getattr(f, "filename", ""):
        raise HTTPException(400, "No file uploaded")
    name = Path(f.filename).name
    if Path(name).suffix.lower() not in VIDEO_EXTS:
        raise HTTPException(400, f"Unsupported video type: {Path(name).suffix}")
    dest = VIDEO_DIR / "uploads" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        while chunk := await f.read(1 << 20):
            out.write(chunk)
    return JSONResponse({"path": dest.relative_to(ROOT).as_posix()})


async def run(request: Request) -> JSONResponse:
    body = await request.json()
    source = str(body.get("source", ""))
    if not source.isdigit():
        video_path(source)  # 404 if not a known video
    if body.get("zones") not in list_zones():
        raise HTTPException(400, "Choose a runway zones file")
    if body.get("weights") not in list_weights():
        raise HTTPException(400, "Unknown detector weights")
    start = body.get("start_time")
    try:
        start_time = datetime.fromisoformat(start) if start else None
    except ValueError:
        raise HTTPException(400, f"Bad start time: {start}")
    try:
        params = RunParams(
            source=source, zones=body["zones"], weights=body["weights"],
            imgsz=int(body.get("imgsz", 1920)), conf=float(body.get("conf", DEFAULT_TRACK_CONF)),
            min_motion=float(body.get("min_motion", DEFAULT_MIN_MOTION)),
            min_track_age=int(body.get("min_track_age", 3)), start_time=start_time,
            risk_weights=body.get("risk_weights"), medium=body.get("medium"), high=body.get("high"),
            min_duration_s=body.get("min_duration_s"), merge_gap_s=body.get("merge_gap_s"))
        run_id = session.start(params)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(409 if isinstance(e, RuntimeError) else 400, str(e))
    return JSONResponse({"run_id": run_id})


async def stop(request: Request) -> JSONResponse:
    session.stop()
    return JSONResponse({"ok": True})


async def state(request: Request) -> JSONResponse:
    return JSONResponse(session.snapshot(int(request.query_params.get("since", 0))))


async def frame(request: Request) -> Response:
    seq = request.query_params.get("seq")
    jpg = session.frame_jpeg(int(seq) if seq and seq.isdigit() else None)
    if jpg is None:
        return Response(status_code=204)
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


async def alerts(request: Request) -> JSONResponse:
    limit = min(int(request.query_params.get("limit", 500)), 5000)
    log = AlertLog(DB)
    try:
        df, total = log.recent(limit), log.count()
    finally:
        log.close()
    return JSONResponse(clean({"total": total, "alerts": df.to_dict(orient="records")}))


async def results(request: Request) -> JSONResponse:
    return JSONResponse(clean(res.results()))


async def result_image(request: Request) -> Response:
    p = res.image_path(request.path_params["key"])
    if p is None:
        raise HTTPException(404, "Figure not found")
    return FileResponse(p)


async def api_not_found(request: Request) -> JSONResponse:
    return JSONResponse({"detail": "Not found"}, status_code=404)


async def http_error(request: Request, exc: HTTPException) -> Response:
    if request.url.path.startswith("/api/") or exc.status_code != 404 or not (DIST / "index.html").exists():
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return FileResponse(DIST / "index.html")  # client-side routes (/live, /alerts, ...) load the app


routes = [
    Route("/api/config", config),
    Route("/api/zones/{name}", zone_file),
    Route("/api/videos/frame", video_frame),
    Route("/api/videos", upload_video, methods=["POST"]),
    Route("/api/run", run, methods=["POST"]),
    Route("/api/stop", stop, methods=["POST"]),
    Route("/api/state", state),
    Route("/api/frame.jpg", frame),
    Route("/api/alerts", alerts),
    Route("/api/results", results),
    Route("/api/results/image/{key}", result_image),
    Route("/api/{rest:path}", api_not_found),
]
if DIST.exists():
    routes.append(Mount("/", StaticFiles(directory=DIST, html=True), name="ui"))

app = Starlette(routes=routes, exception_handlers={HTTPException: http_error})


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    p = argparse.ArgumentParser(description="AviSense web UI and API.")
    p.add_argument("--host", default="127.0.0.1", help="Use 0.0.0.0 only on a trusted network.")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)
    if not DIST.exists():
        print("frontend/dist not found: API only. Build the UI with `cd frontend && npm run build`, "
              "or run `npm run dev` there and open http://localhost:3000")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
