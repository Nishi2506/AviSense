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
| train | chunks 0, 5, 6, 7 (`imagesN.zip`, `labelsN.zip`), minus the held-out sequence below | 38,408 | 29,559 | 71,358 |
| val | chunk 9 (authors' suggested val chunk) + `D02_20210728064810` from chunk 7 | 9,904 | 9,579 | 44,264 |
| test | `images_test_D02_20210628090856.zip` + labels | 10,000 | 1,097 | 1,148 |

Cameras per chunk (from the label file names): chunks 0–4 are camera D01; 5 is D01 +
D02; 6 and 7 are D02; 8 is IP + D02; 9 mixes sljc, IP, sw and xw. The test sequence is
camera **D02**, so chunks 5–7 were added to give 24,683 D02 training frames (none from
the test day, 2021-06-28). One D02 sequence (`D02_20210728064810`, 1,592 frames) is moved
from train to val so model selection also sees the test camera:

```powershell
Move-Item data/raw/airbirds/images/train/D02_20210728064810_* data/raw/airbirds/images/val/
Move-Item data/raw/airbirds/labels/train/D02_20210728064810_* data/raw/airbirds/labels/val/
```

**On the development laptop the images are no longer kept** (only the small label zips
and extracted labels): training and testing run on Google Colab
([`notebooks/train_detector_colab.ipynb`](../notebooks/train_detector_colab.ipynb)), which
downloads the zips itself. To evaluate locally again, download and extract the test
sequence (`images_test_D02_20210628090856.zip`, 17 GB) into `raw/airbirds/images/test`.

Layout (Ultralytics maps `/images/` → `/labels/` to find each label file):

```
raw/airbirds/
├── images/{train,val,test}/*.png
└── labels/{train,val,test}/*.txt
```

Label format: YOLO — `class_id x_center y_center width height` (normalised).
`class_id` is always `0` (bird); an empty file means no birds in that frame.
Images are 1920×1080 and birds are tiny (typically ~5–10 px), so train/infer at
`imgsz=1280` or use tiling.

To add more training data, download `imagesN.zip` + `labelsN.zip` from the same repo and
extract both flat into `images/train` and `labels/train` (the zips contain an
`imagesN/` / `labelsN/` folder). Each image chunk is 12–22 GB.

## Supplementary (optional)

- FBD-SV-2024 (flying-bird surveillance video, good for tracking tests):
  https://github.com/Ziwei89/FBD-SV-2024_github
- Roboflow Universe bird datasets (export as YOLO): https://universe.roboflow.com/search?q=class%3Abird
