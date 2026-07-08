# Screen Recording Converter

[![CI](https://github.com/Sibikarthikeyan/screenrec-converter/actions/workflows/ci.yml/badge.svg)](https://github.com/Sibikarthikeyan/screenrec-converter/actions/workflows/ci.yml)

Automatically converts Ubuntu GNOME screen recordings from `.webm` to `.mp4`
the moment recording finishes — no more opening a terminal and running ffmpeg
by hand.

GNOME's built-in screen recorder (Ctrl+Alt+Shift+R) saves WebM, but WhatsApp,
PowerPoint, Google Slides, LinkedIn, Premiere, Teams and many other targets
want MP4. This tool watches your Screencasts folder, waits until the recorder
has fully finished writing, converts to a maximally compatible H.264/AAC MP4
(`yuv420p`, `+faststart`), notifies you, and optionally archives or removes
the original.

## Features

- **Event-driven watching** — inotify via `watchdog`, no polling, near-zero idle CPU.
- **Safe completion detection** — waits until the file size is stable *and* no
  process holds the file open before converting.
- **Hardware acceleration** — auto-detects NVIDIA NVENC, Intel Quick Sync,
  AMD AMF, and VA-API with a real test-encode probe; falls back to libx264.
- **Quality presets** — lossless / high / balanced / small / very small, plus
  manual CRF or bitrate override.
- **Configurable output** — save beside the original or elsewhere; filename
  patterns with `{stem}`, `{date}`, `{time}`, `{timestamp}` tokens.
- **Original file policies** — keep, delete, archive to a folder, or move to Trash.
  The original is *never* touched if conversion fails.
- **Desktop notifications**, structured rotating logs, system tray icon,
  PySide6 settings window.
- **Plugin architecture** — drop a `.py` into `~/.config/screenrec-converter/plugins/`
  to run automation after each conversion (upload, GIF, transcription, ...).
- **Crash-proof worker** — corrupted files, missing ffmpeg, disk-full and
  permission errors are logged and notified; monitoring always continues.

## Requirements

- Ubuntu 22.04+ (any Linux with inotify works), Python 3.11+
- `ffmpeg` — `sudo apt install ffmpeg`
- `libnotify-bin` for notifications (preinstalled on Ubuntu)

## Installation

```bash
sudo apt install ffmpeg
pipx install .            # or: pip install --user .
# with tray icon + settings GUI:
pipx install '.[gui]'     # or: pip install --user '.[gui]'
```

### Start automatically on login (systemd user service)

```bash
mkdir -p ~/.config/systemd/user
cp packaging/screenrec-converter.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now screenrec-converter
journalctl --user -u screenrec-converter -f   # follow logs
```

### Desktop launcher (tray mode)

```bash
cp packaging/screenrec-converter.desktop ~/.local/share/applications/
```

## Usage

```bash
screenrec-converter run                # headless service (what systemd runs)
screenrec-converter tray               # service + tray icon (needs PySide6)
screenrec-converter convert FILE...    # convert files right now
screenrec-converter settings           # settings window (needs PySide6)
screenrec-converter encoders           # show detected encoders
```

## Configuration

`~/.config/screenrec-converter/config.yaml` (created on first save from the
settings window; all keys optional):

```yaml
watch_directory: ~/Videos/Screencasts
output:
  directory: ""                # "" = beside the original
  filename_pattern: "{stem}"   # e.g. "{stem}_{timestamp}"
quality_preset: high           # lossless | high | balanced | small | very_small
crf: null                      # override preset quality (0-51)
video_bitrate: null            # e.g. "6M" — overrides CRF entirely
target_fps: 30                 # resample GNOME's VFR to constant fps; null = keep source timing
hardware_acceleration: true
forced_encoder: null           # e.g. h264_nvenc
original_policy: keep          # keep | delete | archive | trash
archive_directory: ~/Videos/Screencasts/originals
notifications_enabled: true
stability_seconds: 2.0
stability_timeout_seconds: 600.0
enabled_plugins: []
log_level: INFO
```

Logs: `~/.local/state/screenrec-converter/converter.log` (rotated, 5×2 MiB).

## Writing a plugin

```python
# ~/.config/screenrec-converter/plugins/copy_to_share.py
import shutil
from pathlib import Path
from screenrec_converter.plugins import Plugin

class CopyToShare(Plugin):
    def on_conversion_success(self, result):
        shutil.copy2(result.dest, Path("~/Share").expanduser())
```

Enable it in the config: `enabled_plugins: [CopyToShare]`.
Hooks: `on_conversion_success(result)` and `on_conversion_failure(source, error)`.
`result.dest` is the finished MP4; `result.source`, `.encoder`, `.duration_seconds`,
`.original_bytes`, `.converted_bytes`, `.ratio` are also available.

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Architecture

```
screenrec_converter/
├── watcher/        inotify folder monitoring (watchdog)
├── converter/      stability wait, ffmpeg pipeline, presets, naming
├── encoder/        hardware encoder detection with probe encodes
├── notifications/  notify-send wrapper
├── config/         typed dataclass config <-> YAML
├── gui/            PySide6 settings window (optional)
├── tray/           PySide6 tray icon (optional)
├── logger/         rotating structured logging
├── plugins/        post-conversion plugin API + loader
├── utils/          shared filesystem helpers
└── main.py         CLI entry point
```

Flow: watcher event → worker queue → wait-until-stable → encoder pick →
ffmpeg → original-file policy → notification → plugin hooks.

## Packaging notes

- **Debian package**: `pyproject.toml` is setuptools-based; use
  `pybuild`/`dh-python` with `debian/` scaffolding, or quickly:
  `pip install build && python -m build`, then `dpkg-deb` around a
  `--prefix=/usr` install tree.
- **AppImage**: bundle with `python-appimage` or `linuxdeploy` +
  `linuxdeploy-plugin-python`; entry point is `screenrec_converter.main:main`.
  Note ffmpeg should remain a system dependency (bundling it inflates the
  image by ~80 MB).

## License

MIT
