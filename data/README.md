# Data

Nothing in this folder is committed to git (except this file and `.gitkeep` placeholders).

| Folder | Contents |
|---|---|
| `raw/airbirds/` | AirBirds dataset (ACCV 2022) — YOLO-format images + labels. Download separately. |
| `videos/` | Test videos / self-recorded footage for running the pipeline. |
| `processed/` | Generated artifacts: per-track features, CSV logs, etc. |

Supplementary sources (CUB-200-2011, Roboflow Universe bird sets) can go in
additional subfolders under `raw/`, e.g. `raw/roboflow_birds/`.

The expected YOLO layout for training is:

```
raw/airbirds/
├── images/{train,val,test}/*.jpg
└── labels/{train,val,test}/*.txt
```

Once downloaded, confirm the actual layout matches before writing the dataset YAML.
