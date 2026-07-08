"""Plugin API.

A plugin is a class named in ``enabled_plugins`` in the config, found either
in this package or in ``~/.config/screenrec-converter/plugins/``. Subclass
``Plugin`` and override the hooks you care about. Hooks run on the conversion
worker thread after the conversion finishes; exceptions are caught and logged
so a broken plugin cannot take down the service.

Future plugins (uploaders, transcription, GIF/thumbnail generation, ...) get
the finished MP4 path from ``result.dest``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import AppConfig
    from ..converter import ConversionResult


class Plugin:
    """Base class for post-conversion automation plugins."""

    def __init__(self, cfg: "AppConfig") -> None:
        self.cfg = cfg

    def on_conversion_success(self, result: "ConversionResult") -> None:
        """Called after a successful conversion (worker thread)."""

    def on_conversion_failure(self, source: Path, error: Exception) -> None:
        """Called after a failed conversion (worker thread)."""
