"""Pipeline tests with a fake ffmpeg on PATH — no real encoding needed."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

import screenrec_converter.converter.pipeline as pipeline
from screenrec_converter.config import OriginalPolicy
from screenrec_converter.converter import ConversionWorker, convert_file
from screenrec_converter.encoder.detect import SOFTWARE

FAKE_FFMPEG_OK = """#!/bin/bash
# fake ffmpeg: writes a dummy output file (last argument)
out="${@: -1}"
echo "fake encode" > "$out"
"""

FAKE_FFMPEG_FAIL = """#!/bin/bash
echo "Invalid data found when processing input" >&2
exit 1
"""


@pytest.fixture
def fake_ffmpeg(tmp_path, monkeypatch):
    """Install a fake ffmpeg at the front of PATH; yields a setter to
    switch between success and failure behavior."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "ffmpeg"

    def install(body: str) -> None:
        script.write_text(body)
        script.chmod(script.stat().st_mode | stat.S_IEXEC)

    install(FAKE_FFMPEG_OK)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    # Bypass encoder probing (which would invoke the fake ffmpeg oddly).
    monkeypatch.setattr(pipeline, "detect_best_encoder", lambda *a, **k: SOFTWARE)
    return install


def _make_recording(tmp_path) -> Path:
    src = tmp_path / "rec.webm"
    src.write_bytes(b"webm-data" * 100)
    return src


def test_successful_conversion(tmp_path, cfg, fake_ffmpeg):
    src = _make_recording(tmp_path)
    result = convert_file(src, cfg)
    assert result.dest == tmp_path / "rec.mp4"
    assert result.dest.exists()
    assert src.exists()  # policy: keep
    assert result.original_bytes == 900
    assert result.converted_bytes > 0


def test_failed_conversion_preserves_original_and_removes_partial(tmp_path, cfg, fake_ffmpeg):
    fake_ffmpeg(FAKE_FFMPEG_FAIL)
    src = _make_recording(tmp_path)
    with pytest.raises(RuntimeError, match="Invalid data"):
        convert_file(src, cfg)
    assert src.exists()
    assert not (tmp_path / "rec.mp4").exists()


def test_delete_original_policy(tmp_path, cfg, fake_ffmpeg):
    cfg.original_policy = OriginalPolicy.DELETE
    src = _make_recording(tmp_path)
    convert_file(src, cfg)
    assert not src.exists()


def test_archive_original_policy(tmp_path, cfg, fake_ffmpeg):
    cfg.original_policy = OriginalPolicy.ARCHIVE
    src = _make_recording(tmp_path)
    convert_file(src, cfg)
    assert not src.exists()
    assert (cfg.archive_path / "rec.webm").exists()


def test_missing_ffmpeg_is_reported(tmp_path, cfg, monkeypatch):
    monkeypatch.setattr(pipeline, "ffmpeg_available", lambda: False)
    src = _make_recording(tmp_path)
    with pytest.raises(RuntimeError, match="ffmpeg is not installed"):
        convert_file(src, cfg)
    assert src.exists()


def test_worker_survives_failures_and_runs_hooks(tmp_path, cfg, fake_ffmpeg):
    fake_ffmpeg(FAKE_FFMPEG_FAIL)
    events = []

    class Spy:
        def on_conversion_success(self, result):
            events.append(("ok", result.dest))

        def on_conversion_failure(self, source, error):
            events.append(("fail", source))

    worker = ConversionWorker(cfg, plugins=[Spy()])
    worker.start()

    bad = _make_recording(tmp_path)
    worker.submit(bad)
    # Give the failure time to process, then switch ffmpeg to success.
    import time

    time.sleep(1.5)
    fake_ffmpeg(FAKE_FFMPEG_OK)
    good = tmp_path / "rec2.webm"
    good.write_bytes(b"webm-data")
    worker.submit(good)

    worker.stop()
    worker.join(timeout=15)
    assert not worker.is_alive()

    assert ("fail", bad) in events
    assert any(kind == "ok" for kind, _ in events)
    assert (tmp_path / "rec2.mp4").exists()


def test_worker_dedupes_pending_submissions(cfg, tmp_path):
    worker = ConversionWorker(cfg)
    path = tmp_path / "rec.webm"
    worker.submit(path)
    worker.submit(path)  # duplicate while still queued
    assert worker._queue.qsize() == 1
