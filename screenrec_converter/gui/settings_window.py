"""Settings window (PySide6, optional dependency).

Edits the YAML config in place. The headless service reads config at startup,
so changes take effect on the next service restart (the tray applies watch
pause/resume live).
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_TITLE
from ..config import AppConfig, OriginalPolicy, QualityPreset, save_config

log = logging.getLogger(__name__)


class _DirPicker(QWidget):
    def __init__(self, initial: str, placeholder: str = "") -> None:
        super().__init__()
        self.edit = QLineEdit(initial)
        self.edit.setPlaceholderText(placeholder)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)
        layout.addWidget(browse)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose folder", self.edit.text())
        if chosen:
            self.edit.setText(chosen)

    def value(self) -> str:
        return self.edit.text().strip()


class SettingsWindow(QDialog):
    def __init__(self, cfg: AppConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle(f"{APP_TITLE} — Settings")
        self.setMinimumWidth(560)

        form = QFormLayout()

        self.watch_dir = _DirPicker(cfg.watch_directory)
        form.addRow("Watched folder", self.watch_dir)

        self.output_dir = _DirPicker(cfg.output.directory, "Same folder as the recording")
        form.addRow("Output folder", self.output_dir)

        self.pattern = QLineEdit(cfg.output.filename_pattern)
        self.pattern.setToolTip("Tokens: {stem} {date} {time} {timestamp}")
        form.addRow("Filename pattern", self.pattern)

        self.preset = QComboBox()
        for p in QualityPreset:
            self.preset.addItem(p.value.replace("_", " ").title(), p)
        self.preset.setCurrentIndex(list(QualityPreset).index(cfg.quality_preset))
        form.addRow("Quality preset", self.preset)

        self.hwaccel = QCheckBox("Use hardware acceleration when available")
        self.hwaccel.setChecked(cfg.hardware_acceleration)
        form.addRow("", self.hwaccel)

        self.original = QComboBox()
        for p in OriginalPolicy:
            self.original.addItem(p.value.title(), p)
        self.original.setCurrentIndex(list(OriginalPolicy).index(cfg.original_policy))
        form.addRow("Original .webm file", self.original)

        self.notifications = QCheckBox("Show desktop notifications")
        self.notifications.setChecked(cfg.notifications_enabled)
        form.addRow("", self.notifications)

        self.stability = QDoubleSpinBox()
        self.stability.setRange(0.5, 60.0)
        self.stability.setSingleStep(0.5)
        self.stability.setSuffix(" s")
        self.stability.setValue(cfg.stability_seconds)
        form.addRow("Recording-finished wait", self.stability)

        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level.setCurrentText(cfg.log_level.upper())
        form.addRow("Log level", self.log_level)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _save(self) -> None:
        cfg = self.cfg
        cfg.watch_directory = self.watch_dir.value() or cfg.watch_directory
        cfg.output.directory = self.output_dir.value()
        cfg.output.filename_pattern = self.pattern.text().strip() or "{stem}"
        cfg.quality_preset = self.preset.currentData()
        cfg.hardware_acceleration = self.hwaccel.isChecked()
        cfg.original_policy = self.original.currentData()
        cfg.notifications_enabled = self.notifications.isChecked()
        cfg.stability_seconds = self.stability.value()
        cfg.log_level = self.log_level.currentText()
        try:
            path = save_config(cfg)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        log.info("Settings saved to %s", path)
        self.accept()


def run_settings(cfg: AppConfig) -> int:
    app = QApplication.instance() or QApplication([])
    win = SettingsWindow(cfg)
    win.show()
    return app.exec()
