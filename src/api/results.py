"""Evaluation results shown on the Results page.

Numbers are copied from the README's Results / Tracking tables (test split = AirBirds D02 2021-06-28,
10,000 full frames, 1,148 birds); training curves and figures are read from the run folder itself.
Update BEST_RUN and the tables together when a new model replaces the current one.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BEST_RUN = "airbirds_tiles_temporal2_hn_e1_yolo11n-p2_640"
BEST_WEIGHTS = f"models/{BEST_RUN}.pt"

TEST_SET = {"name": "AirBirds D02 2021-06-28", "frames": 10_000, "birds": 1_148, "imgsz": 1920}

DETECTOR = {  # README "Results" table, current best row
    "precision": 0.755, "recall": 0.762, "map50": 0.761, "map50_95": 0.293,
    "train_tiles": 30_380, "epochs_run": 72, "epochs_max": 80, "best_epoch": 47, "train_hours": 6.4,
    "train_data": "Chunks 5, 6, 7 + D02 2021-07-21, every consecutive frame, hard negatives",
    "model": "YOLO11n + P2 head, 3-frame motion input",
}

TRACKING = {  # README "Tracking against ground truth": tracked-box conf >= 0.3, 20 px motion filter, 60 px matching box
    "precision": 0.800, "recall": 0.618, "false_alarm_frames": 0.018,
    "notes": "Birds matched to ground truth within 15 px; tracks are reported only after moving 20 px.",
}

SPEED = {  # measured 2026-10-08 with python -m src.pipeline on data/videos/D02_20210628090856_f0-1499.mp4
    # (1,500 frames). On battery in Balanced mode the same run gave 4.7 FPS (2026-11-16).
    "pipeline_fps": 12.0, "imgsz": 1920, "gpu": "RTX 5060 Laptop GPU",
    "notes": "Full 1920x1080 frames, detection + tracking + risk scoring; the web UI adds display overhead.",
}

MODELS = [  # README "Results" table, oldest first
    {"weights": "airbirds_yolo11n_1280.pt", "data": "chunk 0 (D01)", "training": "full frames @1280",
     "test_imgsz": 1280, "precision": 0.235, "recall": 0.323, "map50": 0.142, "map50_95": 0.030},
    {"weights": "airbirds_tiles_yolo11n_640.pt", "data": "chunk 0 (D01)", "training": "tiles @640",
     "test_imgsz": 1920, "precision": 0.223, "recall": 0.462, "map50": 0.241, "map50_95": 0.071},
    {"weights": "airbirds_tiles_yolo11s_640.pt", "data": "chunk 0 (D01)", "training": "tiles @640, YOLO11s",
     "test_imgsz": 1920, "precision": 0.183, "recall": 0.503, "map50": 0.169, "map50_95": 0.050},
    {"weights": "airbirds_tiles_c0567_yolo11n_640.pt", "data": "chunks 0, 5, 6, 7 (D01 + D02)", "training": "tiles @640",
     "test_imgsz": 1920, "precision": 0.464, "recall": 0.687, "map50": 0.602, "map50_95": 0.197},
    {"weights": "airbirds_tiles_temporal2_yolo11n_640.pt", "data": "chunks 0, 5, 6, 7", "training": "motion input",
     "test_imgsz": 1920, "precision": 0.597, "recall": 0.625, "map50": 0.603, "map50_95": 0.203},
    {"weights": "airbirds_tiles_hn_yolo11n-p2_640.pt", "data": "chunks 0, 5, 6, 7 + hard negatives",
     "training": "P2 head", "test_imgsz": 1920, "precision": 0.671, "recall": 0.782, "map50": 0.729,
     "map50_95": 0.250},
    {"weights": "airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt", "data": "chunks 0, 5, 6, 7 + D02 07-21, hard negatives",
     "training": "P2 head + motion input", "test_imgsz": 1920, "precision": 0.714, "recall": 0.782,
     "map50": 0.770, "map50_95": 0.276},
    {"weights": f"{BEST_RUN}.pt", "data": "chunks 5, 6, 7 + D02 07-21, every frame, hard negatives",
     "training": "P2 head + motion input", "test_imgsz": 1920, "precision": 0.755, "recall": 0.762,
     "map50": 0.761, "map50_95": 0.293, "current": True},
]

# Figures produced by Ultralytics for the current model (whitelist: only these files are served).
IMAGES = {
    "training_curves": f"runs/detect/{BEST_RUN}/results.png",
    "pr_curve_test": f"runs/detect/test_{BEST_RUN}/BoxPR_curve.png",
    "confusion_test": f"runs/detect/test_{BEST_RUN}/confusion_matrix.png",
    "test_pred": f"runs/detect/test_{BEST_RUN}/val_batch0_pred.jpg",
    "test_labels": f"runs/detect/test_{BEST_RUN}/val_batch0_labels.jpg",
}


def training_curves() -> list[dict]:
    """Per-epoch validation metrics and losses from the run's results.csv (empty if missing)."""
    path = ROOT / "runs" / "detect" / BEST_RUN / "results.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        rows = [{k.strip(): v for k, v in r.items()} for r in csv.DictReader(f)]
    keys = {"epoch": "epoch", "precision": "metrics/precision(B)", "recall": "metrics/recall(B)",
            "map50": "metrics/mAP50(B)", "map50_95": "metrics/mAP50-95(B)", "box_loss": "train/box_loss",
            "cls_loss": "train/cls_loss", "dfl_loss": "train/dfl_loss", "val_box_loss": "val/box_loss"}
    return [{k: float(r[c]) for k, c in keys.items() if c in r} for r in rows]


def image_path(key: str) -> Path | None:
    rel = IMAGES.get(key)
    p = ROOT / rel if rel else None
    return p if p and p.exists() else None


def results() -> dict:
    return {"test_set": TEST_SET, "detector": DETECTOR, "tracking": TRACKING, "speed": SPEED,
            "models": MODELS, "run": BEST_RUN, "curves": training_curves(),
            "images": {k: f"/api/results/image/{k}" for k in IMAGES if image_path(k)}}
