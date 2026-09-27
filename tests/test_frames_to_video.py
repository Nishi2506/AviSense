from src.frames_to_video import find_sequence, output_name


def test_find_sequence_sorts_numerically_and_filters(tmp_path):
    for name in ["D02_20210628090856_0000010.png", "D02_20210628090856_0000002.png",
                 "D02_20210628090856_0000001.png", "D01_20210213091323_0000001.png", "notes.txt"]:
        (tmp_path / name).write_bytes(b"")
    seq = find_sequence(tmp_path, "D02_20210628090856")
    assert [n for n, _ in seq] == [1, 2, 10]


def test_prefix_does_not_match_longer_prefix(tmp_path):
    (tmp_path / "20201111_sljc_1_0000005.png").write_bytes(b"")
    (tmp_path / "20201111_sljc_1_rest_0000005.png").write_bytes(b"")
    assert len(find_sequence(tmp_path, "20201111_sljc_1")) == 1


def test_output_name_shifts_timestamp_to_first_frame():
    # frame 250 at 25 fps = 10 s after 09:08:56
    assert output_name("D02_20210628090856", 250, 999, 25) == "D02_20210628090906_f250-999.mp4"
    assert output_name("20201111_sljc_1", 0, 99, 25) == "20201111_sljc_1_f0-99.mp4"
