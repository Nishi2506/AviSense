#!/bin/bash
# Prepare tiles (every frame) and train the P2 + motion model on them, then test.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
# Chunk 0 is skipped: only 13% of its (camera D01) frames have the consecutive neighbours motion tiles need.
$PY -u -m src.detection.prepare_airbirds --chunks 5 6 7 test_D02_20210721142744 --temporal 2 --train-every 1 --workers 4 \
    --hard-negatives models/airbirds_tiles_temporal2_hn_yolo11n-p2_640.pt --test || exit 1
echo "=== PREP DONE $(date +%T)"
$PY -u -m src.detection.train --model configs/models/yolo11n-p2.yaml --pretrained yolo11n.pt \
    --data configs/airbirds_tiles_temporal2.yaml --imgsz 640 --batch 16 --workers 3 --epochs 80 --patience 25 \
    --name airbirds_tiles_temporal2_hn_e1_yolo11n-p2_640 \
    --test-data configs/airbirds_temporal2_test.yaml --test-imgsz 1920
echo "=== ALL DONE $(date +%T)"
