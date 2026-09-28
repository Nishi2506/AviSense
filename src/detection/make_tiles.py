"""Cut AirBirds frames into native-resolution tiles for training (configs/airbirds_tiles.yaml).

Birds are ~5-10 px in 1920x1080 frames. Training on full frames at imgsz 1280 shrinks
them further; training on 640x640 crops at imgsz 640 keeps every bird at its native
size. The resulting model then runs on *full* frames at imgsz 1920 (YOLO is fully
convolutional), so birds are the same size at train and test time and tracking with
model.track() works unchanged.

Usage (from the project root):
    python -m src.detection.make_tiles                     # train + val -> data/processed/airbirds_tiles
    python -m src.detection.make_tiles --empty-keep 0.2 --val-every 2

Tiles with no birds are subsampled (--empty-keep) so they don't swamp training; the val
set uses every --val-every-th frame, since consecutive frames are near-duplicates.
"""

from __future__ import annotations

import argparse
import random
import shutil
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2

SRC = Path("data/raw/airbirds")
DST = Path("data/processed/airbirds_tiles")


def tile_origins(size: int, tile: int) -> list[int]:
    """Evenly spaced tile starts covering [0, size), overlapping when size isn't a multiple of tile."""
    n = max(1, -(-size // tile))  # ceil
    if n == 1:
        return [0]
    step = (size - tile) / (n - 1)
    return [round(i * step) for i in range(n)]


def read_labels(path: Path, w: int, h: int) -> list[tuple[int, float, float, float, float]]:
    """YOLO labels -> (class, x1, y1, x2, y2) in pixels."""
    boxes = []
    if path.exists():
        for line in path.read_text().split("\n"):
            parts = line.split()
            if len(parts) == 5:
                c, cx, cy, bw, bh = int(parts[0]), *map(float, parts[1:])
                boxes.append((c, (cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
    return boxes


def tile_labels(boxes, x0: int, y0: int, tile: int, min_visible: float) -> list[str]:
    """Boxes clipped to the tile, kept if at least min_visible of their area is inside."""
    lines = []
    for c, x1, y1, x2, y2 in boxes:
        cx1, cy1 = max(x1, x0), max(y1, y0)
        cx2, cy2 = min(x2, x0 + tile), min(y2, y0 + tile)
        if cx2 <= cx1 or cy2 <= cy1:
            continue
        area = (x2 - x1) * (y2 - y1)
        if area > 0 and (cx2 - cx1) * (cy2 - cy1) / area < min_visible:
            continue
        lines.append(f"{c} {((cx1 + cx2) / 2 - x0) / tile:.6f} {((cy1 + cy2) / 2 - y0) / tile:.6f} "
                     f"{(cx2 - cx1) / tile:.6f} {(cy2 - cy1) / tile:.6f}")
    return lines


def process_frame(img_path: Path, split: str, tile: int, empty_keep: float, min_visible: float) -> tuple[int, int]:
    """Write this frame's tiles; returns (tiles written, boxes written)."""
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]
    boxes = read_labels(SRC / "labels" / split / f"{img_path.stem}.txt", w, h)
    rng = random.Random(zlib.crc32(img_path.stem.encode()))  # deterministic per frame
    n_tiles = n_boxes = 0
    for y0 in tile_origins(h, tile):
        for x0 in tile_origins(w, tile):
            lines = tile_labels(boxes, x0, y0, tile, min_visible)
            if not lines and rng.random() >= empty_keep:
                continue
            name = f"{img_path.stem}_x{x0}_y{y0}"
            cv2.imwrite(str(DST / "images" / split / f"{name}.png"), img[y0:y0 + tile, x0:x0 + tile])
            (DST / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
            n_tiles += 1
            n_boxes += len(lines)
    return n_tiles, n_boxes


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Tile AirBirds frames for native-resolution training.")
    p.add_argument("--tile", type=int, default=640, help="Tile size in pixels.")
    p.add_argument("--empty-keep", type=float, default=0.1, help="Fraction of bird-free tiles to keep.")
    p.add_argument("--min-visible", type=float, default=0.5, help="Keep a cut box if this much of it is inside.")
    p.add_argument("--val-every", type=int, default=4, help="Use every Nth val frame.")
    p.add_argument("--train-every", type=int, default=1, help="Use every Nth train frame.")
    p.add_argument("--splits", nargs="+", default=["train", "val"])
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args(argv)

    for split in args.splits:
        for kind in ("images", "labels"):  # start clean so tiles from earlier settings don't linger
            shutil.rmtree(DST / kind / split, ignore_errors=True)
            (DST / kind / split).mkdir(parents=True)
        frames = sorted((SRC / "images" / split).glob("*.png"))
        frames = frames[::args.val_every if split == "val" else args.train_every]
        with ProcessPoolExecutor(args.workers) as ex:
            results = list(ex.map(process_frame, frames, [split] * len(frames), [args.tile] * len(frames),
                                  [args.empty_keep] * len(frames), [args.min_visible] * len(frames),
                                  chunksize=32))
        print(f"{split}: {len(frames)} frames -> {sum(r[0] for r in results)} tiles, "
              f"{sum(r[1] for r in results)} boxes")


if __name__ == "__main__":
    main()
