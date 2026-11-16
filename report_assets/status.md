# AviSense progress report (2026-10-08)

Taken from the repo, `runs/detect/`, `models/` and `data/processed/`. No code was changed and no training was started. To get the screenshots I ran the existing pipeline and dashboard on the two test clips. These were inference runs only, with outputs written to a temp folder. `outputs/alerts.db` was backed up and restored byte for byte. The test suite passes (50 / 50).

## 1. Status by stage

**Dataset: done**
- AirBirds (ACCV 2022, CC BY-NC-SA, birds about 5–10 px in 1920×1080 frames).
- Train: chunks 5, 6, 7 plus the D02 2021-07-21 sequence, every consecutive frame, plus hard negatives. That gives 30,380 motion-stacked 640×640 tiles.
- Val: chunk 9 plus the held-out D02 2021-07-28 sequence.
- Test: the D02 2021-06-28 sequence (10,000 frames, 1,148 birds).
- Only the labels are on the laptop. The images (about 135 GB) were downloaded, tiled and deleted chunk by chunk.

**Detection training: done**
- 8 models trained so far. The current best is `airbirds_tiles_temporal2_hn_e1_yolo11n-p2_640.pt` (YOLO11n with an extra P2 small-object head and 3-frame motion input).
- Test mAP50 went from 0.142 (first model) to 0.761.

**Tracking: done, still being tuned**
- ByteTrack with enlarged matching boxes (60 px) and a 20 px motion filter that removes static false detections.
- On the test sequence it reaches precision 0.80 and recall 0.618 (tracked-box confidence ≥ 0.3). False alarms appear in 1.8% of frames.

**Risk scoring: done for the formula; the ML part is not started**
- A weighted, explainable formula (count, speed, runway proximity, flock size, time of day) gives Low (< 0.3), Medium (0.3–0.6) or High (≥ 0.6).
- Alerts are grouped into episodes and saved to SQLite.
- The weights are hand-set and have not been checked against labelled clips.
- The optional ML classifier (Colab notebook) exists, but there are no human-labelled clips and no `models/risk_model.json`, so it has never been trained.

**Dashboard: done and working**
- Streamlit app with:
  - annotated live video
  - a Low / Medium / High risk tile
  - bird statistics
  - a chart of each factor's contribution
  - a risk-over-time chart
  - pop-up alerts and the alert history
- I ran it end to end on the D02 test clip today.

## 2. Training (latest run: `runs/detect/airbirds_tiles_temporal2_hn_e1_yolo11n-p2_640`)

- **State:** finished, not running. No Python process or GPU load right now. Last write was 2026-10-03 07:51.
- **Epochs:** stopped early at epoch 72 of 80 (patience 25). The best epoch was 47. Training took 6.4 h on an RTX 5060 laptop GPU.
- **Model:** YOLO11n with a P2 head (`configs/models/yolo11n-p2.yaml`), batch 16. Each input's channels are greyscale frames t−4, t−2 and t (motion input).
- **Image size:** 640 for training (native-resolution tiles); 1920 for inference and test (full frames).
- **Data:** see the Dataset section above.
- **Train images:** 30,380 tiles. This matches 1,899 batches × 16 per epoch.
- **Val images:** count not recorded. The tiles were deleted after training and no log kept the number.
- **Test metrics (D02 2021-06-28, full frames at 1920), the numbers to quote:**
  - precision **0.755**
  - recall **0.762**
  - mAP50 **0.761**
  - mAP50-95 **0.293**
- **Val metrics at the best epoch (47):** precision 0.430, recall 0.391, mAP50 0.275, mAP50-95 0.072. At the last epoch (72): 0.423 / 0.400 / 0.270 / 0.071.
- **Why val is much lower than test:** val is mostly chunk 9, which comes from other cameras (sljc, IP, sw, xw) that are not in training. Test uses the training camera, D02.
- **Speed:**
  - pipeline from the command line: 12 FPS on full 1920×1080 video (measured today)
  - dashboard: about 5–6 FPS

## 3. Images in this folder

| File | Caption |
|---|---|
| `01_training_curves.png` | Loss and metric curves over 72 epochs; val metrics stop improving after about epoch 25. |
| `02_confusion_matrix_val.png` | Confusion matrix (bird vs background) on the validation set. |
| `03_PR_curve_val.png` | Precision–recall curve on the validation set (mAP50 0.27, mixed cameras). |
| `04_confusion_matrix_test.png` | Confusion matrix on the D02 test sequence. |
| `05_PR_curve_test.png` | Precision–recall curve on the D02 test sequence (mAP50 0.76). |
| `06_val_batch0_pred.jpg` | Model predictions on a batch of validation tiles. |
| `07_val_batch1_pred.jpg` | Model predictions on a second batch of validation tiles. |
| `08_test_batch0_pred.jpg` | Model predictions on test frames (motion-stacked, so moving birds appear as coloured dots). |
| `09_test_batch0_labels.jpg` | Ground-truth boxes for the same test frames, for comparison with 08. |
| `10_dashboard_start_page.png` | The dashboard before a run: sidebar controls and the alert history. |
| `11_pipeline_risk_LOW_D02_frame120.png` | Pipeline output frame: one tracked bird (#18) far from the runway, so risk is LOW (0.25). |
| `12_pipeline_risk_MEDIUM_D02_frame200.png` | The same bird descending towards the runway zone (red), so risk is MEDIUM (0.39) because of proximity. |
| `13_tracking_id18_trail_D02_zoom.png` | Zoom on frame 200: bird #18 with its confidence (0.46) and flight trail. |
| `14_tracking_3birds_sljc_frame165.png` | Second camera (sljc): three birds tracked at once with separate IDs. |
| `15_tracking_ids127_140_sljc_zoom.png` | Zoom on frame 165: birds #127 and #140, each with its own ID, confidence and trail. |
| `16_tracking_id52_near_runway_D02_zoom.png` | Zoom: bird #52 flying low just above the runway zone, risk MEDIUM 0.37. |
| `17_dashboard_LOW.png` | Live dashboard: LOW tile (0.17), bird statistics and factor contributions. |
| `18_dashboard_MEDIUM.png` | Live dashboard: MEDIUM tile (0.39), with runway proximity as the largest factor. |
| `19_dashboard_MEDIUM_alert_active.png` | Live dashboard 30 s in: MEDIUM with "ALERT active · driven by Runway proximity", three alert peaks on the timeline, and the alert logged in the table. |

- **No High-risk screenshot.** Neither test clip ever reaches High. The highest scores are 0.43 (D02) and 0.34 (sljc), against the 0.6 threshold.
- **Why High is out of reach on these clips:** with the current weights, a single bird inside the runway zone at dawn scores only about 0.55. Reaching High needs a flock near the runway. These clips have at most 1–4 birds, so I left High out rather than fake it.

## 4. Today's pipeline run (D02 clip, 1,500 frames)

- Frames at each level: Low 1,283, Medium 217, High 0.
- Three Medium alert episodes, at 7.0–8.7 s, 18.4–19.8 s and 27.1–32.6 s. All were driven by runway proximity and involved one bird.
- These are the same three episodes as in the earlier saved run.

## 5. Problems, gaps and decisions

**Broken or misleading**
- `python -m src.pipeline` (and `detect` / `track`) default to the COCO `yolo11n.pt`, which finds 0 birds. You must pass `--weights models/airbirds_tiles_temporal2_hn_e1_yolo11n-p2_640.pt`. Only the dashboard defaults to the right model.
- The dashboard's start-time box moves in 1-minute steps and drops the seconds (09:08:56 becomes 09:08). Wall-clock times in its alert log can be up to 59 s early. This is minor.
- The tracker sometimes gives the same bird two IDs: 6 frames in the sljc clip (for example, IDs 81 and 102 at the same spot in frame 116). This can inflate bird counts.

**Slow**
- 12 FPS from the command line and about 5–6 FPS in the dashboard, against the 26 FPS in the README (measured with an older model). Real-time 25 FPS camera feeds would fall behind.
- Each training run takes 3–6 h locally. A Colab path exists.

**Missing**
- **High risk has never been shown** on real footage. No clip has a flock near the runway.
- Risk weights and thresholds are hand-set and have not been checked against labelled data.
- The ML risk classifier needs human-labelled clips (Low/Medium/High time ranges), and none exist yet.
- Only two short AirBirds clips are set up as test videos, and no self-recorded footage. Runway zones were traced by hand from a single frame.
- Validation set size is not recorded for the latest run.
- **Tracking recall is limited:** tracking recall (0.618) is well below detector recall (0.762), because short bird visits of 5 frames or fewer are often missed.

**Decisions for you**
1. **How to show High risk.** Options:
   - (a) Make a clip from the 43-bird flock sequence `D02_20210728064810`. Its images would need to be downloaded again (it is part of chunk 7, 12–22 GB).
   - (b) Show High by lowering the thresholds in the dashboard sidebar, clearly labelled as a demo setting.
   - (c) Report that High is not yet demonstrated.
2. **Whether to re-tune the risk weights** so a single bird inside the runway zone can reach High. This is a safety-policy choice.
3. **Which way to tune tracking.** A 60 px matching box (current) favours recall in flocks; 40 px favours fewer false alarms.
4. **Whether to label clips** so the risk classifier can be trained and the formula weights validated.
5. **Whether real-time speed matters for the presentation**, or offline video processing is enough for now.
