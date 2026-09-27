"""Frame-by-frame bird detection on a video using YOLO + OpenCV.

First stage of the AviSense pipeline:
    Video -> Frame extraction (OpenCV) -> Bird detection (YOLO) -> ...

Usage (from the project root):
    python -m src.detection.detect --source data/videos/sample.mp4 --show
    python -m src.detection.detect --source 0 --show            # webcam
    python -m src.detection.detect --source data/videos/sample.mp4 \
        --weights models/airbirds_best.pt --save outputs/annotated.mp4
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
from ultralytics import YOLO

DEFAULT_WEIGHTS = "yolo11n.pt"  # COCO-pretrained; auto-downloaded on first use
BIRD_CLASS_NAMES = {"bird"}


@dataclass
class Detection:
    """One detected object in one frame. Box is (x1, y1, x2, y2) in pixels."""

    frame_idx: int
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


class BirdDetector:
    """Wraps a YOLO model and returns bird detections for a single frame."""

    def __init__(
        self,
        weights: str = DEFAULT_WEIGHTS,
        conf: float = 0.25,
        imgsz: int = 640,
        device: str | None = None,
        birds_only: bool = True,
    ) -> None:
        self.model = YOLO(weights)
        self.conf = conf
        self.imgsz = imgsz
        self.device = device  # None lets Ultralytics pick GPU if available
        self.names: dict[int, str] = self.model.names

        # Resolve bird class ids by name so this works for both COCO weights
        # (bird = 14) and AirBirds fine-tuned weights (likely bird = 0).
        if birds_only:
            self.classes = [i for i, n in self.names.items() if n.lower() in BIRD_CLASS_NAMES]
            if not self.classes:
                raise ValueError(
                    f"No 'bird' class in model {weights!r}. Classes: {self.names}. "
                    "Use --all-classes to disable filtering."
                )
        else:
            self.classes = None

    def detect(self, frame: np.ndarray, frame_idx: int = 0) -> list[Detection]:
        result = self.model.predict(
            frame,
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            classes=self.classes,
            verbose=False,
        )[0]

        detections = []
        for (x1, y1, x2, y2), conf, cls in zip(
            result.boxes.xyxy.cpu().numpy(),
            result.boxes.conf.cpu().numpy(),
            result.boxes.cls.cpu().numpy().astype(int),
        ):
            detections.append(
                Detection(frame_idx, float(x1), float(y1), float(x2), float(y2),
                          float(conf), int(cls), self.names[int(cls)])
            )
        return detections


def iter_frames(source: str) -> Iterator[tuple[int, np.ndarray]]:
    """Yield (frame_idx, BGR frame) from a video file or webcam index."""
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video source: {source}")
    try:
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield idx, frame
            idx += 1
    finally:
        cap.release()


def source_fps(source: str, fallback: float = 30.0) -> float:
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps and fps > 0 else fallback


def draw_detections(frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
    for d in detections:
        p1, p2 = (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2))
        cv2.rectangle(frame, p1, p2, (0, 200, 255), 2)
        cv2.putText(frame, f"{d.class_name} {d.confidence:.2f}", (p1[0], max(p1[1] - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1, cv2.LINE_AA)
    return frame


def run(args: argparse.Namespace) -> None:
    detector = BirdDetector(args.weights, args.conf, args.imgsz, args.device,
                            birds_only=not args.all_classes)

    writer = None
    total_dets = 0
    start = time.perf_counter()
    idx = -1

    for idx, frame in iter_frames(args.source):
        t0 = time.perf_counter()
        detections = detector.detect(frame, idx)
        fps = 1.0 / max(time.perf_counter() - t0, 1e-6)
        total_dets += len(detections)

        if args.show or args.save:
            annotated = draw_detections(frame, detections)
            cv2.putText(annotated, f"birds: {len(detections)}  fps: {fps:.1f}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

            if args.save:
                if writer is None:
                    Path(args.save).parent.mkdir(parents=True, exist_ok=True)
                    h, w = annotated.shape[:2]
                    writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"),
                                             args.save_fps or source_fps(args.source), (w, h))
                writer.write(annotated)

            if args.show:
                cv2.imshow("AviSense - detection (q to quit)", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()

    n_frames = idx + 1
    elapsed = time.perf_counter() - start
    print(f"Processed {n_frames} frames in {elapsed:.1f}s "
          f"({n_frames / max(elapsed, 1e-6):.1f} FPS), {total_dets} detections total.")
    if args.save:
        print(f"Annotated video saved to {args.save}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AviSense: YOLO bird detection on video.")
    p.add_argument("--source", required=True, help="Video file path, or webcam index (e.g. 0).")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS, help="YOLO weights (.pt).")
    p.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    p.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    p.add_argument("--device", default=None, help="'0' for first GPU, 'cpu', or omit for auto.")
    p.add_argument("--all-classes", action="store_true", help="Do not filter to bird class.")
    p.add_argument("--show", action="store_true", help="Show a live preview window.")
    p.add_argument("--save", default=None, help="Path to save annotated .mp4.")
    p.add_argument("--save-fps", type=float, default=None,
                   help="FPS for the saved video (default: same as source).")
    return p.parse_args(argv)


if __name__ == "__main__":
    run(parse_args())
