"""Output path construction from the configured filename pattern."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import AppConfig
from ..utils import unique_path


def build_output_path(source: Path, cfg: AppConfig, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    name = cfg.output.filename_pattern.format(
        stem=source.stem,
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H%M%S"),
        timestamp=now.strftime("%Y%m%d_%H%M%S"),
    )
    out_dir = cfg.output_dir_for(source)
    return unique_path(out_dir / f"{name}.mp4")
