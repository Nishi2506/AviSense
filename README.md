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
| Frame extraction + detection | `src/detection/detect.py` | ✅ Working starter |
| Tracking (ByteTrack via `model.track()`) | `src/tracking/track.py` | ✅ Working starter |
| Runway zones (polygons) | `src/risk_scoring/zones.py`, `zone_editor.py` | ✅ Working starter |
| Feature extraction | `src/risk_scoring/features.py` | ✅ Working starter |
| Risk scoring + classification | `src/risk_scoring/` | ⏳ Planned |
| Dashboard + alerts | `src/dashboard/` | ⏳ Planned |

## Risk scoring

A transparent weighted formula, not a black box:

```
risk_score = w1·count + w2·speed + w3·proximity_to_runway_zone + w4·flock_size + w5·time_of_day
```

Each feature is normalised to [0, 1] and the weights sum to 1, so the score is in [0, 1]:

| Level | Score |
|---|---|
| 🟢 Low | < 0.3 |
| 🟡 Medium | 0.3 – 0.6 |
| 🔴 High | > 0.6 |

Weights and thresholds are tunable. An optional scikit-learn classifier can be compared
against the formula as a baseline.

## Project structure

```
AviSense/
├── data/
│   ├── raw/airbirds/     # AirBirds dataset (download separately — see data/README.md)
│   ├── videos/           # test footage
│   └── processed/        # extracted features, logs
├── models/               # trained / fine-tuned weights (.pt) — git-ignored
├── configs/              # dataset YAMLs (airbirds.yaml), zones/ (runway polygons)
├── notebooks/            # exploration, training, evaluation
├── outputs/              # annotated videos, reports — git-ignored
├── src/
│   ├── detection/        # YOLO bird detection
│   ├── tracking/         # ByteTrack multi-object tracking
│   ├── risk_scoring/     # features + risk formula + classifier
│   └── dashboard/        # Streamlit app
├── tests/
├── requirements.txt
└── README.md
```

## Setup (Windows, NVIDIA GPU)

**Python:** use **3.10 – 3.12**. Newer versions may not yet have wheels for all
dependencies.

```powershell
# 1. Create and activate a virtual environment
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install PyTorch with CUDA FIRST.
#    RTX 50-series (Blackwell) GPUs need CUDA 12.8+ builds (cu128).
#    Check https://pytorch.org/get-started/locally/ for the current command.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 3. Install the rest
pip install -r requirements.txt

# 4. Verify the GPU is visible
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

No NVIDIA GPU? Skip step 2. pip will install the CPU build, which is slower but
fine for development. Use Google Colab for training.

## Running detection

Put a test video in `data/videos/`, then from the project root:

```powershell
# Live preview (press q to quit)
python -m src.detection.detect --source data/videos/sample.mp4 --show

# Save an annotated video
python -m src.detection.detect --source data/videos/sample.mp4 --save outputs/annotated.mp4

# Webcam
python -m src.detection.detect --source 0 --show

# Use your fine-tuned AirBirds weights
python -m src.detection.detect --source data/videos/sample.mp4 --weights models/airbirds_best.pt --show
```

On the first run, `yolo11n.pt` (COCO-pretrained, about 5 MB) downloads automatically.
Detection is filtered to the `bird` class by default. Pass `--all-classes` to turn
this off.

Useful flags: `--conf 0.25` (confidence threshold), `--imgsz 640` (use a larger value
such as 1280 for small or distant birds), `--device 0` or `--device cpu`.

## Running tracking

Tracking assigns each bird a persistent ID, draws motion trails, and can export
one CSV row per bird per frame (input to feature extraction):

```powershell
python -m src.tracking.track --source data/videos/sample.mp4 --show
python -m src.tracking.track --source data/videos/sample.mp4 --save outputs/tracked.mp4 --csv data/processed/tracks.csv
```

CSV columns: `frame_idx, time_s, track_id, class_id, class_name, confidence,
x1, y1, x2, y2, cx, cy, frame_w, frame_h`. The default `--conf` is 0.1 because
ByteTrack uses low-score detections to keep tracks alive.

## Runway zones and features

Draw the runway (and any other protected areas) once per camera. Vertices are
saved as fractions of the frame size, so the file works at any resolution:

```powershell
python -m src.risk_scoring.zone_editor --source data/videos/sample.mp4 --out configs/zones/cam1.json --names runway
```

Left click adds a point, right click undoes, `n` starts the next zone, `s` saves, `q` quits.

Then turn a tracks CSV into features:

```powershell
python -m src.risk_scoring.features --tracks data/processed/tracks.csv --zones configs/zones/cam1.json `
    --out data/processed/frame_features.csv --start-time 2021-06-28T09:08:56
```

Distances and speeds are fractions of the frame diagonal (speed 0.1 = 10% of the
diagonal per second).

| Per frame | Meaning |
|---|---|
| `count` | birds tracked in the frame |
| `flock_size`, `n_flocks` | largest group of birds within `--flock-radius` of each other; number of groups |
| `max_speed`, `mean_speed` | bird speed (diag/s) |
| `min_dist_to_zone` | nearest bird's distance to a zone (0 = inside; empty if no birds) |
| `n_in_zone`, `n_approaching` | birds inside a zone; birds whose distance to a zone is shrinking |
| `hour` | time of day (needs `--start-time`) |

## Tests

```powershell
python -m pytest -q tests
```

## Datasets

- **Primary:** AirBirds (ACCV 2022): real airport imagery with YOLO-format bounding boxes.
- **Supplementary:** CUB-200-2011, Roboflow Universe bird datasets, self-recorded footage.

See [`data/README.md`](data/README.md) for where to place them.

## Roadmap

1. ✅ Detection on video (COCO-pretrained YOLO11n)
2. Fine-tune on AirBirds (`notebooks/`), save best weights to `models/`
3. ✅ Tracking with ByteTrack (`model.track(persist=True, tracker="bytetrack.yaml")`)
4. ✅ Per-track features: speed, heading, count, flock size, distance to runway zone polygon
5. Weighted risk score and Low/Med/High classification
6. Streamlit dashboard with live video, risk gauge and alert log (SQLite)
7. Evaluation: detection mAP, tracking consistency, risk-level agreement with labelled clips
