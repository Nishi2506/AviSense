# Data

Nothing in this folder is committed to git (except this file and `.gitkeep` placeholders).

| Folder | Contents |
|---|---|
| `raw/airbirds/` | AirBirds dataset (ACCV 2022) — YOLO-format images + labels. |
| `videos/` | Test videos / self-recorded footage for running the pipeline. |
| `processed/` | Generated artifacts: per-track features, CSV logs, etc. |

## AirBirds

Source: Hugging Face mirror by the dataset authors —
https://huggingface.co/datasets/auniquesun/AirBirds (no sign-up needed).
License: CC BY-NC-SA 4.0, non-commercial research/education only. Cite:
Sun et al., *AirBirds: A Large-scale Challenging Dataset for Bird Strike Prevention
in Real-world Airports*, ACCV 2022.

The full set is ~176 GB (train chunks 0–9, two test chunks). We use a subset:

| Split | Source files | Frames | Frames with birds | Boxes |
|---|---|---|---|---|
| train | `images0.zip`, `labels0.zip` | 10,000 | 9,138 | 29,719 |
| val | `images9.zip`, `labels9.zip` (authors' suggested val chunk) | 8,312 | 8,182 | 39,641 |
| test | `images_test_D02_20210628090856.zip` + labels | 10,000 | 1,097 | 1,148 |

Layout (Ultralytics maps `/images/` → `/labels/` to find each label file):

```
raw/airbirds/
├── images/{train,val,test}/*.jpg
└── labels/{train,val,test}/*.txt
```

Label format: YOLO — `class_id x_center y_center width height` (normalised).
`class_id` is always `0` (bird); an empty file means no birds in that frame.
Images are 1920×1080 and birds are tiny (typically ~5–10 px), so train/infer at
`imgsz=1280` or use tiling.

To add more training data later, download `imagesN.zip` + `labelsN.zip` from the
same repo.

## Supplementary (optional)

- FBD-SV-2024 (flying-bird surveillance video, good for tracking tests):
  https://github.com/Ziwei89/FBD-SV-2024_github
- Roboflow Universe bird datasets (export as YOLO): https://universe.roboflow.com/search?q=class%3Abird
