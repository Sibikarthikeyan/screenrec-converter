from __future__ import annotations

from screenrec_converter.config import (
    AppConfig,
    OriginalPolicy,
    QualityPreset,
    load_config,
    save_config,
)


def test_defaults():
    cfg = AppConfig()
    assert cfg.quality_preset is QualityPreset.HIGH
    assert cfg.original_policy is OriginalPolicy.KEEP
    assert cfg.watch_path.name == "Screencasts"
    assert cfg.output.filename_pattern == "{stem}"


def test_roundtrip(tmp_path):
    cfg = AppConfig()
    cfg.quality_preset = QualityPreset.SMALL
    cfg.original_policy = OriginalPolicy.ARCHIVE
    cfg.output.directory = "/tmp/out"
    cfg.enabled_plugins = ["MyPlugin"]
    path = tmp_path / "config.yaml"
    save_config(cfg, path)

    loaded = load_config(path)
    assert loaded.quality_preset is QualityPreset.SMALL
    assert loaded.original_policy is OriginalPolicy.ARCHIVE
    assert loaded.output.directory == "/tmp/out"
    assert loaded.enabled_plugins == ["MyPlugin"]


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "nope.yaml") == AppConfig()


def test_invalid_yaml_gives_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("quality_preset: [not: valid")
    assert load_config(path) == AppConfig()


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("log_level: DEBUG\nfuture_option: 42\n")
    cfg = load_config(path)
    assert cfg.log_level == "DEBUG"


def test_output_dir_beside_original(tmp_path):
    cfg = AppConfig()
    src = tmp_path / "rec.webm"
    assert cfg.output_dir_for(src) == tmp_path
    cfg.output.directory = str(tmp_path / "mp4")
    assert cfg.output_dir_for(src) == tmp_path / "mp4"
