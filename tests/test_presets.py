from __future__ import annotations

from pathlib import Path

from screenrec_converter.config import AppConfig, QualityPreset
from screenrec_converter.converter import build_ffmpeg_command
from screenrec_converter.encoder import Encoder
from screenrec_converter.encoder.detect import SOFTWARE

SRC = Path("/in/rec.webm")
DST = Path("/out/rec.mp4")

NVENC = Encoder(name="h264_nvenc", label="NVIDIA NVENC", hardware=True)
VAAPI = Encoder(
    name="h264_vaapi", label="VA-API", hardware=True,
    input_args=("-vaapi_device", "/dev/dri/renderD128"),
    video_filter="format=nv12,hwupload",
)


def _cmd(cfg, encoder=SOFTWARE) -> list[str]:
    return build_ffmpeg_command(SRC, DST, cfg, encoder)


def test_software_high_quality(cfg):
    cmd = _cmd(cfg)
    assert cmd[0] == "ffmpeg"
    assert "-nostdin" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert cmd[cmd.index("-crf") + 1] == "18"
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert "+faststart" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert cmd[-1] == str(DST)


def test_vfr_source_is_resampled_to_constant_fps(cfg):
    # GNOME screencasts are VFR; without fps normalization ffmpeg duplicates
    # frames to the guessed 1000 fps and the output is unplayable.
    cmd = _cmd(cfg)
    assert cmd[cmd.index("-vf") + 1] == "fps=30"


def test_target_fps_none_keeps_source_timing(cfg):
    cfg.target_fps = None
    cmd = _cmd(cfg)
    assert "-vf" not in cmd


def test_lossless_uses_qp_zero(cfg):
    cfg.quality_preset = QualityPreset.LOSSLESS
    cmd = _cmd(cfg)
    assert cmd[cmd.index("-qp") + 1] == "0"
    assert "-crf" not in cmd


def test_crf_override(cfg):
    cfg.crf = 30
    assert _cmd(cfg)[_cmd(cfg).index("-crf") + 1] == "30"


def test_bitrate_overrides_crf(cfg):
    cfg.video_bitrate = "6M"
    cmd = _cmd(cfg)
    assert cmd[cmd.index("-b:v") + 1] == "6M"
    assert "-crf" not in cmd


def test_nvenc_uses_cq(cfg):
    cmd = _cmd(cfg, NVENC)
    assert cmd[cmd.index("-c:v") + 1] == "h264_nvenc"
    assert cmd[cmd.index("-cq") + 1] == "18"


def test_vaapi_uses_hwupload_filter_and_device(cfg):
    cmd = _cmd(cfg, VAAPI)
    assert cmd[cmd.index("-vaapi_device") + 1] == "/dev/dri/renderD128"
    # fps resample must happen on CPU frames, before upload to the GPU.
    assert cmd[cmd.index("-vf") + 1] == "fps=30,format=nv12,hwupload"
    # hw frames are uploaded by the filter; no CPU-side pix_fmt forcing
    assert "-pix_fmt" not in cmd
    assert cmd[cmd.index("-qp") + 1] == "18"


def test_all_presets_produce_commands(cfg):
    for preset in QualityPreset:
        cfg.quality_preset = preset
        for enc in (SOFTWARE, NVENC, VAAPI):
            cmd = build_ffmpeg_command(SRC, DST, cfg, enc)
            assert cmd[0] == "ffmpeg" and cmd[-1] == str(DST)
