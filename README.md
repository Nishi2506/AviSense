# AviSense

**AI-based Bird Strike Risk Detection and Alert System for airports.**

AviSense is a low-cost, camera-based alternative to commercial avian radar. It detects
birds in video, tracks them across frames, computes an **explainable** risk score, and
shows Low / Medium / High risk on a live dashboard with alerts.

## Pipeline

```
Camera / Video
   │  OpenCV
   ▼
Frame Extraction ──► Bird Detection (YOLO11) ──► Multi-Object Tracking (ByteTrack)
                                                        │
                                                        ▼
Dashboard & Alerts ◄── Risk Classification ◄── Risk Scoring ◄── Feature Extraction
   (Streamlit)          (Low / Med / High)      (weighted)     (speed, direction,
                                                                count, proximity)
```

| Stage | Module | Status |
|---|---|---|
| Frame extraction + detection | `src/detection/detect.py` | ✅ |
| Fine-tuning on AirBirds | `src/detection/train.py`, `configs/airbirds.yaml` | ✅ first run done (weak — see results) |
| Tracking (ByteTrack via `model.track()`) | `src/tracking/track.py` | ✅ |
| Runway zones (polygons) | `src/risk_scoring/zones.py`, `zone_editor.py` | ✅ |
| Feature extraction | `src/risk_scoring/features.py` | ✅ |
| Risk scoring + classification + alerts | `src/risk_scoring/risk.py`, `configs/risk.yaml` | ✅ |
| End-to-end live pipeline + SQLite alert log | `src/pipeline.py`, `src/alert_log.py` | ✅ |
| Dashboard | `src/dashboard/app.py` | ✅ |
| Optional ML classifier | `notebooks/risk_classifier_colab.ipynb`, `src/risk_scoring/ml_model.py` | ✅ (runs on Colab) |

## Quick start

```powershell
.venv\Scripts\Activate.ps1

# 1. Draw the runway zone for your camera once
python -m src.risk_scoring.zone_editor --source data/videos/<clip>.mp4 --out configs/zones/cam1.json --names runway

# 2. Open the dashboard, pick the video + zones, press Run
streamlit run src/dashboard/app.py
```

## Risk scoring

A transparent weighted formula, not a black box:

```
risk_score = w1·count + w2·speed + w3·proximity_to_runway_zone + w4·flock_size + w5·time_of_day
```

Each term is normalised to [0, 1] and the weights sum to 1, so the score is in [0, 1].
Everything is set in [`configs/risk.yaml`](configs/risk.yaml):

| Term | Normalisation (default) | Weight |
|---|---|---|
| count | birds ÷ 20, capped at 1 | 0.20 |
| speed | fastest bird ÷ 0.5 diag/s, capped at 1 | 0.15 |
| proximity | 1 inside a runway zone → 0 at 0.3 diag away | 0.35 |
| flock_size | largest flock ÷ 10, capped at 1 | 0.15 |
| time_of_day | 1.0 at dawn (05–09) and dusk (17–20), 0.4 otherwise, 0.5 if unknown | 0.15 |

| Level | Score |
|---|---|
| ✔ Low | < 0.3 |
| ▲ Medium | 0.3 – 0.6 |
| ⬣ High | ≥ 0.6 |

- **No birds → no risk:** the time-of-day term only counts when birds are present.
- **Smoothing:** the score is a rolling mean over 15 frames to avoid flicker.
- **Explainable:** every output keeps each term's weighted contribution (`c_*`) and the
  largest one (`top_factor`), so each alert says *why* (e.g. "runway proximity").
- **Alerts:** consecutive frames at Medium or above form an alert episode; episodes
  shorter than 1 s are ignored and gaps under 2 s are merged.

## Dashboard

```powershell
streamlit run src/dashboard/app.py
```

Pick a video from `data/videos/` (or upload one, or use a webcam), a zones file from
`configs/zones/`, and detector weights (fine-tuned weights in `models/` appear
automatically). Weights and thresholds can be adjusted live in the sidebar.

It shows the annotated video (zones, tracked birds, trails, risk banner), the current
risk level, bird count / flock / distance / speed, a risk-over-time chart with the
thresholds, a per-factor contribution chart, pop-up alerts, and the alert history
from SQLite (`outputs/alerts.db`).

The video start time (for the time-of-day term) is read from the filename when it
contains a `YYYYMMDDhhmmss` stamp (AirBirds style), or can be set in the sidebar.

## Command-line pipeline

The same pipeline without the dashboard:

```powershell
python -m src.pipeline --source data/videos/<clip>.mp4 --zones configs/zones/cam1.json `
    --weights models/airbirds_yolo11n_1280.pt --imgsz 1280 --save outputs/pipeline.mp4 --db outputs/alerts.db
```

Or step by step, producing CSVs at each stage (used for the ML notebook and analysis):

```powershell
python -m src.tracking.track --source data/videos/<clip>.mp4 --csv data/processed/<clip>_tracks.csv --imgsz 1280
python -m src.risk_scoring.features --tracks data/processed/<clip>_tracks.csv --zones configs/zones/cam1.json `
    --out data/processed/<clip>_features.csv --start-time 2021-06-28T09:08:56
python -m src.risk_scoring.risk --features data/processed/<clip>_features.csv --out data/processed/<clip>_risk.csv `
    --alerts-out data/processed/<clip>_alerts.csv
```

The live pipeline and the step-by-step commands compute identical scores (checked in
`tests/test_pipeline.py`).

## Training on AirBirds

Data: train = chunk 0, val = chunk 9 (the authors' suggestion), test = D02 0628 —
see [`data/README.md`](data/README.md).

```powershell
python -m src.detection.train                               # yolo11n, imgsz 1280, 50 epochs, batch 8
python -m src.detection.train --model yolo11s.pt --epochs 100
python -m src.detection.train --resume                      # continue an interrupted run
python -m src.detection.train --evaluate models/airbirds_yolo11n_1280.pt   # test split only
```

Birds are ~5–10 px in 1920×1080 frames, so training uses `imgsz=1280` and a milder
scale augmentation. Runs are saved in `runs/detect/`; the best weights are copied to
`models/airbirds_<model>_<imgsz>.pt` and evaluated on the test split. Plug the laptop
in and use the Best Performance power mode — on battery the GPU is heavily throttled.

## Test videos from AirBirds

AirBirds frames are consecutive per camera, so sequences can be stitched into videos
for the tracker and dashboard (the test chunk is 10,000 consecutive frames from camera
D02). The capture frame rate is not documented; `--fps` defaults to 25.

```powershell
python -m src.frames_to_video --images data/raw/airbirds/images/test --prefix D02_20210628090856 --count 1500
python -m src.frames_to_video --images data/raw/airbirds/images/val --prefix 20201111_sljc_1 --count 300 `
    --labels data/raw/airbirds/labels/val --out-dir outputs     # draw ground-truth boxes
```

Baseline: on a 300-frame val clip (1,036 ground-truth birds), the COCO-pretrained
YOLO11n finds **0** birds at both `imgsz` 640 and 1280 — fine-tuning is essential.

### Results: YOLO11n, imgsz 1280 (`models/airbirds_yolo11n_1280.pt`)

Batch 8, patience 15, `scale=0.2`, RTX 5060 laptop GPU. Early stopping ended the run
after 23 of 50 epochs (2.0 h); the best checkpoint is from epoch 8.

| Split | Images | Birds | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| val (chunk 9) | 8,312 | 39,641 | 0.356 | 0.209 | 0.139 | 0.040 |
| test (D02 0628) | 10,000 | 1,148 | 0.235 | 0.323 | 0.142 | 0.030 |

Inference is ~5 ms/image at 1280. Validation mAP50 plateaued at 0.10–0.14 from epoch 6
onwards, so the small model at this resolution is the limit, not the training length.
Next things to try: tiled (SAHI-style) training and inference so birds are larger
relative to the input, `yolo11s`, more training chunks, and longer patience.

## Optional ML risk classifier (Google Colab)

[`notebooks/risk_classifier_colab.ipynb`](notebooks/risk_classifier_colab.ipynb) trains
a classifier on **human-labelled clips** and compares it with the formula:

1. Produce `<clip>_risk.csv` with the step-by-step commands above.
2. Watch the clip and write `<clip>_labels.csv` with time ranges:
   `start_s,end_s,label` (label = Low / Medium / High).
3. Upload both to Colab and run the notebook. It cross-validates by video and compares
   the current formula, logistic regression, random forest, and **the formula with
   weights learned from your labels** (it prints suggested `risk.yaml` values).
4. Download `risk_model.json` into `models/` and use it locally:
   `python -m src.risk_scoring.risk ... --ml-model models/risk_model.json` (adds `ml_level`).

The exported model runs with NumPy only.

## Individual stages

**Detection** — `python -m src.detection.detect --source <video> --show`
(`--weights`, `--imgsz 1280`, `--conf`, `--save`, `--all-classes` for testing on non-bird footage).

**Tracking** — `python -m src.tracking.track --source <video> --show --csv <out.csv>`.
CSV columns: `frame_idx, time_s, track_id, class_id, class_name, confidence, x1, y1, x2,
y2, cx, cy, frame_w, frame_h`. Default `--conf` is 0.1 because ByteTrack uses
low-score detections to keep tracks alive.

**Runway zones** — `python -m src.risk_scoring.zone_editor --source <video or image> --out configs/zones/<cam>.json`.
Left click adds a point, right click undoes, `n` starts the next zone, `s` saves, `q` quits.
Vertices are stored as fractions of the frame size, so a zone works at any resolution.

**Features** — distances and speeds are fractions of the frame diagonal (speed 0.1 =
10% of the diagonal per second):

| Per frame | Meaning |
|---|---|
| `count` | birds tracked in the frame |
| `flock_size`, `n_flocks` | largest group of birds within `--flock-radius` of each other; number of groups |
| `max_speed`, `mean_speed` | bird speed (diag/s) |
| `min_dist_to_zone` | nearest bird's distance to a zone (0 = inside; empty if no birds) |
| `n_in_zone`, `n_approaching` | birds inside a zone; birds whose distance to a zone is shrinking |
| `hour` | time of day (needs `--start-time`) |

## Project structure

```
AviSense/
├── configs/              # airbirds.yaml (dataset), risk.yaml (scoring), zones/ (runway polygons)
├── data/
│   ├── raw/airbirds/     # AirBirds subset (see data/README.md) — git-ignored
│   ├── videos/           # test footage — git-ignored
│   └── processed/        # tracks / features / risk CSVs — git-ignored
├── models/               # fine-tuned weights, risk_model.json — git-ignored
├── notebooks/            # risk_classifier_colab.ipynb
├── outputs/              # annotated videos, alerts.db — git-ignored
├── src/
│   ├── detection/        # detect.py, train.py
│   ├── tracking/         # track.py
│   ├── risk_scoring/     # zones, zone_editor, features, risk, ml_model
│   ├── dashboard/        # app.py (Streamlit)
│   ├── pipeline.py       # end-to-end live pipeline
│   └── alert_log.py      # SQLite alert log
└── tests/
```

## Setup (Windows, NVIDIA GPU)

Developed on Python 3.14 with an RTX 5060 laptop GPU; Python 3.10+ should work.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1

# PyTorch with CUDA first. RTX 50-series (Blackwell) GPUs need CUDA 12.8+ builds (cu128).
# Check https://pytorch.org/get-started/locally/ for the current command.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

No NVIDIA GPU? Skip the PyTorch step; pip installs the CPU build (slow for training —
use Colab).

**Windows Smart App Control / Application Control:** on the development laptop it
blocks some SciPy DLLs, which also breaks scikit-learn. AviSense's core does not need
either; the ML classifier runs on Colab instead and its exported model runs with NumPy.

## Tests

```powershell
python -m pytest -q tests
```

## Datasets

- **Primary:** AirBirds (ACCV 2022) — real airport imagery with YOLO-format labels,
  from the authors' Hugging Face mirror. CC BY-NC-SA 4.0; cite Sun et al., ACCV 2022.
- **Supplementary (optional):** FBD-SV-2024 flying-bird surveillance videos, Roboflow
  Universe bird datasets, self-recorded footage.

See [`data/README.md`](data/README.md).

## Roadmap

1. ✅ Detection on video (COCO-pretrained YOLO11n)
2. ✅ Fine-tune on AirBirds — YOLO11n baseline: test mAP50 0.142 (needs improving: tiling / larger model)
3. ✅ Tracking with ByteTrack
4. ✅ Features: speed, heading, count, flock size, distance to runway polygon, time of day
5. ✅ Weighted risk score, Low/Medium/High, explainable alerts
6. ✅ Streamlit dashboard with live video, risk level, charts and SQLite alert log
7. ⏳ Evaluation: detection mAP on the test split ✅; tracking consistency and
   risk-level agreement with labelled clips (Colab notebook) still to do
