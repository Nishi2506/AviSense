"""Interactive editor for drawing runway zone polygons on a camera frame.

Usage (from the project root):
    python -m src.risk_scoring.zone_editor --source data/videos/sample.mp4 --out configs/zones/cam1.json
    python -m src.risk_scoring.zone_editor --source path/to/frame.jpg --out configs/zones/D02.json \
        --camera D02 --names runway taxiway

Controls:
    left click   add a vertex to the current zone
    right click  remove the last vertex
    n            finish current zone, start the next (names from --names)
    s            save and quit
    q / Esc      quit without saving
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from src.risk_scoring.zones import Zone, draw_zones, load_zones, save_zones

WINDOW = "AviSense - zone editor"
MAX_DISPLAY_W = 1600  # scale large frames down to fit the screen


def read_frame(source: str, frame_idx: int = 0) -> np.ndarray:
    if Path(source).suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
        frame = cv2.imread(source)
    else:
        cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        _, frame = cap.read()
        cap.release()
    if frame is None:
        raise FileNotFoundError(f"Could not read a frame from {source}")
    return frame


def edit(frame: np.ndarray, names: list[str], existing: list[Zone]) -> list[Zone] | None:
    h, w = frame.shape[:2]
    scale = min(1.0, MAX_DISPLAY_W / w)
    done: list[Zone] = list(existing)
    current: list[tuple[float, float]] = []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            current.append((x / scale / w, y / scale / h))
        elif event == cv2.EVENT_RBUTTONDOWN and current:
            current.pop()

    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, on_mouse)

    def next_name() -> str:
        i = len(done)
        return names[i] if i < len(names) else f"zone_{i + 1}"

    while True:
        view = draw_zones(frame.copy(), done)
        pts = (np.array(current) * [w, h]).astype(np.int32)
        for p in pts:
            cv2.circle(view, tuple(int(v) for v in p), 5, (0, 255, 255), -1)
        if len(pts) > 1:
            cv2.polylines(view, [pts.reshape(-1, 1, 2)], len(pts) > 2, (0, 255, 255), 2)
        cv2.putText(view, f"drawing: {next_name()} ({len(current)} pts) | n=next zone  s=save  q=quit",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow(WINDOW, cv2.resize(view, None, fx=scale, fy=scale) if scale < 1 else view)

        key = cv2.waitKey(30) & 0xFF
        if key in (ord("n"), ord("s")) and len(current) >= 3:
            done.append(Zone(next_name(), current.copy()))
            current.clear()
        if key == ord("s"):
            cv2.destroyAllWindows()
            return done
        if key in (ord("q"), 27):
            cv2.destroyAllWindows()
            return None


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Draw runway zone polygons on a camera frame.")
    p.add_argument("--source", required=True, help="Video file or image of the camera view.")
    p.add_argument("--out", required=True, help="Output zones JSON (e.g. configs/zones/D02.json).")
    p.add_argument("--frame", type=int, default=0, help="Frame index to draw on (videos only).")
    p.add_argument("--camera", default=None, help="Camera ID stored in the JSON.")
    p.add_argument("--names", nargs="*", default=["runway"], help="Names for zones, in drawing order.")
    args = p.parse_args(argv)

    frame = read_frame(args.source, args.frame)
    camera, existing = (load_zones(args.out) if Path(args.out).exists() else (args.camera, []))
    zones = edit(frame, args.names, existing)
    if zones is None:
        print("Quit without saving.")
        return
    if not zones:
        print("No zone with >= 3 points; nothing saved.")
        return
    save_zones(args.out, zones, args.camera or camera)
    print(f"Saved {len(zones)} zone(s) to {args.out}: {[z.name for z in zones]}")


if __name__ == "__main__":
    main()
