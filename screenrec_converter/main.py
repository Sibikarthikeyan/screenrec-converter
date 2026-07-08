"""Entry point.

Subcommands:
    run       headless background service (default; used by systemd)
    tray      service + system tray icon (requires PySide6)
    convert   convert one or more files right now and exit
    settings  open the settings window (requires PySide6)
    encoders  show detected encoders and exit
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path

from . import APP_NAME, __version__
from .config import load_config
from .converter import ConversionWorker, convert_file
from .logger import setup_logging
from .plugins import load_plugins
from .utils import human_size
from .watcher import RecordingWatcher

log = logging.getLogger(__name__)


def _build_service(cfg):
    """Wire up worker + watcher (shared by `run` and `tray`)."""
    worker = ConversionWorker(cfg, plugins=load_plugins(cfg))
    watcher = RecordingWatcher(cfg.watch_path, worker.submit)
    return worker, watcher


def cmd_run(cfg) -> int:
    worker, watcher = _build_service(cfg)
    worker.start()
    watcher.start()

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log.info("%s %s running (Ctrl-C to stop)", APP_NAME, __version__)
    stop.wait()

    watcher.stop()
    worker.stop()
    worker.join(timeout=10)
    log.info("Stopped")
    return 0


def cmd_convert(cfg, files: list[str]) -> int:
    failures = 0
    for name in files:
        path = Path(name).expanduser()
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            failures += 1
            continue
        try:
            result = convert_file(path, cfg)
        except Exception as exc:
            print(f"FAILED  {path.name}: {exc}", file=sys.stderr)
            failures += 1
        else:
            print(
                f"OK      {result.dest}  "
                f"({human_size(result.original_bytes)} -> {human_size(result.converted_bytes)}, "
                f"{result.encoder.label}, {result.duration_seconds:.1f}s)"
            )
    return 1 if failures else 0


def cmd_encoders(cfg) -> int:
    from .encoder import detect_best_encoder, ffmpeg_available, list_working_encoders

    if not ffmpeg_available():
        print("ffmpeg is not installed. Install it with: sudo apt install ffmpeg")
        return 1
    working = list_working_encoders()
    best = detect_best_encoder(cfg.hardware_acceleration, cfg.forced_encoder)
    for enc in working:
        marker = " (selected)" if enc.name == best.name else ""
        kind = "hardware" if enc.hardware else "software"
        print(f"{enc.name:14} {enc.label:22} [{kind}]{marker}")
    return 0


def cmd_tray(cfg) -> int:
    try:
        from .tray.tray_app import run_tray
    except ImportError:
        print(
            "PySide6 is required for the tray icon.\n"
            "Install it with: pip install 'screenrec-converter[gui]'  (or pip install PySide6)",
            file=sys.stderr,
        )
        return 1
    worker, watcher = _build_service(cfg)
    return run_tray(cfg, worker, watcher)


def cmd_settings(cfg) -> int:
    try:
        from .gui.settings_window import run_settings
    except ImportError:
        print("PySide6 is required for the settings window (pip install PySide6).",
              file=sys.stderr)
        return 1
    return run_settings(cfg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME,
                                     description="Auto-convert GNOME screen recordings to MP4")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="run the background service (default)")
    sub.add_parser("tray", help="run with a system tray icon")
    p_convert = sub.add_parser("convert", help="convert files now and exit")
    p_convert.add_argument("files", nargs="+", help=".webm files to convert")
    sub.add_parser("settings", help="open the settings window")
    sub.add_parser("encoders", help="list detected encoders")

    args = parser.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg.log_level)

    command = args.command or "run"
    if command == "run":
        return cmd_run(cfg)
    if command == "convert":
        return cmd_convert(cfg, args.files)
    if command == "encoders":
        return cmd_encoders(cfg)
    if command == "tray":
        return cmd_tray(cfg)
    if command == "settings":
        return cmd_settings(cfg)
    parser.error(f"unknown command {command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
