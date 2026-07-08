from __future__ import annotations

from datetime import datetime

from screenrec_converter.config import AppConfig
from screenrec_converter.converter import build_output_path

NOW = datetime(2026, 7, 8, 20, 15, 0)


def test_default_pattern_keeps_stem(tmp_path, cfg):
    src = tmp_path / "Screencast from 2026-07-08.webm"
    out = build_output_path(src, cfg, NOW)
    assert out == tmp_path / "Screencast from 2026-07-08.mp4"


def test_timestamp_pattern(tmp_path, cfg):
    cfg.output.filename_pattern = "Recording_{timestamp}"
    src = tmp_path / "whatever.webm"
    out = build_output_path(src, cfg, NOW)
    assert out.name == "Recording_20260708_201500.mp4"


def test_date_time_tokens(tmp_path, cfg):
    cfg.output.filename_pattern = "{stem}_{date}_{time}"
    out = build_output_path(tmp_path / "rec.webm", cfg, NOW)
    assert out.name == "rec_2026-07-08_201500.mp4"


def test_collision_appends_suffix(tmp_path, cfg):
    (tmp_path / "rec.mp4").touch()
    out = build_output_path(tmp_path / "rec.webm", cfg, NOW)
    assert out.name == "rec_1.mp4"


def test_separate_output_directory(tmp_path, cfg):
    cfg.output.directory = str(tmp_path / "mp4")
    out = build_output_path(tmp_path / "rec.webm", cfg, NOW)
    assert out.parent == tmp_path / "mp4"
