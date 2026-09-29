"""Motion-aware input: stack three greyscale frames (t-2k, t-k, t) as the B, G, R channels.

Birds move ~3-10 px per frame, most false detections (sky texture, horizon clutter) don't.
In the stacked image a moving bird appears as three offset dots of different colours,
while anything static is grey, so the detector can learn to use motion directly. Only
past frames are used, so it works on a live stream.

Models trained on these images have "temporal<k>" in their file name (see
temporal_step), and BirdDetector composes its input automatically for them.
"""

from __future__ import annotations

import re
from collections import deque
from pathlib import Path

import cv2
import numpy as np


def temporal_step(weights: str | Path) -> int:
    """Frame step k encoded in a weights file name as 'temporal<k>', or 0 for ordinary RGB models."""
    m = re.search(r"temporal(\d+)", Path(str(weights)).stem)
    return int(m.group(1)) if m else 0


def compose(oldest: np.ndarray, middle: np.ndarray, current: np.ndarray) -> np.ndarray:
    """BGR image whose channels are the greyscale frames t-2k, t-k and t."""
    gray = [f if f.ndim == 2 else cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in (oldest, middle, current)]
    return np.dstack(gray)


class TemporalBuffer:
    """Keeps the last 2k frames of a stream and returns the composed image for each new frame.

    Until 2k earlier frames exist, the missing ones are replaced by the oldest frame seen,
    so the first frames of a stream look static (no motion cue) rather than failing.
    """

    def __init__(self, step: int) -> None:
        self.step = step
        self._frames: deque[np.ndarray] = deque(maxlen=2 * step + 1)

    def push(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        self._frames.append(gray)
        f = list(self._frames)
        pick = lambda back: f[max(0, len(f) - 1 - back)]
        return compose(pick(2 * self.step), pick(self.step), f[-1])


def sequence_neighbours(path: Path, step: int) -> tuple[Path, Path] | None:
    """Paths of frames n-2k and n-k of an AirBirds frame '<prefix>_<n:07d>.png', if both exist."""
    prefix, num = path.stem.rsplit("_", 1)
    n = int(num)
    if n < 2 * step:
        return None
    older = [path.with_name(f"{prefix}_{n - b:0{len(num)}d}{path.suffix}") for b in (2 * step, step)]
    return (older[0], older[1]) if all(p.exists() for p in older) else None


def load_composed(path: Path, step: int) -> np.ndarray | None:
    """Composed image for a frame on disk, or None if its earlier frames are missing."""
    nb = sequence_neighbours(path, step)
    if nb is None:
        return None
    return compose(*(cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) for p in (*nb, path)))


def write_sequence(images: Path, labels: Path, out: Path, split: str, step: int) -> int:
    """Write motion-stacked copies of every frame (and its labels) for evaluation.

    Frames are processed in order per sequence with a TemporalBuffer that is reset at
    gaps in the frame numbering, exactly as the live pipeline sees a stream.
    """
    (out / "images" / split).mkdir(parents=True, exist_ok=True)
    (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    frames = sorted(images.glob("*.png"), key=lambda p: (p.stem.rsplit("_", 1)[0], int(p.stem.rsplit("_", 1)[1])))
    buf, prev = None, (None, None)
    for i, p in enumerate(frames):
        prefix, n = p.stem.rsplit("_", 1)[0], int(p.stem.rsplit("_", 1)[1])
        if (prefix, n - 1) != prev:
            buf = TemporalBuffer(step)
        prev = (prefix, n)
        cv2.imwrite(str(out / "images" / split / p.name), buf.push(cv2.imread(str(p))))
        lbl = labels / f"{p.stem}.txt"
        (out / "labels" / split / lbl.name).write_text(lbl.read_text() if lbl.exists() else "")
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(frames)} frames")
    return len(frames)


def main(argv: list[str] | None = None) -> None:
    import argparse

    p = argparse.ArgumentParser(description="Write motion-stacked frames for evaluating temporal models.")
    p.add_argument("--images", default="data/raw/airbirds/images/test")
    p.add_argument("--labels", default="data/raw/airbirds/labels/test")
    p.add_argument("--split", default="test")
    p.add_argument("--step", type=int, default=2, help="Frame step k (frames t-2k, t-k, t).")
    p.add_argument("--out", default=None, help="Default: data/processed/airbirds_temporal<k>_<split>.")
    args = p.parse_args(argv)
    out = Path(args.out or f"data/processed/airbirds_temporal{args.step}_{args.split}")
    n = write_sequence(Path(args.images), Path(args.labels), out, args.split, args.step)
    print(f"Wrote {n} motion-stacked frames to {out}")


if __name__ == "__main__":
    main()
