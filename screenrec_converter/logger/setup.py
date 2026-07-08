"""Structured logging with rotation.

Logs go to ``~/.local/state/screenrec-converter/converter.log`` (respecting
``$XDG_STATE_HOME``) and to the console.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

from .. import APP_NAME

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def log_file_path() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    return base / APP_NAME / "converter.log"


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers when called twice (e.g. config reload).
    if any(getattr(h, "_screenrec", False) for h in root.handlers):
        return

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT))
    console._screenrec = True  # type: ignore[attr-defined]
    root.addHandler(console)

    path = log_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(_FORMAT))
        file_handler._screenrec = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("Cannot open log file %s: %s (console only)", path, exc)
