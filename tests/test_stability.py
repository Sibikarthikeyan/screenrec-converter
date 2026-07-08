from __future__ import annotations

import threading
import time

import pytest

from screenrec_converter.converter.pipeline import StabilityTimeout, wait_until_stable


def test_stable_file_returns_quickly(tmp_path, cfg):
    path = tmp_path / "rec.webm"
    path.write_bytes(b"x" * 1000)
    start = time.monotonic()
    wait_until_stable(path, cfg)
    assert time.monotonic() - start < cfg.stability_timeout_seconds


def test_waits_for_growing_file(tmp_path, cfg):
    path = tmp_path / "rec.webm"
    path.write_bytes(b"")
    done_growing = threading.Event()

    def writer():
        with open(path, "ab") as f:
            for _ in range(4):
                f.write(b"x" * 100)
                f.flush()
                time.sleep(0.15)
        done_growing.set()

    t = threading.Thread(target=writer)
    t.start()
    wait_until_stable(path, cfg)
    # We must not have returned while the writer was still appending.
    assert done_growing.is_set()
    t.join()
    assert path.stat().st_size == 400


def test_timeout_on_never_stable(tmp_path, cfg):
    cfg.stability_timeout_seconds = 1.0
    path = tmp_path / "rec.webm"
    path.write_bytes(b"")
    stop = threading.Event()

    def writer():
        with open(path, "ab") as f:
            while not stop.is_set():
                f.write(b"x")
                f.flush()
                time.sleep(0.05)

    t = threading.Thread(target=writer)
    t.start()
    try:
        with pytest.raises(StabilityTimeout):
            wait_until_stable(path, cfg)
    finally:
        stop.set()
        t.join()


def test_disappearing_file_raises(tmp_path, cfg):
    path = tmp_path / "rec.webm"
    path.write_bytes(b"x")

    def deleter():
        time.sleep(0.1)
        path.unlink()

    t = threading.Thread(target=deleter)
    t.start()
    # Depending on timing this either raises FileNotFoundError from stat()
    # or completes if stability was reached before deletion; force the race
    # to resolve deterministically by using a long stability window.
    cfg.stability_seconds = 1.0
    with pytest.raises(FileNotFoundError):
        wait_until_stable(path, cfg)
    t.join()
