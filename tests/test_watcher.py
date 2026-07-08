from __future__ import annotations

import time
from pathlib import Path

from screenrec_converter.watcher import RecordingWatcher


def _wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def test_detects_new_webm(tmp_path):
    seen: list[Path] = []
    watcher = RecordingWatcher(tmp_path / "watch", seen.append)
    watcher.start()
    try:
        rec = tmp_path / "watch" / "Screencast from 2026-07-08.webm"
        rec.write_bytes(b"data")
        assert _wait_for(lambda: rec in seen)
    finally:
        watcher.stop()


def test_ignores_other_extensions_and_hidden(tmp_path):
    seen: list[Path] = []
    watcher = RecordingWatcher(tmp_path / "watch", seen.append)
    watcher.start()
    try:
        (tmp_path / "watch" / "notes.txt").write_text("x")
        (tmp_path / "watch" / ".hidden.webm").write_bytes(b"x")
        marker = tmp_path / "watch" / "real.webm"
        marker.write_bytes(b"x")
        assert _wait_for(lambda: marker in seen)
        assert seen == [marker]
    finally:
        watcher.stop()


def test_detects_rename_to_webm(tmp_path):
    seen: list[Path] = []
    watch = tmp_path / "watch"
    watcher = RecordingWatcher(watch, seen.append)
    watcher.start()
    try:
        tmp = watch / "recording.part"
        tmp.write_bytes(b"x")
        final = watch / "recording.webm"
        tmp.rename(final)
        assert _wait_for(lambda: final in seen)
    finally:
        watcher.stop()


def test_pause_and_resume(tmp_path):
    seen: list[Path] = []
    watch = tmp_path / "watch"
    watcher = RecordingWatcher(watch, seen.append)
    watcher.start()
    try:
        watcher.pause()
        ignored = watch / "while_paused.webm"
        ignored.write_bytes(b"x")
        time.sleep(0.5)
        assert ignored not in seen

        watcher.resume()
        active = watch / "after_resume.webm"
        active.write_bytes(b"x")
        assert _wait_for(lambda: active in seen)
        assert ignored not in seen
    finally:
        watcher.stop()
