import cv2
import numpy as np

from src.detection.temporal import TemporalBuffer, compose, load_composed, sequence_neighbours, temporal_step


def _frame(value):
    return np.full((4, 6, 3), value, np.uint8)


def test_temporal_step_from_weights_name():
    assert temporal_step("models/airbirds_tiles_temporal2_yolo11n_640.pt") == 2
    assert temporal_step("models/airbirds_tiles_c0567_yolo11n_640.pt") == 0


def test_compose_puts_oldest_to_newest_in_bgr_channels():
    out = compose(_frame(10), _frame(20), _frame(30))
    assert out.shape == (4, 6, 3) and out[0, 0].tolist() == [10, 20, 30]


def test_buffer_uses_frames_t_minus_2k_and_t_minus_k():
    buf = TemporalBuffer(step=2)
    outs = [buf.push(_frame(v))[0, 0].tolist() for v in (0, 10, 20, 30, 40, 50)]
    assert outs[0] == [0, 0, 0]          # start of stream: no motion cue yet
    assert outs[4] == [0, 20, 40]        # frames 0, 2, 4
    assert outs[5] == [10, 30, 50]


def test_neighbours_on_disk(tmp_path):
    for n in (1, 3, 5):
        cv2.imwrite(str(tmp_path / f"D02_x_{n:07d}.png"), np.full((4, 6), n * 10, np.uint8))
    p = tmp_path / "D02_x_0000005.png"
    assert sequence_neighbours(p, 2) == (tmp_path / "D02_x_0000001.png", tmp_path / "D02_x_0000003.png")
    assert load_composed(p, 2)[0, 0].tolist() == [10, 30, 50]
    assert sequence_neighbours(p, 1) is None  # frame 4 is missing


def test_write_sequence_resets_buffer_at_gaps(tmp_path):
    from src.detection.temporal import write_sequence
    src = tmp_path / "img"; src.mkdir()
    for n in (0, 1, 2, 7):  # gap between 2 and 7
        cv2.imwrite(str(src / f"D02_x_{n:07d}.png"), np.full((4, 6, 3), n * 10, np.uint8))
    assert write_sequence(src, tmp_path / "lbl", tmp_path / "out", "test", 1) == 4
    read = lambda n: cv2.imread(str(tmp_path / "out/images/test" / f"D02_x_{n:07d}.png"))[0, 0].tolist()
    assert read(2) == [0, 10, 20]
    assert read(7) == [70, 70, 70]  # fresh start after the gap
    assert (tmp_path / "out/labels/test/D02_x_0000007.txt").read_text() == ""


def test_neighbours_for_names_without_prefix(tmp_path):
    for n in (1, 2, 3):
        cv2.imwrite(str(tmp_path / f"{n:07d}.png"), np.zeros((4, 6), np.uint8))
    assert sequence_neighbours(tmp_path / "0000003.png", 1) == (tmp_path / "0000001.png", tmp_path / "0000002.png")
