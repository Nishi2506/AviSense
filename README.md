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
| Fine-tuning on AirBirds (native-resolution tiles) | `src/detection/make_tiles.py`, `train.py`, `configs/airbirds_tiles.yaml` | ✅ test mAP50 0.602 |
| Tracking (ByteTrack, enlarged-box matching for tiny birds) | `src/tracking/track.py` | ✅ |
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

Zones for the two AirBirds cameras used in testing are included:
[`configs/zones/D02.json`](configs/zones/D02.json) (test sequence) and
[`configs/zones/sljc.json`](configs/zones/sljc.json) (`20201112_sljc_2_rest`, val). They
cover the paved strip visible behind the runway edge lights and were traced from a
single frame, so check them against your own view before relying on them.

For the best detector, pick `models/airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt` (the dashboard default) with **image size
1920** (see [Training](#training-on-airbirds) for why).

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
    --weights models/airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt --imgsz 1920 --save outputs/pipeline.mp4 --db outputs/alerts.db
```

Or step by step, producing CSVs at each stage (used for the ML notebook and analysis):

```powershell
python -m src.tracking.track --source data/videos/<clip>.mp4 --csv data/processed/<clip>_tracks.csv `
    --weights models/airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt --imgsz 1920
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

Birds are ~5–10 px in 1920×1080 frames. Training on full frames at `imgsz` 1280
shrinks them further, so the recommended setup trains on **640×640 crops at native
resolution** and runs the model on **full frames at `imgsz` 1920**. YOLO is fully
convolutional, so a bird is the same pixel size in training and at inference, and
tracking and the pipeline work on whole frames unchanged.

```powershell
# Tiled (recommended): cut train + val into 640 px tiles in data/processed/airbirds_tiles (~8.4 GB)
python -m src.detection.make_tiles --train-every 2
python -m src.detection.train --data configs/airbirds_tiles.yaml --imgsz 640 --batch 32 --epochs 80 `
    --patience 25 --name airbirds_tiles_c0567_yolo11n_640 --test-data configs/airbirds.yaml --test-imgsz 1920

# Full frames (original baseline)
python -m src.detection.train                               # yolo11n, imgsz 1280, 50 epochs, batch 8

python -m src.detection.train --resume --name <run>          # continue an interrupted run
python -m src.detection.train --evaluate models/airbirds_tiles_c0567_yolo11n_640.pt `
    --test-data configs/airbirds.yaml --imgsz 1920          # test split only
```

`make_tiles` keeps every tile with a bird, 10% of empty tiles (`--empty-keep`), every
2nd train frame (`--train-every`) and every 4th val frame (`--val-every`; consecutive
frames are near-duplicates). With chunks 0, 5, 6, 7: train 19,204 frames → 33,318 tiles;
val 2,476 frames → 6,105 tiles. Training uses a milder scale
augmentation (`scale=0.2`) so birds aren't shrunk to nothing. Runs are saved in
`runs/detect/`; the best weights are copied to `models/<run name>.pt` and evaluated on
the full-frame test split. Plug the laptop in and use the Best Performance power
mode — on battery the GPU is heavily throttled.

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

### Results

Test split = D02 0628, 10,000 full frames, 1,148 birds. RTX 5060 laptop GPU.

| Model (`models/…`) | Training data | Training | Test imgsz | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|---|
| `airbirds_yolo11n_1280.pt` | chunk 0 (D01) | full frames @1280, batch 8; stopped at epoch 23 (best 8), 2.0 h | 1280 | 0.235 | 0.323 | 0.142 | 0.030 |
| `airbirds_tiles_yolo11n_640.pt` | chunk 0 (D01) | tiles @640, batch 32; stopped at epoch 58 (best 33), 2.4 h | 1920 | 0.223 | 0.462 | 0.241 | 0.071 |
| `airbirds_tiles_yolo11s_640.pt` | chunk 0 (D01) | tiles @640, batch 16; stopped at epoch 57 (best 32), 4.0 h | 1920 | 0.183 | 0.503 | 0.169 | 0.050 |
| `airbirds_tiles_c0567_yolo11n_640.pt` | chunks 0, 5, 6, 7 (D01 + D02) | tiles @640, batch 32; stopped at epoch 52 (best 27), 3.1 h | 1920 | 0.464 | 0.687 | 0.602 | 0.197 |
| `airbirds_tiles_temporal2_yolo11n_640.pt` | chunks 0, 5, 6, 7 — consecutive frames only | **motion input**, batch 16; stopped at epoch 43 (best 18), 1.3 h | 1920 | 0.597 | 0.625 | 0.603 | 0.203 |
| `airbirds_tiles_hn_yolo11n-p2_640.pt` | chunks 0, 5, 6, 7 + hard negatives | **P2 head**, batch 16; stopped at epoch 42 (best 17), 4.5 h | 1920 | 0.671 | **0.782** | 0.729 | 0.250 |
| **`airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt`** | **chunks 0, 5, 6, 7 + D02 2021-07-21, consecutive frames, hard negatives** | **P2 head + motion input**, batch 16; stopped at epoch 48 (best 23), 2.8 h | 1920 | **0.714** | **0.782** | **0.770** | **0.276** |

**Current best: `airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt`** (dashboard default), combining four improvements:

1. **Training on the test camera's view.** Chunk 0 is entirely camera D01, the test
   sequence camera D02. Adding chunks 5–7 (24,683 D02 frames from other days) raised
   test mAP50 from 0.241 to 0.602.
2. **A P2 detection head** ([`configs/models/yolo11-p2.yaml`](configs/models/yolo11-p2.yaml)):
   an extra stride-4 output, so a ~6 px bird covers ~2×2 feature cells instead of one.
3. **Hard negatives** (`make_tiles --hard-negatives`): bird-free tiles where the previous
   model fired falsely are added to training. With the P2 head: mAP50 0.602 → 0.729.
4. **Motion input** ([`src/detection/temporal.py`](src/detection/temporal.py)): the three
   channels are greyscale frames t−4, t−2, t, so a moving bird shows as three offset
   coloured dots and static clutter stays grey. Needs consecutive frames, so training
   uses only those (plus the separately labelled D02 sequence from 2021-07-21, a
   different day from the test sequence). Hue/saturation augmentation is disabled for
   these images. Combined with 2 and 3: precision 0.671 → 0.714, mAP50 → 0.770.

Diagnosis behind these choices (tiled YOLO11n, test split): at confidence ≥ 0.3 the
detector already put a box within 10 px of 99.8% of birds, so the gap was (a) false
positives on sky specks and horizon clutter and (b) box placement — birds are a median
**6 px**, and 18% of correct detections had IoU < 0.5 with the label, which mAP50 counts
as a miss. **mAP50-95 cannot approach 0.8 on this data:** for a 6×6 px box a one-pixel
offset already gives IoU ≈ 0.7, and the labels themselves are not pixel-exact. Test-time
augmentation (flips/scales) made results worse (mAP50 0.770 → 0.695).

Earlier findings: native-resolution tiles (vs. full frames at 1280) had raised mAP50 by 70%. The larger Native-resolution tiles (vs. full frames at 1280) had raised mAP50 by 70%. The larger
`yolo11s` matched `yolo11n` on validation (mAP50 ~0.20) but did worse on the test
camera: slightly higher recall, more false positives. `yolo11n` tiles is the default. The
full-frame model plateaued at val mAP50 0.10–0.14 from epoch 6; the tiled model kept
improving until epoch 33. Detector precision is low (~0.22): it fires on specks of sky
and horizon clutter. Most of these don't move, which the tracker uses to drop them —
see the next section. The end-to-end pipeline runs at ~26 FPS on full 1920×1080 video
with the tiled model (laptop on AC power, Best Performance mode).

### Tracking against ground truth

[`src/evaluate_tracking.py`](src/evaluate_tracking.py) runs the tracker over a labelled
sequence and matches tracked birds to ground-truth birds (centre within 15 px):

```powershell
python -m src.evaluate_tracking --images data/raw/airbirds/images/test --labels data/raw/airbirds/labels/test `
    --prefix D02_20210628090856 --tracks-csv data/processed/eval_test_D02.csv --min-motion 0 10 20
```

The test sequence (10,000 consecutive frames, 1,148 birds in 1,097 frames) is the
main benchmark. With the D01-only tiled model, 91% of the false-alarm boxes came from
tracks that never moved (median displacement 0.01 px), while real birds move ~3 px per
frame. Reporting a track only after it has moved 20 px (`--min-motion`, the default)
removes most of them. Test sequence, conf 0.1:

| Detector | Matching box (`--assoc-size`) | Motion filter | Precision | Recall | Frames with a false alarm |
|---|---|---|---|---|---|
| D01-only tiles | 40 px | none | 0.058 | 0.680 | 50.9% |
| D01-only tiles | 40 px | ≥ 20 px | 0.454 | 0.599 | 7.7% |
| D01 + D02 tiles | 40 px | ≥ 20 px | **0.551** | 0.623 | **5.7%** |
| **D01 + D02 tiles (default)** | **60 px** | **≥ 20 px** | 0.457 | 0.679 | 8.9% |
| D01 + D02 tiles | 80 px | ≥ 20 px | 0.414 | **0.740** | 11.0% |

**Flocks.** The test sequence has at most 2 birds at once. In the held-out D02 sequence
(`D02_20210728064810`) a flock of up to 43 birds crosses the sky; in a tight flock a
40 px matching box confuses neighbours, IDs switch, and each new ID must travel 20 px
again before it is reported. On its two longest *continuous* stretches (the sequence
is otherwise cut into 442 short runs, median 2 frames, so the rest isn't a fair tracking
test), with the 20 px motion filter:

| Flock stretch | 40 px: precision / recall | 60 px: precision / recall | 80 px: precision / recall |
|---|---|---|---|
| 90 frames, ~13 birds/frame | 0.877 / 0.323 | 0.884 / **0.575** | 0.814 / 0.627 |
| 47 frames, ~18 birds/frame | 0.798 / 0.228 | 0.693 / **0.439** | 0.700 / 0.502 |

With the current best model (motion input + P2, conf 0.1, 60 px, ≥ 20 px motion) tracking
precision is 0.695 and recall 0.552, with a false alarm in 2.8% of frames; keeping only
tracked boxes with confidence ≥ 0.3 gives precision **0.801**, recall 0.533 and 1.5%
false-alarm frames. Tracking recall is lower than the detector's (0.782) mainly because a
track is reported only after ByteTrack has matched it in consecutive frames and it has
moved 20 px: in the test sequence birds appear in 167 short visits (median 2 frames,
24% of labelled birds in visits of ≤ 5 frames). Recall is 0.37–0.48 in a visit's first
three frames and ~0.89 from the tenth frame (0.4 s) on. Lowering ByteTrack's thresholds
([`configs/bytetrack_birds.yaml`](configs/bytetrack_birds.yaml), `--tracker`) did not help
(recall 0.533).

The default is 60 px: it nearly doubles recall in flocks — the most dangerous case for
strikes — for a moderate precision cost on sparse scenes. Use `--assoc-size 40` if
false alarms matter more than missed birds.

The motion filter's cost: a bird that never moves at all (e.g. standing on the runway
the whole time) is not reported; set `--min-motion 0` to keep everything. Results are
similar for 10–30 px.

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
ByteTrack links boxes across frames by overlap, but AirBirds birds are ~7 px and move
6–10 px per frame (median IoU between frames ~0.03), so plain ByteTrack almost never
confirms a track. The tracker matches on boxes enlarged to at least `--assoc-size`
(default 60 px) around each centre and reports the original boxes. With 40 px, on 300 val frames (554
ground-truth birds) tracked detections went from 24 to 457. Tracks are reported once
they have moved `--min-motion` px (default 20) — see
[Tracking against ground truth](#tracking-against-ground-truth).
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
2. ✅ Fine-tune on AirBirds — native-resolution tiles, D01 + D02 cameras: test mAP50 0.602 (full-frame D01-only baseline 0.142)
3. ✅ Tracking with ByteTrack (enlarged-box matching for tiny, fast birds)
4. ✅ Features: speed, heading, count, flock size, distance to runway polygon, time of day
5. ✅ Weighted risk score, Low/Medium/High, explainable alerts
6. ✅ Streamlit dashboard with live video, risk level, charts and SQLite alert log
7. ⏳ Evaluation: detection mAP on the test split ✅; tracking precision/recall against
   ground truth ✅; risk-level agreement with labelled clips (Colab notebook) still to do
