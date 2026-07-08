"""inotify-based folder monitoring via watchdog.

Event-driven (no polling): GNOME Shell writes ``Screencast from ....webm``
into the watched folder; we react to create/move events for ``.webm`` files
and hand them to the conversion worker, which then waits for the recording
to actually finish (see converter.pipeline.wait_until_stable).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from watchdog.events import FileMovedEvent, FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

log = logging.getLogger(__name__)

WEBM_SUFFIX = ".webm"


class _WebmHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[Path], None]) -> None:
        self._callback = callback

    def _maybe_submit(self, raw_path: str | bytes) -> None:
        path = Path(raw_path if isinstance(raw_path, str) else raw_path.decode())
        if path.suffix.lower() != WEBM_SUFFIX:
            return
        if path.name.startswith("."):  # hidden/temp files
            return
        self._callback(path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._maybe_submit(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # A rename/move INTO a .webm name counts as a new recording.
        if not event.is_directory and isinstance(event, FileMovedEvent):
            self._maybe_submit(event.dest_path)


class RecordingWatcher:
    """Watches one directory for new .webm recordings."""

    def __init__(self, directory: Path, on_new_recording: Callable[[Path], None]) -> None:
        self.directory = directory
        self._observer = Observer()
        self._handler = _WebmHandler(on_new_recording)
        self._paused = False
        self._on_new_recording = on_new_recording

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        self._paused = True
        self._handler._callback = lambda _path: None
        log.info("Monitoring paused")

    def resume(self) -> None:
        self._paused = False
        self._handler._callback = self._on_new_recording
        log.info("Monitoring resumed")

    def start(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(self.directory), recursive=False)
        self._observer.start()
        log.info("Watching %s for new recordings", self.directory)

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=5)
