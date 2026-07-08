"""Map quality presets to ffmpeg arguments for each encoder family.

Output targets maximum compatibility: H.264 + AAC, yuv420p pixel format,
``+faststart`` so the moov atom is at the front for streaming/preview.
Resolution, frame rate, and audio are passed through untouched.
"""

from __future__ import annotations

from pathlib import Path

from ..config import AppConfig, QualityPreset
from ..encoder import Encoder

# CRF-style quality value per preset. Used as -crf (libx264), -cq (nvenc),
# -global_quality (qsv), -qp (vaapi/amf). Lossless uses encoder-specific args.
_QUALITY = {
    QualityPreset.LOSSLESS: 0,
    QualityPreset.HIGH: 18,
    QualityPreset.BALANCED: 23,
    QualityPreset.SMALL: 28,
    QualityPreset.VERY_SMALL: 32,
}

_X264_SPEED = {
    QualityPreset.LOSSLESS: "medium",
    QualityPreset.HIGH: "slow",
    QualityPreset.BALANCED: "medium",
    QualityPreset.SMALL: "medium",
    QualityPreset.VERY_SMALL: "fast",
}


def _quality_args(encoder: Encoder, cfg: AppConfig) -> list[str]:
    preset = cfg.quality_preset
    q = cfg.crf if cfg.crf is not None else _QUALITY[preset]

    if cfg.video_bitrate:
        return ["-b:v", cfg.video_bitrate]

    if encoder.name == "libx264":
        args = ["-preset", _X264_SPEED[preset]]
        if preset is QualityPreset.LOSSLESS and cfg.crf is None:
            return args + ["-qp", "0"]
        return args + ["-crf", str(q)]
    if encoder.name == "h264_nvenc":
        if preset is QualityPreset.LOSSLESS and cfg.crf is None:
            return ["-preset", "p7", "-tune", "lossless"]
        return ["-preset", "p5", "-rc", "vbr", "-cq", str(q), "-b:v", "0"]
    if encoder.name == "h264_qsv":
        return ["-global_quality", str(max(q, 1))]
    # vaapi / amf and any future QP-style encoder.
    return ["-qp", str(q)]


def build_ffmpeg_command(
    source: Path, dest: Path, cfg: AppConfig, encoder: Encoder
) -> list[str]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        *encoder.input_args,
        "-i", str(source),
    ]

    filters = []
    # GNOME screencasts are variable-frame-rate in a 1ms timebase and only
    # contain frames where the screen changed; without normalization ffmpeg
    # guesses "1000 fps" and duplicates frames to fill it, producing a huge,
    # unplayable file. The fps filter resamples to a constant frame rate with
    # correct timing (frames land at their original moments).
    if cfg.target_fps:
        filters.append(f"fps={cfg.target_fps}")
    if encoder.video_filter:
        filters.append(encoder.video_filter)
    else:
        # yuv420p is what players (and WhatsApp/PowerPoint/etc.) expect;
        # GNOME's VP8/VP9 output is already 4:2:0 so this is usually a no-op.
        cmd += ["-pix_fmt", "yuv420p"]
    if filters:
        cmd += ["-vf", ",".join(filters)]

    cmd += ["-c:v", encoder.name, *_quality_args(encoder, cfg)]
    # Recordings may have no audio track; these flags simply don't apply then.
    cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(dest)]
    return cmd
