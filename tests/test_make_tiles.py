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
