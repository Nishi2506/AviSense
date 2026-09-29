import pytest

from src.detection.make_tiles import tile_labels, tile_origins


def test_tile_origins_cover_frame_with_even_overlap():
    assert tile_origins(1920, 640) == [0, 640, 1280]
    assert tile_origins(1080, 640) == [0, 440]  # two tiles overlapping by 200 px
    assert tile_origins(500, 640) == [0]


def test_box_inside_tile_is_shifted_and_normalised():
    [line] = tile_labels([(0, 650.0, 450.0, 660.0, 460.0)], 640, 440, 640, 0.5)
    c, cx, cy, w, h = line.split()
    assert c == "0"
    assert float(cx) == pytest.approx(15 / 640, abs=1e-6) and float(cy) == pytest.approx(15 / 640, abs=1e-6)
    assert float(w) == pytest.approx(10 / 640, abs=1e-6) and float(h) == pytest.approx(10 / 640, abs=1e-6)


def test_cut_boxes_kept_only_if_mostly_visible():
    mostly_in = (0, 630.0, 0.0, 642.0, 10.0)   # 10 of 12 px wide inside tile x0=0
    mostly_out = (0, 638.0, 0.0, 650.0, 10.0)  # 2 of 12 px inside
    outside = (0, 700.0, 0.0, 710.0, 10.0)
    assert len(tile_labels([mostly_in, mostly_out, outside], 0, 0, 640, 0.5)) == 1


def test_hard_negative_tiles_are_kept(tmp_path, monkeypatch):
    import cv2
    import numpy as np
    from src.detection import make_tiles as mt

    monkeypatch.setattr(mt, "SRC", tmp_path / "src")
    for d in ("src/images/train", "src/labels/train", "dst/images/train", "dst/labels/train"):
        (tmp_path / d).mkdir(parents=True)
    img = tmp_path / "src/images/train/f_0000001.png"
    cv2.imwrite(str(img), np.zeros((1080, 1920, 3), np.uint8))
    (tmp_path / "src/labels/train/f_0000001.txt").write_text("")  # no birds

    dst = tmp_path / "dst"
    assert mt.process_frame(img, "train", 640, 0.0, 0.5, dst=dst)[0] == 0  # no empties kept
    n_tiles, n_boxes, n_hard = mt.process_frame(img, "train", 640, 0.0, 0.5, hard=[(700.0, 100.0)], dst=dst)
    assert (n_tiles, n_boxes, n_hard) == (1, 0, 1)
    assert (tmp_path / "dst/images/train/f_0000001_x640_y0.png").exists()
