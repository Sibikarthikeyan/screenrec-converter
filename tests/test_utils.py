from __future__ import annotations

from screenrec_converter.utils import human_size, is_file_open, unique_path


def test_human_size():
    assert human_size(500) == "500 B"
    assert human_size(2048) == "2.0 KiB"
    assert human_size(57925143) == "55.2 MiB"


def test_unique_path(tmp_path):
    p = tmp_path / "a.mp4"
    assert unique_path(p) == p
    p.touch()
    assert unique_path(p) == tmp_path / "a_1.mp4"
    (tmp_path / "a_1.mp4").touch()
    assert unique_path(p) == tmp_path / "a_2.mp4"


def test_is_file_open_detects_our_own_handle(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"x")
    assert not is_file_open(path)
    with open(path, "rb"):
        assert is_file_open(path)
    assert not is_file_open(path)
