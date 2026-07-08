"""Hardware encoder detection.

``ffmpeg -encoders`` listing an encoder does not mean it works on this
machine (e.g. h264_nvenc is compiled in but there is no NVIDIA GPU), so each
candidate is verified with a tiny test encode to the null muxer. Results are
cached for the process lifetime.
"""

from __future__ import annotations

import functools
import logging
import shutil
import subprocess
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_TEST_TIMEOUT = 20  # seconds per encoder probe


@dataclass(frozen=True)
class Encoder:
    name: str  # ffmpeg encoder name, e.g. "h264_nvenc"
    label: str  # human-readable, e.g. "NVIDIA NVENC"
    hardware: bool
    # Extra input/global args required for this encoder (before -i).
    input_args: tuple[str, ...] = ()
    # Extra filter needed before encoding (e.g. hwupload for VAAPI).
    video_filter: str = ""
    extra_output_args: tuple[str, ...] = field(default_factory=tuple)


SOFTWARE = Encoder(name="libx264", label="Software (libx264)", hardware=False)

# Preference order: NVENC > QSV > AMF > VAAPI > software.
_CANDIDATES: tuple[Encoder, ...] = (
    Encoder(name="h264_nvenc", label="NVIDIA NVENC", hardware=True),
    Encoder(name="h264_qsv", label="Intel Quick Sync", hardware=True),
    Encoder(name="h264_amf", label="AMD AMF", hardware=True),
    Encoder(
        name="h264_vaapi",
        label="VA-API",
        hardware=True,
        input_args=("-vaapi_device", "/dev/dri/renderD128"),
        video_filter="format=nv12,hwupload",
    ),
    SOFTWARE,
)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


@functools.lru_cache(maxsize=1)
def _compiled_encoders() -> frozenset[str]:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=_TEST_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("Could not list ffmpeg encoders: %s", exc)
        return frozenset()
    names = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            names.add(parts[1])
    return frozenset(names)


def _probe(encoder: Encoder) -> bool:
    """Encode 0.1s of synthetic video with this encoder; True if it works."""
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", *encoder.input_args,
           "-f", "lavfi", "-i", "color=black:size=320x240:rate=30:duration=0.1"]
    if encoder.video_filter:
        cmd += ["-vf", encoder.video_filter]
    cmd += ["-c:v", encoder.name, "-f", "null", "-"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=_TEST_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@functools.lru_cache(maxsize=1)
def list_working_encoders() -> tuple[Encoder, ...]:
    """All candidate encoders verified to work here, in preference order."""
    if not ffmpeg_available():
        return ()
    compiled = _compiled_encoders()
    working = []
    for enc in _CANDIDATES:
        if enc.name not in compiled:
            continue
        if _probe(enc):
            working.append(enc)
            log.debug("Encoder available: %s", enc.label)
        else:
            log.debug("Encoder compiled but not functional: %s", enc.name)
    return tuple(working)


def detect_best_encoder(
    hardware_acceleration: bool = True, forced: str | None = None
) -> Encoder:
    """Pick the encoder to use, honoring config overrides.

    Falls back to software if a forced/hardware encoder is unavailable.
    """
    working = list_working_encoders()
    if forced:
        for enc in working:
            if enc.name == forced:
                return enc
        log.warning("Forced encoder %r not available; falling back", forced)
    if hardware_acceleration:
        for enc in working:
            if enc.hardware:
                return enc
    for enc in working:
        if not enc.hardware:
            return enc
    # ffmpeg missing or nothing probed successfully; the conversion attempt
    # will surface the real error to the user.
    return SOFTWARE
