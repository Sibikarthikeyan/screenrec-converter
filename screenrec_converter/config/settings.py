"""Application configuration: typed dataclasses persisted as YAML.

The config file lives at ``~/.config/screenrec-converter/config.yaml``
(respecting ``$XDG_CONFIG_HOME``). Unknown keys in the file are ignored so
older configs keep working after upgrades; missing keys fall back to defaults.
"""

from __future__ import annotations

import dataclasses
import enum
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .. import APP_NAME

log = logging.getLogger(__name__)


class QualityPreset(str, enum.Enum):
    """Encoding quality presets, from largest file to smallest."""

    LOSSLESS = "lossless"
    HIGH = "high"
    BALANCED = "balanced"
    SMALL = "small"
    VERY_SMALL = "very_small"


class OriginalPolicy(str, enum.Enum):
    """What to do with the source .webm after a successful conversion."""

    KEEP = "keep"
    DELETE = "delete"
    ARCHIVE = "archive"
    TRASH = "trash"


@dataclass
class OutputConfig:
    """Where converted files go and how they are named."""

    # Empty string means "save beside the original".
    directory: str = ""
    # Tokens: {stem} original name without extension, {date} YYYY-MM-DD,
    # {time} HHMMSS, {timestamp} YYYYMMDD_HHMMSS.
    filename_pattern: str = "{stem}"


@dataclass
class AppConfig:
    """Top-level application configuration."""

    watch_directory: str = "~/Videos/Screencasts"
    output: OutputConfig = field(default_factory=OutputConfig)

    quality_preset: QualityPreset = QualityPreset.HIGH
    # Optional overrides; None means "use the preset's value".
    crf: int | None = None
    video_bitrate: str | None = None  # e.g. "6M"

    # Output frame rate. GNOME records variable-frame-rate (frames only when
    # the screen changes), which many players and platforms mishandle; we
    # resample to this constant rate. None keeps the source timing as-is.
    target_fps: int | None = 30

    hardware_acceleration: bool = True
    # Force a specific encoder name (e.g. "h264_nvenc"); None = auto-detect.
    forced_encoder: str | None = None

    original_policy: OriginalPolicy = OriginalPolicy.KEEP
    archive_directory: str = "~/Videos/Screencasts/originals"

    notifications_enabled: bool = True

    # How long the file size must stay unchanged before we treat the
    # recording as finished, and how long to keep retrying overall.
    stability_seconds: float = 2.0
    stability_timeout_seconds: float = 600.0

    enabled_plugins: list[str] = field(default_factory=list)

    log_level: str = "INFO"

    @property
    def watch_path(self) -> Path:
        return Path(self.watch_directory).expanduser()

    @property
    def archive_path(self) -> Path:
        return Path(self.archive_directory).expanduser()

    def output_dir_for(self, source: Path) -> Path:
        if self.output.directory:
            return Path(self.output.directory).expanduser()
        return source.parent


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return base / APP_NAME / "config.yaml"


def _from_dict(cls: type, data: dict[str, Any]) -> Any:
    """Build a dataclass from a dict, ignoring unknown keys and coercing enums."""
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        if f.name == "output" and isinstance(value, dict):
            value = _from_dict(OutputConfig, value)
        elif f.name == "quality_preset":
            value = QualityPreset(value)
        elif f.name == "original_policy":
            value = OriginalPolicy(value)
        kwargs[f.name] = value
    return cls(**kwargs)


def _to_dict(cfg: AppConfig) -> dict[str, Any]:
    def encode(obj: Any) -> Any:
        if isinstance(obj, enum.Enum):
            return obj.value
        if dataclasses.is_dataclass(obj):
            return {f.name: encode(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        if isinstance(obj, list):
            return [encode(v) for v in obj]
        return obj

    return encode(cfg)


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from disk; return defaults if the file is missing or invalid."""
    path = path or config_path()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"config root must be a mapping, got {type(raw).__name__}")
        return _from_dict(AppConfig, raw)
    except FileNotFoundError:
        return AppConfig()
    except (yaml.YAMLError, ValueError, TypeError) as exc:
        log.warning("Invalid config at %s (%s); using defaults", path, exc)
        return AppConfig()


def save_config(cfg: AppConfig, path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(_to_dict(cfg), sort_keys=False))
    return path
