"""Runway / protected zones as polygons, and distance-to-zone geometry.

Zones are stored as JSON with polygon vertices normalised to [0, 1] of frame
width/height, so one file works at any resolution of the same camera view:

    {
      "camera": "D02",
      "zones": [
        {"name": "runway", "polygon": [[0.10, 0.62], [0.95, 0.55], [0.98, 0.70], [0.08, 0.80]]}
      ]
    }

Draw them with `python -m src.risk_scoring.zone_editor`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Zone:
    name: str
    polygon: list[tuple[float, float]]  # normalised (x, y) in [0, 1]

    def to_pixels(self, frame_w: int, frame_h: int) -> np.ndarray:
        """Polygon as an OpenCV contour of float32 pixel coords, shape (N, 1, 2)."""
        pts = np.asarray(self.polygon, dtype=np.float32) * np.array([frame_w, frame_h], dtype=np.float32)
        return pts.reshape(-1, 1, 2)


def load_zones(path: str | Path) -> tuple[str | None, list[Zone]]:
    data = json.loads(Path(path).read_text())
    zones = [Zone(z["name"], [tuple(p) for p in z["polygon"]]) for z in data["zones"]]
    for z in zones:
        if len(z.polygon) < 3:
            raise ValueError(f"Zone {z.name!r} needs at least 3 points, got {len(z.polygon)}")
    return data.get("camera"), zones


def save_zones(path: str | Path, zones: list[Zone], camera: str | None = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    data = {"camera": camera,
            "zones": [{"name": z.name, "polygon": [[round(x, 5), round(y, 5)] for x, y in z.polygon]}
                      for z in zones]}
    Path(path).write_text(json.dumps(data, indent=2))


def distance_to_zones(x: float, y: float, zones: list[Zone], frame_w: int, frame_h: int) -> float:
    """Pixel distance from (x, y) to the nearest zone edge; 0 if inside any zone."""
    best = np.inf
    for z in zones:
        signed = cv2.pointPolygonTest(z.to_pixels(frame_w, frame_h), (float(x), float(y)), True)
        best = min(best, max(0.0, -signed))  # pointPolygonTest: + inside, - outside
    return float(best)


def draw_zones(frame: np.ndarray, zones: list[Zone], color=(0, 0, 255)) -> np.ndarray:
    h, w = frame.shape[:2]
    overlay = frame.copy()
    polys = [z.to_pixels(w, h).astype(np.int32) for z in zones]
    for pts in polys:
        cv2.fillPoly(overlay, [pts], color)
    out = cv2.addWeighted(overlay, 0.25, frame, 0.75, 0)
    for z, pts in zip(zones, polys):  # outline and label on top of the fill
        cv2.polylines(out, [pts], True, color, 2)
        x, y = pts[:, 0, :].min(axis=0)
        cv2.putText(out, z.name, (int(x) + 6, int(y) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return out
