"""System tray icon (PySide6, optional dependency)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from .. import APP_TITLE
from ..config import AppConfig
from ..converter import ConversionWorker
from ..logger import log_file_path
from ..watcher import RecordingWatcher

log = logging.getLogger(__name__)


def _xdg_open(target: Path) -> None:
    subprocess.Popen(["xdg-open", str(target)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_tray(cfg: AppConfig, worker: ConversionWorker, watcher: RecordingWatcher) -> int:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_TITLE)

    worker.start()
    watcher.start()

    icon = QIcon.fromTheme("media-record", QIcon.fromTheme("video-x-generic"))
    tray = QSystemTrayIcon(icon)
    tray.setToolTip(APP_TITLE)
    menu = QMenu()

    act_enabled = QAction("Automatic conversion", menu, checkable=True, checked=True)

    def toggle_enabled(checked: bool) -> None:
        watcher.resume() if checked else watcher.pause()

    act_enabled.toggled.connect(toggle_enabled)
    menu.addAction(act_enabled)

    def convert_manually() -> None:
        files, _filter = QFileDialog.getOpenFileNames(
            None, "Convert recordings", str(cfg.watch_path), "WebM videos (*.webm)"
        )
        for f in files:
            worker.submit(Path(f))

    act_convert = QAction("Convert files…", menu)
    act_convert.triggered.connect(convert_manually)
    menu.addAction(act_convert)

    act_open = QAction("Open output folder", menu)
    act_open.triggered.connect(lambda: _xdg_open(cfg.output_dir_for(cfg.watch_path / "x.webm")))
    menu.addAction(act_open)

    menu.addSeparator()

    def open_settings() -> None:
        try:
            from ..gui.settings_window import SettingsWindow
        except ImportError:
            log.error("Settings window unavailable")
            return
        win = SettingsWindow(cfg)
        win.show()
        # Keep a reference so the window isn't garbage-collected.
        tray._settings_window = win  # type: ignore[attr-defined]

    act_settings = QAction("Settings…", menu)
    act_settings.triggered.connect(open_settings)
    menu.addAction(act_settings)

    act_logs = QAction("View logs", menu)
    act_logs.triggered.connect(lambda: _xdg_open(log_file_path()))
    menu.addAction(act_logs)

    menu.addSeparator()
    act_quit = QAction("Quit", menu)
    act_quit.triggered.connect(app.quit)
    menu.addAction(act_quit)

    tray.setContextMenu(menu)
    tray.show()

    code = app.exec()
    watcher.stop()
    worker.stop()
    worker.join(timeout=10)
    return code
