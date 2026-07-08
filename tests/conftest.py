from __future__ import annotations

import pytest

from screenrec_converter.config import AppConfig


@pytest.fixture
def cfg(tmp_path) -> AppConfig:
    """A config sandboxed to a temp directory with fast stability timings."""
    c = AppConfig()
    c.watch_directory = str(tmp_path / "watch")
    c.archive_directory = str(tmp_path / "archive")
    c.stability_seconds = 0.2
    c.stability_timeout_seconds = 5.0
    c.notifications_enabled = False
    return c
