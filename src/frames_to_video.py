"""Stitch a sequence of AirBirds frames into an MP4 for the tracker/dashboard.

AirBirds frames are consecutive images per camera, named <prefix>_<frame number>.png,
e.g. D02_20210628090856_0000123.png. The output name keeps a YYYYMMDDhhmmss stamp,
shifted to the first exported frame, so the pipeline can infer the start time.

Usage (from the project root):
    python -m src.frames_to_video --images data/raw/airbirds/images/test \
        --prefix D02_20210628090856 --start 0 --count 1500 --out-dir data/videos
    python -m src.frames_to_video --images data/raw/airbirds/images/val --prefix 20201111_sljc_1 \
        --count 600 --labels data/raw/airbirds/labels/val --out-dir outputs   # draw ground truth
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

import cv2

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def find_sequence(images: Path, prefix: str) -> list[tuple[int, Path]]:
    """(frame number, path) for images named <prefix>_<digits>, sorted by frame number."""
    pat = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    frames = []
    for p in images.iterdir():
        m = pat.match(p.stem)
        if m and p.suffix.lower() in IMAGE_EXTS:
            frames.append((int(m.group(1)), p))
    return sorted(frames)


def output_name(prefix: str, first: int, last: int, fps: float) -> str:
    m = re.search(r"(\d{14})", prefix)
    if m:  # shift the wall-clock stamp to the first exported frame
        t0 = datetime.strptime(m.group(1), "%Y%m%d%H%M%S") + timedelta(seconds=first / fps)
        prefix = prefix.replace(m.group(1), t0.strftime("%Y%m%d%H%M%S"))
    return f"{prefix}_f{first}-{last}.mp4"


def draw_labels(frame, label_path: Path) -> None:
    if not label_path.exists():
        return
    h, w = frame.shape[:2]
    for line in label_path.read_text().split("\n"):
        parts = line.split()
        if len(parts) != 5:
            continue
        _, cx, cy, bw, bh = map(float, parts)
        # Birds are tiny: pad the drawn box so it is visible at normal viewing size.
        x1, y1 = int((cx - bw / 2) * w) - 6, int((cy - bh / 2) * h) - 6
        x2, y2 = int((cx + bw / 2) * w) + 6, int((cy + bh / 2) * h) + 6
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Stitch AirBirds frames into an MP4.")
    p.add_argument("--images", required=True, help="Folder of frames (e.g. data/raw/airbirds/images/test).")
    p.add_argument("--prefix", required=True, help="Sequence prefix before _<frame number>.")
    p.add_argument("--start", type=int, default=0, help="First frame number to include.")
    p.add_argument("--count", type=int, default=None, help="Number of frames (default: all from --start).")
    p.add_argument("--fps", type=float, default=25.0,
                   help="Output frame rate. AirBirds does not state its capture rate; 25 is an assumption.")
    p.add_argument("--labels", default=None, help="Labels folder: draw ground-truth boxes (for checking).")
    p.add_argument("--scale", type=float, default=1.0, help="Resize factor (e.g. 0.5 for smaller files).")
    p.add_argument("--out-dir", default="data/videos", help="Where to write the MP4.")
    args = p.parse_args(argv)

    seq = [(n, path) for n, path in find_sequence(Path(args.images), args.prefix) if n >= args.start]
    if args.count:
        seq = seq[: args.count]
    if not seq:
        raise SystemExit(f"No frames matching {args.prefix}_<number> from {args.start} in {args.images}")
    gaps = sum(1 for (a, _), (b, _) in zip(seq, seq[1:]) if b != a + 1)
    if gaps:
        print(f"Warning: {gaps} gap(s) in frame numbering; the video will skip those frames.")

    out = Path(args.out_dir) / output_name(args.prefix, seq[0][0], seq[-1][0], args.fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    for i, (n, path) in enumerate(seq):
        frame = cv2.imread(str(path))
        if args.labels:
            draw_labels(frame, Path(args.labels) / f"{path.stem}.txt")
        if args.scale != 1.0:
            frame = cv2.resize(frame, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_AREA)
        if writer is None:
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (w, h))
        writer.write(frame)
        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{len(seq)} frames")
    writer.release()
    print(f"Wrote {len(seq)} frames ({len(seq) / args.fps:.0f}s at {args.fps:g} fps) to {out}")


if __name__ == "__main__":
    main()
