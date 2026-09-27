"""Fine-tune YOLO on AirBirds (configs/airbirds.yaml), starting from COCO weights.

Usage (from the project root):
    python -m src.detection.train                              # yolo11n, imgsz 1280, 50 epochs
    python -m src.detection.train --model yolo11s.pt --epochs 100
    python -m src.detection.train --evaluate models/airbirds_yolo11n_1280.pt   # test split only

Birds in AirBirds are ~5-10 px in 1920x1080 frames, hence imgsz 1280 and a
milder scale augmentation than the default (0.5), which can shrink birds to
nothing.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

# Absolute, because Ultralytics nests relative project paths under its own runs dir.
RUNS_DIR = Path("runs/detect").resolve()


def train(args: argparse.Namespace) -> Path:
    name = args.name or f"airbirds_{Path(args.model).stem}_{args.imgsz}"
    if args.resume:  # Ultralytics resumes from the run's own last.pt with its saved settings
        model = YOLO(RUNS_DIR / name / "weights" / "last.pt")
        model.train(resume=True)
    else:
        model = YOLO(args.model)
        model.train(
            data=args.data,
            imgsz=args.imgsz,
            epochs=args.epochs,
            batch=args.batch,        # -1 = AutoBatch (fits ~60% of GPU memory)
            device=args.device,
            workers=args.workers,
            patience=args.patience,  # early stop if val mAP stops improving
            scale=0.2,
            project=str(RUNS_DIR),
            name=name,
            fraction=args.fraction,
            plots=True,
        )
    best = Path(model.trainer.save_dir) / "weights" / "best.pt"
    dest = Path("models") / f"{name}.pt"
    dest.parent.mkdir(exist_ok=True)
    shutil.copy2(best, dest)
    print(f"Best weights copied to {dest}")
    return dest


def evaluate(weights: str | Path, args: argparse.Namespace) -> None:
    metrics = YOLO(str(weights)).val(data=args.data, split="test", imgsz=args.imgsz,
                                     batch=args.batch if args.batch > 0 else 8,
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
    p.add_argument("--batch", type=int, default=-1, help="Batch size; -1 = AutoBatch.")
    p.add_argument("--device", default="0", help="'0' for first GPU, 'cpu'.")
    p.add_argument("--workers", type=int, default=4, help="Dataloader workers.")
    p.add_argument("--patience", type=int, default=15, help="Early-stopping patience (epochs).")
    p.add_argument("--fraction", type=float, default=1.0, help="Fraction of train set to use (quick tests).")
    p.add_argument("--name", default=None, help="Run name (default: airbirds_<model>_<imgsz>).")
    p.add_argument("--resume", action="store_true", help="Resume the named run from its last.pt.")
    p.add_argument("--evaluate", default=None, metavar="WEIGHTS",
                   help="Skip training; evaluate these weights on the test split.")
    p.add_argument("--no-test", action="store_true", help="Do not evaluate on the test split after training.")
    args = p.parse_args(argv)

    if args.evaluate:
        evaluate(args.evaluate, args)
        return
    weights = train(args)
    if not args.no_test:
        evaluate(weights, args)


if __name__ == "__main__":
    main()
