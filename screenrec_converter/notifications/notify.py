"""Desktop notifications via ``notify-send``.

Using the CLI keeps us free of D-Bus library dependencies; if notify-send is
missing or fails we log and move on — notifications are never load-bearing.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from ..config import AppConfig

log = logging.getLogger(__name__)


def notify(cfg: AppConfig, title: str, body: str = "", icon: str = "video-x-generic") -> None:
    if not cfg.notifications_enabled:
        return
    tool = shutil.which("notify-send")
    if tool is None:
        log.debug("notify-send not found; skipping notification: %s", title)
        return
    try:
        subprocess.run(
            [tool, "--app-name=Screen Recording Converter", f"--icon={icon}", title, body],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("Notification failed: %s", exc)
