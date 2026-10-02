import zipfile

from src.detection.prepare_airbirds import extract_flat, move_sequence, zip_name


def test_zip_names_match_the_hugging_face_mirror():
    assert zip_name("images", "5") == "images5.zip"
    assert zip_name("labels", "test_D02_20210721142744") == "labels_test_D02_20210721142744.zip"


def test_extract_flat_drops_folders(tmp_path):
    z = tmp_path / "images5.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("images5/", "")
        f.writestr("images5/D02_x_0000001.png", b"png")
        f.writestr("images5/D02_x_0000002.png", b"png2")
    assert extract_flat(z, tmp_path / "out") == 2
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["D02_x_0000001.png", "D02_x_0000002.png"]


def test_move_sequence_moves_images_and_labels(tmp_path):
    for kind, ext in (("images", "png"), ("labels", "txt")):
        (tmp_path / kind / "train").mkdir(parents=True)
        for name in ("D02_keep_0000001", "D02_held_0000001", "D02_held_0000002"):
            (tmp_path / kind / "train" / f"{name}.{ext}").write_text("")
    assert move_sequence(tmp_path, "D02_held", "train", "val") == 2
    assert sorted(p.name for p in (tmp_path / "images" / "train").iterdir()) == ["D02_keep_0000001.png"]
    assert len(list((tmp_path / "labels" / "val").iterdir())) == 2


def test_byte_ranges_cover_the_file_exactly():
    from src.detection.prepare_airbirds import byte_ranges
    r = byte_ranges(100, 3)
    assert r == [(0, 33), (34, 67), (68, 99)]
    assert byte_ranges(10, 1) == [(0, 9)]
