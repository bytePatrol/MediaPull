"""
FFmpeg merge/encode module.

Merges separate video + audio streams into a single H.264+AAC MP4.
Uses VideoToolbox (hardware) with automatic libx264 (CPU) fallback.

Usage:
  python -m python.convert merge --video FILE --audio FILE --output FILE
"""

import re
import subprocess
import sys

from python.protocol import emit_result, emit_error, emit_log, emit_progress
from python.models import BITRATE_PRESETS
from python.exec_resolve import find_ffmpeg, get_env


def detect_resolution(video_file: str) -> tuple[int, int]:
    """
    Detect actual source resolution using ffmpeg stderr.
    Returns (width, height).
    """
    ffmpeg = find_ffmpeg()
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", video_file],
            capture_output=True, text=True, timeout=15
        )
        stderr = proc.stderr
        # Parse: "Video: ... WIDTHxHEIGHT" or "WIDTHxHEIGHT [SAR"
        m = re.search(r"(\d{3,4})x(\d{3,4})", stderr)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 0, 0


def _get_bitrate_args(
    height: int,
    bitrate_mode: str = "auto",
    custom_bitrate: int | None = None,
    per_res_bitrates: dict | None = None,
) -> list[str]:
    """Get bitrate arguments based on mode.

    Modes:
      auto           — match source, no explicit bitrate args
      per-resolution — user-defined Mbps per resolution tier
      custom         — single Mbps value for all resolutions
    """
    if bitrate_mode == "auto":
        # No explicit bitrate — ffmpeg will match source
        return []

    if bitrate_mode == "custom" and custom_bitrate:
        br = f"{custom_bitrate}M"
        maxr = f"{int(custom_bitrate * 1.15)}M"
        buf = f"{custom_bitrate * 2}M"
        return ["-b:v", br, "-maxrate", maxr, "-bufsize", buf]

    if bitrate_mode == "per-resolution" and per_res_bitrates:
        # Find closest user-defined preset
        for preset_h in sorted(per_res_bitrates.keys(), reverse=True):
            if height >= preset_h:
                mbps = per_res_bitrates[preset_h]
                br = f"{mbps}M"
                maxr = f"{int(mbps * 1.15)}M"
                buf = f"{mbps * 2}M"
                return ["-b:v", br, "-maxrate", maxr, "-bufsize", buf]
        # Use the lowest tier
        lowest = min(per_res_bitrates.keys())
        mbps = per_res_bitrates[lowest]
        br = f"{mbps}M"
        maxr = f"{int(mbps * 1.15)}M"
        buf = f"{mbps * 2}M"
        return ["-b:v", br, "-maxrate", maxr, "-bufsize", buf]

    # Fallback: use built-in presets (per-resolution without custom values)
    for preset_h in sorted(BITRATE_PRESETS.keys(), reverse=True):
        if height >= preset_h:
            bp = BITRATE_PRESETS[preset_h]
            return ["-b:v", bp["bitrate"], "-maxrate", bp["maxrate"], "-bufsize", bp["bufsize"]]

    bp = BITRATE_PRESETS[480]
    return ["-b:v", bp["bitrate"], "-maxrate", bp["maxrate"], "-bufsize", bp["bufsize"]]


def _parse_ffmpeg_progress(line: str, total_duration: float) -> dict | None:
    """Parse ffmpeg stderr progress line."""
    # frame=  123 fps= 45 ... time=00:01:23.45 ...
    time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
    fps_match = re.search(r"fps=\s*(\d+\.?\d*)", line)

    if time_match:
        h = int(time_match.group(1))
        m = int(time_match.group(2))
        s = int(time_match.group(3))
        cs = int(time_match.group(4))
        current_time = h * 3600 + m * 60 + s + cs / 100.0

        percent = 0.0
        if total_duration > 0:
            percent = min((current_time / total_duration) * 100.0, 100.0)

        fps = 0.0
        if fps_match:
            fps = float(fps_match.group(1))

        return {"percent": percent, "fps": fps, "current_time": current_time}
    return None


def _get_duration(video_file: str) -> float:
    """Get video duration using ffmpeg."""
    ffmpeg = find_ffmpeg()
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", video_file],
            capture_output=True, text=True, timeout=15
        )
        m = re.search(r"Duration:\s+(\d{2}):(\d{2}):(\d{2})\.(\d{2})", proc.stderr)
        if m:
            h = int(m.group(1))
            min_ = int(m.group(2))
            s = int(m.group(3))
            cs = int(m.group(4))
            return h * 3600 + min_ * 60 + s + cs / 100.0
    except Exception:
        pass
    return 0.0


def merge_and_encode(
    video_file: str,
    audio_file: str,
    output_path: str,
    stage_offset: float = 60.0,
    stage_weight: float = 25.0,
    bitrate_mode: str = "auto",
    custom_bitrate: int | None = None,
    per_res_bitrates: dict | None = None,
) -> bool:
    """
    Merge video + audio and encode to H.264+AAC MP4.
    Returns True on success.
    """
    ffmpeg = find_ffmpeg()
    width, height = detect_resolution(video_file)
    total_duration = _get_duration(video_file)

    emit_log("info", f"Source resolution: {width}x{height}")

    bitrate_args = _get_bitrate_args(height, bitrate_mode, custom_bitrate, per_res_bitrates)
    if bitrate_mode != "auto":
        emit_log("info", f"Bitrate mode: {bitrate_mode}")

    # Try VideoToolbox first, then fall back to libx264
    for encoder in ["h264_videotoolbox", "libx264"]:
        cmd = [
            ffmpeg, "-y",
            "-i", video_file,
            "-i", audio_file,
            "-c:v", encoder,
        ]

        # Explicit resolution to prevent VideoToolbox downscaling
        if width > 0 and height > 0:
            cmd.extend(["-s", f"{width}x{height}"])

        cmd.extend(bitrate_args)
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-shortest",
        ])

        if encoder == "libx264":
            cmd.extend(["-preset", "medium"])

        cmd.append(output_path)

        emit_log("info", f"Encoding with {encoder}...")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=get_env(),
            )

            # Parse progress from stderr
            for line in proc.stderr:
                line = line.strip()
                if not line:
                    continue

                progress = _parse_ffmpeg_progress(line, total_duration)
                if progress:
                    overall = stage_offset + (progress["percent"] / 100.0) * stage_weight
                    emit_progress("convert", overall, fps=progress.get("fps", 0))

            proc.wait(timeout=3600)  # 1 hour timeout for long videos

            if proc.returncode == 0:
                emit_log("info", f"Encoding complete with {encoder}")
                return True

            stderr_out = proc.stderr.read() if proc.stderr else ""
            if encoder == "h264_videotoolbox":
                emit_log("warning", f"VideoToolbox failed, falling back to libx264...")
                continue
            else:
                emit_error("conversion_error", f"FFmpeg encoding failed: {stderr_out[:200]}")
                return False

        except subprocess.TimeoutExpired:
            proc.kill()
            emit_error("conversion_error", "Encoding timed out (>1 hour)")
            return False
        except Exception as e:
            if encoder == "h264_videotoolbox":
                emit_log("warning", f"VideoToolbox error: {e}, falling back to libx264...")
                continue
            emit_error("conversion_error", str(e))
            return False

    emit_error("conversion_error", "All encoders failed")
    return False


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.convert merge --video FILE --audio FILE --output FILE")
        return

    if sys.argv[1] == "merge":
        import argparse
        import json as _json
        parser = argparse.ArgumentParser()
        parser.add_argument("merge")
        parser.add_argument("--video", required=True)
        parser.add_argument("--audio", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--bitrate-mode", default="auto")
        parser.add_argument("--custom-bitrate", type=int, default=None)
        parser.add_argument("--per-res-bitrates", default=None)
        args = parser.parse_args()

        per_res = None
        if args.per_res_bitrates:
            try:
                per_res = {int(k): int(v) for k, v in _json.loads(args.per_res_bitrates).items()}
            except Exception:
                pass

        success = merge_and_encode(
            args.video, args.audio, args.output,
            bitrate_mode=args.bitrate_mode,
            custom_bitrate=args.custom_bitrate,
            per_res_bitrates=per_res,
        )
        if success:
            emit_result({"output_path": args.output})


if __name__ == "__main__":
    main()
