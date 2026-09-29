"""Fine-tune YOLO on AirBirds (configs/airbirds.yaml), starting from COCO weights.

Usage (from the project root):
    python -m src.detection.train                              # yolo11n, imgsz 1280, 50 epochs
    python -m src.detection.train --model yolo11s.pt --epochs 100
    python -m src.detection.train --evaluate models/airbirds_yolo11n_1280.pt   # test split only

    # Native-resolution tiles (src.detection.make_tiles), tested on full frames at 1920:
    python -m src.detection.train --data configs/airbirds_tiles.yaml --imgsz 640         --test-data configs/airbirds.yaml --test-imgsz 1920

Birds in AirBirds are ~5-10 px in 1920x1080 frames, hence imgsz 1280 and a
milder scale augmentation than the default (0.5), which can shrink birds to
nothing.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

from src.detection.temporal import temporal_step

# Absolute, because Ultralytics nests relative project paths under its own runs dir.
RUNS_DIR = Path("runs/detect").resolve()


def train(args: argparse.Namespace) -> Path:
    name = args.name or f"airbirds_{Path(args.model).stem}_{args.imgsz}"
    if args.resume:  # Ultralytics resumes from the run's own last.pt with its saved settings
        model = YOLO(RUNS_DIR / name / "weights" / "last.pt")
        model.train(resume=True)
    else:
        model = YOLO(args.model)
        # Motion-stacked data: channels are frames, not colours, so hue/saturation
        # augmentation would scramble them (brightness scaling is still fine).
        colour_aug = {"hsv_h": 0.0, "hsv_s": 0.0} if temporal_step(args.data) else {}
        model.train(
            **colour_aug,
            data=args.data,
            imgsz=args.imgsz,
            epochs=args.epochs,
            batch=args.batch,
            device=args.device,
            workers=args.workers,
            patience=args.patience,  # early stop if val mAP stops improving
            scale=0.2,
            project=str(RUNS_DIR),
            name=name,
            fraction=args.fraction,
            pretrained=args.pretrained or True,  # a .pt path loads its weights into a .yaml-built model
            plots=True,
        )
    best = Path(model.trainer.save_dir) / "weights" / "best.pt"
    dest = Path("models") / f"{name}.pt"
    dest.parent.mkdir(exist_ok=True)
    shutil.copy2(best, dest)
    print(f"Best weights copied to {dest}")
    return dest


def evaluate(weights: str | Path, args: argparse.Namespace) -> None:
    metrics = YOLO(str(weights)).val(data=args.test_data or args.data, split="test",
                                     imgsz=args.test_imgsz or args.imgsz,
                                     batch=min(args.batch, 8) if args.batch > 0 else 8,  # full frames: keep VRAM low
                                     device=args.device, plots=True, project=str(RUNS_DIR),
                                     name=f"test_{Path(weights).stem}")
    print(f"Test split: mAP50 {metrics.box.map50:.3f}  mAP50-95 {metrics.box.map:.3f}  "
          f"precision {metrics.box.mp:.3f}  recall {metrics.box.mr:.3f}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Fine-tune YOLO on AirBirds.")
    p.add_argument("--data", default="configs/airbirds.yaml", help="Dataset YAML.")
    p.add_argument("--model", default="yolo11n.pt", help="Starting weights (COCO-pretrained).")
    p.add_argument("--imgsz", type=int, default=1280, help="Training image size.")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch", type=int, default=8,
                   help="Batch size (8 fits imgsz 1280 on an 8 GB GPU); -1 = AutoBatch, which picked 2 here.")
    p.add_argument("--device", default="0", help="'0' for first GPU, 'cpu'.")
    p.add_argument("--workers", type=int, default=4, help="Dataloader workers.")
    p.add_argument("--patience", type=int, default=15, help="Early-stopping patience (epochs).")
    p.add_argument("--pretrained", default=None,
                   help="Weights to load into a model built from a .yaml (e.g. yolo11n.pt for yolo11n-p2.yaml).")
    p.add_argument("--fraction", type=float, default=1.0, help="Fraction of train set to use (quick tests).")
    p.add_argument("--name", default=None, help="Run name (default: airbirds_<model>_<imgsz>).")
    p.add_argument("--resume", action="store_true", help="Resume the named run from its last.pt.")
    p.add_argument("--evaluate", default=None, metavar="WEIGHTS",
                   help="Skip training; evaluate these weights on the test split.")
    p.add_argument("--no-test", action="store_true", help="Do not evaluate on the test split after training.")
    p.add_argument("--test-data", default=None, help="Dataset YAML for the test split (default: --data).")
    p.add_argument("--test-imgsz", type=int, default=None, help="Test image size (default: --imgsz).")
    args = p.parse_args(argv)

    if args.evaluate:
        evaluate(args.evaluate, args)
        return
    weights = train(args)
    if not args.no_test:
        evaluate(weights, args)


if __name__ == "__main__":
    main()
