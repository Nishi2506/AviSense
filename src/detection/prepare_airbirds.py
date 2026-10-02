"""Download AirBirds chunk by chunk, tile each one and delete its frames (low-disk training prep).

The full training set is ~135 GB of PNGs. This keeps only the tiles: each chunk's zip is
downloaded, extracted, tiled with src.detection.make_tiles (--append) and deleted before
the next one, so disk use peaks at roughly two chunks (~35 GB) plus the tiles. A marker
file per finished chunk lets an interrupted run continue where it stopped.

Usage (from the project root):
    python -m src.detection.prepare_airbirds --temporal 2 --train-every 1 \
        --hard-negatives models/airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt --test
then train on configs/airbirds_tiles_temporal2.yaml (tiles in data/processed/airbirds_tiles_temporal2)
and, with --test, test on configs/airbirds_temporal2_test.yaml.

Same data recipe as notebooks/train_detector_colab.ipynb: train = chunks 0, 5, 6, 7 and the
D02 2021-07-21 sequence; val = chunk 9 + the held-out D02 sequence 2021-07-28 (from chunk 7);
test = the D02 2021-06-28 sequence.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HF = "https://huggingface.co/datasets/auniquesun/AirBirds/resolve/main"
TRAIN_CHUNKS = ["0", "5", "6", "7", "test_D02_20210721142744"]
VAL_CHUNK = "9"
HELD_OUT = "D02_20210728064810"
TEST_SEQ = "test_D02_20210628090856"


def zip_name(kind: str, chunk: str) -> str:
    """'images' / '5' -> 'images5.zip'; 'labels' / 'test_D02_...' -> 'labels_test_D02_....zip'."""
    return f"{kind}{chunk}.zip" if chunk.isdigit() else f"{kind}_{chunk}.zip"


CURL = ["curl", "-sSL", "--retry", "20", "--retry-all-errors", "--retry-delay", "5"]


def remote_size(url: str) -> int | None:
    """Content-Length of the final (redirected) response, or None if unknown."""
    out = subprocess.run([*CURL, "-I", url], capture_output=True, text=True).stdout
    sizes = [int(l.split(":", 1)[1]) for l in out.splitlines() if l.lower().startswith("content-length:")]
    return sizes[-1] if sizes else None


def byte_ranges(size: int, parts: int) -> list[tuple[int, int]]:
    """Split [0, size) into `parts` inclusive (start, end) byte ranges."""
    step = -(-size // parts)
    return [(s, min(s + step, size) - 1) for s in range(0, size, step)]


def download(name: str, dest: Path, parts: int = 8, min_split: int = 50_000_000) -> Path:
    """Download one file from the AirBirds mirror in `parts` parallel byte ranges.

    One HTTP connection to the mirror manages ~7 MB/s here; several in parallel are much
    faster. Finished parts are kept, so a rerun only fetches the missing ones.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{HF}/{name}"
    size = remote_size(url)
    if size is None or size < min_split:  # small or unknown size: one plain resumable download
        subprocess.run([*CURL, "-C", "-", "-o", str(dest), url], check=True)
        return dest
    if dest.exists() and dest.stat().st_size == size:
        return dest

    def fetch_part(i_rng):
        i, (s, e) = i_rng
        part = dest.with_name(f"{dest.name}.part{i}")
        for _ in range(20):  # connections do get cut mid-range; resume from what arrived
            have = part.stat().st_size if part.exists() else 0
            if have == e - s + 1:
                return part
            if have > e - s + 1:
                part.unlink()
                have = 0
            # No curl --retry here: when writing to stdout, curl's own retry re-sends the whole
            # range and appends it again (duplicate bytes). This loop resumes instead.
            with open(part, "ab") as f:
                subprocess.run(["curl", "-sSL", "--connect-timeout", "30", "--speed-limit", "50000",
                                "--speed-time", "60", "-r", f"{s + have}-{e}", url], stdout=f, check=False)
        raise RuntimeError(f"failed to download bytes {s}-{e} of {name}")

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(parts) as ex:
        part_files = list(ex.map(fetch_part, enumerate(byte_ranges(size, parts))))
    with open(dest, "wb") as out:
        for part in part_files:
            with open(part, "rb") as f:
                shutil.copyfileobj(f, out, 1 << 24)
            part.unlink()
    if dest.stat().st_size != size:
        raise RuntimeError(f"{name}: got {dest.stat().st_size} bytes, expected {size}")
    return dest


def extract_flat(zip_path: Path, out_dir: Path) -> int:
    """Extract every file of a zip into out_dir, dropping the zip's folder structure."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            with z.open(info) as src, open(out_dir / Path(info.filename).name, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            n += 1
    return n


def fetch(chunk: str, split: str, raw: Path, dl: Path) -> int:
    """Download + extract one chunk's images and labels into raw/{images,labels}/<split>; delete the zips."""
    n = 0
    for kind in ("images", "labels"):
        z = download(zip_name(kind, chunk), dl / zip_name(kind, chunk))
        count = extract_flat(z, raw / kind / split)
        n = count if kind == "images" else n
        z.unlink()
    print(f"chunk {chunk}: {n} {split} frames extracted", flush=True)
    return n


def move_sequence(raw: Path, prefix: str, src_split: str, dst_split: str) -> int:
    """Move all frames (and labels) of one sequence between splits; returns frames moved."""
    moved = 0
    for kind, ext in (("images", "png"), ("labels", "txt")):
        (raw / kind / dst_split).mkdir(parents=True, exist_ok=True)
        for f in (raw / kind / src_split).glob(f"{prefix}_*.{ext}"):
            shutil.move(str(f), raw / kind / dst_split / f.name)
            moved += kind == "images"
    return moved


def clear(raw: Path, split: str) -> None:
    for kind in ("images", "labels"):
        shutil.rmtree(raw / kind / split, ignore_errors=True)


def tile(raw: Path, out: Path, split: str, args: argparse.Namespace) -> None:
    cmd = [sys.executable, "-m", "src.detection.make_tiles", "--src", str(raw), "--out", str(out),
           "--splits", split, "--append", "--temporal", str(args.temporal),
           "--train-every", str(args.train_every), "--workers", str(args.workers)]
    if split == "train" and args.hard_negatives:
        cmd += ["--hard-negatives", args.hard_negatives]
    subprocess.run(cmd, check=True)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Download, tile and delete AirBirds chunks one at a time.")
    p.add_argument("--chunks", nargs="+", default=TRAIN_CHUNKS, help="Training chunks.")
    p.add_argument("--val-chunk", default=VAL_CHUNK)
    p.add_argument("--held-out", default=HELD_OUT, help="Sequence moved from train to val.")
    p.add_argument("--temporal", type=int, default=2, help="Motion-stacked tiles (0 = colour).")
    p.add_argument("--train-every", type=int, default=1, help="Use every Nth training frame.")
    p.add_argument("--hard-negatives", default=None, metavar="WEIGHTS", help="Model for hard-negative mining.")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--raw", default="data/raw/airbirds", help="Where frames are extracted temporarily.")
    p.add_argument("--out", default=None, help="Tiles folder (default: data/processed/airbirds_tiles[_temporalK]).")
    p.add_argument("--test", action="store_true",
                   help="Also download the test sequence (kept, 17 GB; plus 17 GB motion-stacked copy if --temporal).")
    p.add_argument("--restart", action="store_true", help="Delete existing tiles and progress markers first.")
    args = p.parse_args(argv)

    raw, dl = Path(args.raw), Path(args.raw) / "_download"
    out = Path(args.out or f"data/processed/airbirds_tiles{f'_temporal{args.temporal}' if args.temporal else ''}")
    if args.restart:
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    done = lambda name: out / f".done_{name}"

    for chunk in args.chunks:
        if done(chunk).exists():
            print(f"chunk {chunk}: already tiled, skipping")
            continue
        clear(raw, "train")  # leftovers from an interrupted run
        fetch(chunk, "train", raw, dl)
        held = move_sequence(raw, args.held_out, "train", "heldout")
        if held:
            print(f"moved {held} {args.held_out} frames to val")
        tile(raw, out, "train", args)
        clear(raw, "train")
        done(chunk).touch()

    if not done("val").exists():
        clear(raw, "val")
        fetch(args.val_chunk, "val", raw, dl)
        for kind in ("images", "labels"):  # add the held-out sequence kept aside above
            for f in (raw / kind / "heldout").glob("*"):
                shutil.move(str(f), raw / kind / "val" / f.name)
        tile(raw, out, "val", args)
        clear(raw, "val")
        clear(raw, "heldout")
        done("val").touch()

    if args.test and not (raw / "images" / "test").exists():
        fetch(TEST_SEQ, "test", raw, dl)
        if args.temporal:
            subprocess.run([sys.executable, "-m", "src.detection.temporal", "--images", str(raw / "images" / "test"),
                            "--labels", str(raw / "labels" / "test"), "--step", str(args.temporal)], check=True)
    shutil.rmtree(dl, ignore_errors=True)
    for split in ("train", "val"):
        print(split, sum(1 for _ in (out / "images" / split).glob("*.png")), "tiles in", out)


if __name__ == "__main__":
    main()
