# AviSense Risk Labelling Guide

**For:** the AI assistant helping a human annotator label bird-strike risk in short airport video clips.
**Project:** AviSense, a college project (camera-based bird-strike risk detection and alerts for airports).

---

## 0. How to use this guide

- You are the **annotator's assistant**. The **human makes the final call** on every label. Your job is to prepare the clips for viewing, suggest labels with reasons, keep the files tidy and run the checks below.
- Risk is a judgement. Do not state a label as fact when you are unsure; mark low confidence instead (see section 6).
- If something promised in section 3 is missing (clips, frame rate, runway zone, template), **stop and ask** instead of guessing.

## 1. Why we need these labels

The AviSense system detects and tracks birds, then computes a risk score from five factors (bird count, speed, distance to the runway zone, flock size, time of day) and turns it into **Low / Medium / High**. The weights in that formula were set by hand and have never been checked against human judgement.

Your labels will be used to:
1. check whether the formula agrees with human judgement, and
2. train an optional machine-learning risk classifier.

**For this to be valid, the labels must come from human judgement alone.** Never base a label on any risk score, risk colour or dashboard output. You will not be given any, and if you see one, ignore it and tell Nishita.

## 2. What exactly is being labelled

For every clip, split the whole timeline into **non-overlapping time segments** and give each segment one level: **Low**, **Medium** or **High**.

Judge only the **bird situation relative to the runway zone**. Do not guess whether an aircraft is present; the project has no aircraft data.

## 3. What you will receive

Check that all of this is present before starting:

| Item | What it is |
|---|---|
| `clips/clip_001.mp4 ...` | Short clips with a burned-in timestamp (seconds). Birds are marked with boxes because they are only about 5 to 10 pixels wide and almost invisible without them. The runway zone is drawn as a red polygon. |
| `storyboards/clip_001.png ...` | One frame per second, in a grid with timestamps, for assistants that cannot read video. |
| `clips_index.csv` | `clip_id, fps, duration_s, time_of_day, notes` |
| `labels_template.csv` | Empty file with the correct columns (section 6). |
| This guide | |

Clip names are neutral on purpose, so you cannot tell which camera or sequence a clip came from. Do not try to find out.

## 4. The labelling rubric

> **Decision needed before labelling starts (Nishita and her team):** can a **single** bird inside the runway zone count as **High**? The draft below says **no** (single bird = Medium; High needs a flock or a fast, low crossing). Confirm or change this first, because it changes many labels. Write the final decision here: `[ DECIDED: ______ ]`

### Questions to ask for each moment
1. **How many birds are in view?**
2. **Where are they relative to the red runway zone?** Inside it, touching or just above it, approaching it, circling nearby, or clearly far away.
3. **How are they moving?** Towards the zone, away from it, crossing it, hovering or circling. Fast and low is more dangerous than slow and high.
4. **Is there a flock?** Roughly three or more birds close together and moving together.
5. **Time of day** is context only (dawn and dusk usually have more activity). Do not raise a label for time of day alone.

### Levels

| Level | Use when |
|---|---|
| **Low** | No birds, or only a few birds that are clearly far from the runway zone and not heading towards it. |
| **Medium** | At least one bird is inside or touching the runway zone or clearly moving towards it; **or** a larger group is present in the scene but not yet near the zone. |
| **High** | A flock (about 3 or more together) is inside, over or heading straight for the runway zone; **or** birds are crossing the zone fast and low; **or** many birds are converging on the zone. A situation where a pilot would have very little time to avoid contact. |

### Tie-break rules
- **When torn between two levels, pick the lower one and lower the confidence to 1.** Do not average or split the difference.
- **Look at the trend.** A bird clearly approaching the zone can be labelled Medium a little before it arrives; do not wait until it is inside.
- **Short events:** a level must last **at least 1 second** to become its own segment. Anything shorter is merged into the neighbouring segment.
- **Birds leaving:** when the birds leave the zone, drop the level once they are clearly moving away or out of view.
- **Occlusion or blur:** if you cannot tell what is happening, label by the most likely situation and set confidence to 1 with a note.

## 5. Workflow (step by step)

1. Read `clips_index.csv` and note each clip's `fps` and `duration_s`.
2. For each clip, watch the video or study its storyboard. Write a short timeline (what happens and when) before giving any label.
3. Suggest segments with reasons, using the rubric questions in section 4.
4. **The human reviews, corrects and approves.** Only approved segments go into the CSV.
5. Fill `labels_template.csv`, run the check in section 7, and fix any errors.
6. Repeat for the next clip.

Label every clip **independently**. Do not look back at earlier clips to keep labels consistent. Consistency should come from the rubric.

## 6. Output format

A CSV with exactly these columns:

```
clip_id,start_s,end_s,risk_level,confidence,notes,annotator
```

| Column | Rule |
|---|---|
| `clip_id` | Exactly as in `clips_index.csv`, e.g. `clip_007`. |
| `start_s`, `end_s` | Seconds from the start of the clip, with up to 2 decimals. `start_s` < `end_s`. |
| `risk_level` | Exactly `Low`, `Medium` or `High` (capital first letter, nothing else). |
| `confidence` | `1` = unsure, `2` = fairly sure, `3` = certain. |
| `notes` | Short reason, e.g. "3 birds heading into zone". Never put commas inside notes; use semicolons. |
| `annotator` | The human's name or initials. |

Rules:
- Segments of a clip must **cover the whole clip**: the first starts at `0` and the last ends at `duration_s`.
- No gaps and no overlaps: each segment starts exactly where the previous one ended.
- Neighbouring segments should have different levels; merge them if they are the same.

Example:

```
clip_007,0,6.5,Low,3,no birds in view,AB
clip_007,6.5,9.0,Medium,2,one bird approaching zone,AB
clip_007,9.0,12.5,High,2,3 birds crossing zone low and fast,AB
clip_007,12.5,20.0,Low,3,birds left the scene,AB
```

## 7. Checks to run before returning the file

Save this as `check_labels.py` and run it as `python check_labels.py labels.csv clips_index.csv`.

```python
import csv
import sys

labels_file = sys.argv[1]
index_file = sys.argv[2]

allowed_levels = ["Low", "Medium", "High"]

# Read how long each clip is.
durations = {}
with open(index_file, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        durations[row["clip_id"]] = float(row["duration_s"])

# Read the labels and group them by clip.
segments = {}
with open(labels_file, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        clip = row["clip_id"]
        if clip not in segments:
            segments[clip] = []
        segments[clip].append(row)

problems = 0

for clip in durations:
    if clip not in segments:
        print("MISSING: no labels for", clip)
        problems = problems + 1
        continue

    rows = sorted(segments[clip], key=lambda r: float(r["start_s"]))
    expected_start = 0.0

    for row in rows:
        start = float(row["start_s"])
        end = float(row["end_s"])

        if abs(start - expected_start) > 0.01:
            print("GAP OR OVERLAP in", clip, "near", start)
            problems = problems + 1
        if end <= start:
            print("BAD TIME RANGE in", clip, "at", start)
            problems = problems + 1
        if row["risk_level"] not in allowed_levels:
            print("BAD LEVEL in", clip, ":", row["risk_level"])
            problems = problems + 1
        if row["confidence"] not in ["1", "2", "3"]:
            print("BAD CONFIDENCE in", clip, ":", row["confidence"])
            problems = problems + 1

        expected_start = end

    if abs(expected_start - durations[clip]) > 0.05:
        print("LABELS DO NOT REACH THE END of", clip)
        problems = problems + 1

# Count how many seconds each level covers, to see the balance.
totals = {"Low": 0.0, "Medium": 0.0, "High": 0.0}
for clip in segments:
    for row in segments[clip]:
        level = row["risk_level"]
        if level in totals:
            totals[level] = totals[level] + (float(row["end_s"]) - float(row["start_s"]))

print("Seconds per level:", totals)
print("Problems found:", problems)
```

Fix every problem it reports before sending the file back.

## 8. Agreement check (a second annotator on a subset)

Nishita will independently label about 10 of the same clips. Do **not** see her labels beforehand. Afterwards the two sets are compared to measure how well humans agree. Where you disagree, discuss and note the final decision; do not silently overwrite.

## 9. Things you must not do

- Do not use or ask for any risk score, risk colour or alert from the AviSense system.
- Do not try to identify the camera, date or original dataset sequence of a clip.
- Do not label the whole clip with one level just because it is easier; segments must follow what happens.
- Do not invent events you cannot see. Use low confidence and a note instead.
- Do not share the clips outside the project. They come from a dataset licensed for non-commercial use (CC BY-NC-SA).

## 10. What to send back

1. `labels.csv` in the format above, with the check in section 7 showing **0 problems**.
2. A short note: how many clips were labelled, anything unclear in the rubric, and any clips where you were unsure.
