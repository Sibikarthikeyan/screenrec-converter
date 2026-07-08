"""The conversion pipeline: stability wait -> ffmpeg -> post-processing.

A single worker thread consumes a queue of paths so conversions never run
concurrently (screen recordings are large; parallel encodes would thrash).
Every failure mode is caught, logged, and reported via notification — the
worker itself must never die.
"""

from __future__ import annotations

import logging
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import AppConfig, OriginalPolicy
from ..encoder import Encoder, detect_best_encoder, ffmpeg_available
from ..notifications import notify
from ..utils import human_size, is_file_open, move_to_trash, unique_path
from .naming import build_output_path
from .presets import build_ffmpeg_command

log = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    source: Path
    dest: Path
    encoder: Encoder
    duration_seconds: float
    original_bytes: int
    converted_bytes: int

    @property
    def ratio(self) -> float:
        return self.converted_bytes / self.original_bytes if self.original_bytes else 0.0


class StabilityTimeout(Exception):
    """The file never stopped growing within the configured timeout."""


def wait_until_stable(path: Path, cfg: AppConfig) -> None:
    """Block until ``path``'s size is unchanged for ``stability_seconds``
    and no process holds it open. Raises on timeout or disappearance."""
    deadline = time.monotonic() + cfg.stability_timeout_seconds
    check_interval = min(cfg.stability_seconds, 1.0)
    last_size = -1
    stable_since: float | None = None

    while time.monotonic() < deadline:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            raise FileNotFoundError(f"{path} disappeared while waiting for it to finish")
        now = time.monotonic()
        if size != last_size:
            last_size = size
            stable_since = now
        elif stable_since is not None and now - stable_since >= cfg.stability_seconds:
            if not is_file_open(path):
                return
            # Still open by the recorder; reset and keep waiting.
            stable_since = now
        time.sleep(check_interval)
    raise StabilityTimeout(f"{path} was still being written after {cfg.stability_timeout_seconds}s")


def _handle_original(source: Path, cfg: AppConfig) -> None:
    policy = cfg.original_policy
    if policy is OriginalPolicy.KEEP:
        return
    if policy is OriginalPolicy.DELETE:
        source.unlink()
    elif policy is OriginalPolicy.TRASH:
        move_to_trash(source)
    elif policy is OriginalPolicy.ARCHIVE:
        cfg.archive_path.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(unique_path(cfg.archive_path / source.name)))
    log.info("Original %s: %s", policy.value, source.name)


def convert_file(source: Path, cfg: AppConfig) -> ConversionResult:
    """Convert one file synchronously. Raises on failure; the partial output
    file is removed so a retry starts clean and the original is never touched."""
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is not installed. Install it with: sudo apt install ffmpeg"
        )

    wait_until_stable(source, cfg)
    original_bytes = source.stat().st_size
    encoder = detect_best_encoder(cfg.hardware_acceleration, cfg.forced_encoder)
    dest = build_output_path(source, cfg)
    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_ffmpeg_command(source, dest, cfg, encoder)
    log.info("Converting %s -> %s [%s]", source.name, dest.name, encoder.label)
    log.debug("ffmpeg command: %s", " ".join(cmd))

    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"Failed to launch ffmpeg: {exc}") from exc

    if proc.returncode != 0:
        dest.unlink(missing_ok=True)
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"ffmpeg exited with code {proc.returncode}:\n{tail}")

    elapsed = time.monotonic() - started
    result = ConversionResult(
        source=source,
        dest=dest,
        encoder=encoder,
        duration_seconds=elapsed,
        original_bytes=original_bytes,
        converted_bytes=dest.stat().st_size,
    )
    log.info(
        "Converted %s in %.1fs: %s -> %s (%.0f%%) using %s",
        source.name,
        elapsed,
        human_size(result.original_bytes),
        human_size(result.converted_bytes),
        result.ratio * 100,
        encoder.label,
    )
    _handle_original(source, cfg)
    return result


class ConversionWorker(threading.Thread):
    """Background thread that serializes conversions from a queue."""

    def __init__(self, cfg: AppConfig, plugins: list | None = None) -> None:
        super().__init__(name="conversion-worker", daemon=True)
        self.cfg = cfg
        self.plugins = plugins or []
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._pending: set[Path] = set()
        self._lock = threading.Lock()

    def submit(self, path: Path) -> None:
        with self._lock:
            if path in self._pending:
                return
            self._pending.add(path)
        log.info("Queued: %s", path)
        self._queue.put(path)

    def stop(self) -> None:
        self._queue.put(None)

    def run(self) -> None:
        while True:
            path = self._queue.get()
            if path is None:
                return
            try:
                self._process(path)
            except Exception:
                # Belt and braces: _process handles its own errors, but the
                # worker must survive absolutely anything.
                log.exception("Unexpected error processing %s", path)
            finally:
                with self._lock:
                    self._pending.discard(path)

    def _process(self, path: Path) -> None:
        try:
            result = convert_file(path, self.cfg)
        except FileNotFoundError as exc:
            log.warning("%s", exc)
            return
        except Exception as exc:
            log.error("Conversion failed for %s: %s", path.name, exc)
            notify(self.cfg, "Conversion failed", f"{path.name}: {exc}")
            self._run_hook("on_conversion_failure", path, exc)
            return

        notify(
            self.cfg,
            "Screen recording converted",
            f"{result.dest.name} ({human_size(result.converted_bytes)})",
        )
        self._run_hook("on_conversion_success", result)

    def _run_hook(self, hook: str, *args) -> None:
        for plugin in self.plugins:
            fn = getattr(plugin, hook, None)
            if fn is None:
                continue
            try:
                fn(*args)
            except Exception:
                log.exception("Plugin %s failed in %s", type(plugin).__name__, hook)
