"""Filesystem helpers shared across modules."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num_bytes) < 1024 or unit == "TiB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TiB"


def unique_path(path: Path) -> Path:
    """Return ``path`` if free, else ``name_1.ext``, ``name_2.ext``, ..."""
    if not path.exists():
        return path
    for i in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"No free filename variant for {path}")


def is_file_open(path: Path) -> bool:
    """Return True if any process on this machine holds ``path`` open.

    Scans ``/proc/*/fd``; processes we cannot inspect (other users) are
    skipped, so this is a best-effort check used alongside the size-stability
    wait, not a guarantee.
    """
    try:
        target = path.resolve()
    except OSError:
        return False
    proc = Path("/proc")
    for pid_dir in proc.iterdir():
        if not pid_dir.name.isdigit():
            continue
        fd_dir = pid_dir / "fd"
        try:
            for fd in fd_dir.iterdir():
                try:
                    if Path(os.readlink(fd)) == target:
                        return True
                except OSError:
                    continue
        except (PermissionError, FileNotFoundError):
            continue
    return False


def move_to_trash(path: Path) -> None:
    """Move a file to the desktop Trash, falling back to a manual move."""
    gio = shutil.which("gio")
    if gio:
        result = subprocess.run(
            [gio, "trash", str(path)], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return
        log.warning("gio trash failed for %s: %s", path, result.stderr.strip())
    # Fallback: XDG trash layout without the .trashinfo niceties.
    trash_files = Path("~/.local/share/Trash/files").expanduser()
    trash_files.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(unique_path(trash_files / path.name)))
