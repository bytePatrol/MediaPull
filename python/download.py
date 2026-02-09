"""
Download module: video + audio stream downloads with retry system.

Usage:
  python -m python.download run --url URL --quality QUALITY --output-dir DIR [options]

The full pipeline: download_video → download_audio → convert → sponsorblock
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from python.protocol import emit_result, emit_error, emit_log, emit_progress
from python.models import FORMAT_SELECTORS, BITRATE_PRESETS
from python.errors import classify_error, DownloadError
from python.exec_resolve import build_ytdlp_cmd, get_env
from python.utils import sanitize_filename, find_temp_file, parse_youtube_url, unique_filepath


# Retry configuration
MAX_ATTEMPTS = 6
RETRY_DELAYS = [10, 20, 30, 45, 60]
SILENT_RETRIES = 2


def _get_format_selector(quality: str, attempt: int = 0, last_format_id: str = None) -> str:
    """
    Build format selector string based on quality.
    For 4K+: resolution-first. For <=1080p: prefer H.264.
    After first failure with specific format, switch to generic.
    """
    try:
        height = int(quality.replace("p", "").replace("k", "").replace("K", ""))
        if quality.lower() in ("4k", "2160", "2160p"):
            height = 2160
    except ValueError:
        height = 1080

    if height >= 1440:
        return FORMAT_SELECTORS["resolution_first"]
    else:
        if attempt > 0 and last_format_id:
            # After first failure, use generic selector
            return FORMAT_SELECTORS["generic"].format(h=height)
        return FORMAT_SELECTORS["h264_pref"].format(h=height)


def _parse_progress(line: str) -> dict | None:
    """Parse yt-dlp progress output line."""
    # [download]  42.5% of 1.23GiB at 12.3MiB/s ETA 01:24
    m = re.search(
        r"\[download\]\s+(\d+\.?\d*)%\s+of\s+~?(\S+)\s+at\s+(\S+)\s+ETA\s+(\S+)",
        line
    )
    if m:
        percent = float(m.group(1))
        speed_str = m.group(3)
        eta_str = m.group(4)

        # Parse speed
        speed_mbps = 0.0
        sm = re.match(r"([\d.]+)(Ki|Mi|Gi)?B/s", speed_str)
        if sm:
            val = float(sm.group(1))
            unit = sm.group(2) or ""
            if unit == "Gi":
                speed_mbps = val * 1024
            elif unit == "Mi":
                speed_mbps = val
            elif unit == "Ki":
                speed_mbps = val / 1024
            else:
                speed_mbps = val / (1024 * 1024)

        # Parse ETA
        eta_secs = 0.0
        parts = eta_str.split(":")
        try:
            if len(parts) == 3:
                eta_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                eta_secs = int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            pass

        return {
            "percent": percent,
            "speed_mbps": speed_mbps,
            "eta_seconds": eta_secs,
        }
    return None


def download_stream(
    url: str,
    format_selector: str,
    output_template: str,
    stage: str,
    stage_offset: float = 0.0,
    stage_weight: float = 40.0,
    trim_start: str = None,
    trim_end: str = None,
    cookies_browser: str = None,
    cookies_profile: str = None,
) -> str | None:
    """
    Download a single stream (video or audio) with retry system.
    Returns the output file path or None on failure.
    """
    last_format_id = None

    for attempt in range(MAX_ATTEMPTS):
        if attempt > 0:
            delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
            is_silent = attempt <= SILENT_RETRIES

            if not is_silent:
                emit_log("warning", f"Retry {attempt}/{MAX_ATTEMPTS-1} in {delay}s...")
            else:
                emit_log("debug", f"Retry {attempt} in {delay}s...")

            # Countdown progress during wait
            for remaining in range(delay, 0, -1):
                emit_progress(f"{stage}_retry", stage_offset, speed_mbps=0, eta_seconds=remaining)
                time.sleep(1)

        # Build format selector (may switch to generic after failures)
        current_selector = format_selector
        if attempt > 0 and last_format_id:
            # For 4K, switch to generic after first failure
            m = re.search(r"\d{3,4}", format_selector)
            if m and int(m.group()) >= 1440:
                current_selector = FORMAT_SELECTORS["resolution_first"]

        args = [
            "-f", current_selector,
            "-o", output_template,
            "--no-continue",
            "--force-overwrites",
            "--no-playlist",
            "--no-mtime",
        ]

        # Trim support
        if trim_start or trim_end:
            start = trim_start or "0"
            end = trim_end or "inf"
            args.extend(["--download-sections", f"*{start}-{end}"])

        # Cookie support
        if cookies_browser:
            cookie_str = cookies_browser
            if cookies_profile:
                cookie_str += f":{cookies_profile}"
            args.extend(["--cookies-from-browser", cookie_str])

        args.append(url)
        cmd = build_ytdlp_cmd(args)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=get_env(),
            )

            # Stream progress from stdout
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue

                progress = _parse_progress(line)
                if progress:
                    # Map 0-100% to stage range
                    overall = stage_offset + (progress["percent"] / 100.0) * stage_weight
                    emit_progress(stage, overall, progress["speed_mbps"], progress["eta_seconds"])

                # Extract format ID for retry fallback
                m = re.search(r"Downloading format (\S+)", line)
                if m:
                    last_format_id = m.group(1)

            proc.wait(timeout=300)
            stderr = proc.stderr.read()

            if proc.returncode == 0:
                # Find the output file
                output_dir = str(Path(output_template).parent)
                video_id = parse_youtube_url(url).get("video_id", "")

                # Check for the file
                stem = Path(output_template).stem.split(".")[0]
                for f in Path(output_dir).iterdir():
                    if stem in f.name and f.stat().st_size > 1024:
                        return str(f)

                # Broader search
                found = find_temp_file(output_dir, video_id)
                if found:
                    return found

                emit_log("warning", "Download reported success but file not found, retrying...")
                continue

            # Non-zero exit — classify error
            err = classify_error(stderr)
            if attempt < MAX_ATTEMPTS - 1:
                if attempt >= SILENT_RETRIES:
                    emit_log("warning", f"Download failed: {err.message}")
                continue
            else:
                emit_error(err.code, err.message)
                return None

        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
            emit_log("warning", "Download timed out")
            continue
        except Exception as e:
            emit_log("error", f"Download error: {e}")
            if attempt >= MAX_ATTEMPTS - 1:
                emit_error("download_error", str(e))
                return None

    emit_error("download_error", "All download attempts failed")
    return None


def run_pipeline(args):
    """Run the full download pipeline."""
    url = args.url
    quality = args.quality
    output_dir = args.output_dir
    audio_only = args.audio_only

    # Parse chapters if provided
    chapters = None
    if args.chapters:
        import json as _json
        try:
            chapters = _json.loads(args.chapters)
        except Exception:
            emit_error("chapters_error", "Invalid chapters JSON")
            return

    parsed = parse_youtube_url(url)
    video_id = parsed.get("video_id", "unknown")

    os.makedirs(output_dir, exist_ok=True)
    temp_dir = output_dir

    emit_log("info", f"Starting download: {quality}")

    if audio_only:
        # Audio-only download
        emit_log("info", "Downloading audio...")
        audio_template = os.path.join(temp_dir, f"{video_id}_audio.%(ext)s")
        audio_file = download_stream(
            url=url,
            format_selector=FORMAT_SELECTORS["audio"],
            output_template=audio_template,
            stage="download_audio",
            stage_offset=0,
            stage_weight=80,
            trim_start=args.trim_start,
            trim_end=args.trim_end,
            cookies_browser=args.cookies_browser,
            cookies_profile=args.cookies_profile,
        )

        if not audio_file:
            return

        # Get title for final filename
        title = _fetch_title(url, args)
        safe_title = sanitize_filename(title)
        ext = Path(audio_file).suffix
        final_path = unique_filepath(Path(output_dir) / f"{safe_title}{ext}")

        os.rename(audio_file, final_path)
        emit_progress("complete", 100)
        emit_result({
            "output_path": str(final_path),
            "title": title,
        })
        return

    # Progress weights depend on whether we're splitting chapters
    # Chapters: video(0-35) audio(35-55) convert(55-80) split(80-100)
    # Normal:   video(0-40) audio(40-60) convert(60-85) sponsorblock(85-100)
    if chapters:
        VID_OFF, VID_WT = 0, 35
        AUD_OFF, AUD_WT = 35, 20
        CVT_OFF, CVT_WT = 55, 25
    else:
        VID_OFF, VID_WT = 0, 40
        AUD_OFF, AUD_WT = 40, 20
        CVT_OFF, CVT_WT = 60, 25

    # Video download pipeline
    # Stage 1: Download video
    emit_log("info", "Downloading video stream...")
    video_selector = _get_format_selector(quality)
    video_template = os.path.join(temp_dir, f"{video_id}_temp_video.%(ext)s")

    video_file = download_stream(
        url=url,
        format_selector=video_selector,
        output_template=video_template,
        stage="download_video",
        stage_offset=VID_OFF,
        stage_weight=VID_WT,
        trim_start=args.trim_start,
        trim_end=args.trim_end,
        cookies_browser=args.cookies_browser,
        cookies_profile=args.cookies_profile,
    )

    if not video_file:
        return

    # Stage 2: Download audio
    emit_log("info", "Downloading audio stream...")
    audio_template = os.path.join(temp_dir, f"{video_id}_temp_audio.%(ext)s")

    audio_file = download_stream(
        url=url,
        format_selector=FORMAT_SELECTORS["audio"],
        output_template=audio_template,
        stage="download_audio",
        stage_offset=AUD_OFF,
        stage_weight=AUD_WT,
        trim_start=args.trim_start,
        trim_end=args.trim_end,
        cookies_browser=args.cookies_browser,
        cookies_profile=args.cookies_profile,
    )

    if not audio_file:
        _cleanup_temp(temp_dir, video_id)
        return

    # Stage 3: Convert/merge
    emit_log("info", "Merging and encoding...")
    title = _fetch_title(url, args)
    safe_title = sanitize_filename(title)
    final_path = unique_filepath(Path(output_dir) / f"{safe_title}.mp4")

    # Parse per-resolution bitrates if provided
    per_res = None
    if args.per_res_bitrates:
        import json as _json
        try:
            per_res = {int(k): int(v) for k, v in _json.loads(args.per_res_bitrates).items()}
        except Exception:
            pass

    from python.convert import merge_and_encode
    success = merge_and_encode(
        video_file=video_file,
        audio_file=audio_file,
        output_path=str(final_path),
        stage_offset=CVT_OFF,
        stage_weight=CVT_WT,
        bitrate_mode=args.bitrate_mode,
        custom_bitrate=args.custom_bitrate,
        per_res_bitrates=per_res,
    )

    if not success:
        _cleanup_temp(temp_dir, video_id)
        return

    # Stage 4: Chapters or SponsorBlock
    if chapters:
        # Split into chapter files
        emit_log("info", f"Splitting into {len(chapters)} chapters...")
        from python.chapters import split_chapters
        output_files = split_chapters(
            video_file=str(final_path),
            chapters=chapters,
            output_dir=output_dir,
            title=title,
            stage_offset=80,
            stage_weight=20,
        )

        # Delete the full encoded file — chapters are the deliverables
        try:
            final_path.unlink(missing_ok=True)
        except Exception:
            pass

        _cleanup_temp(temp_dir, video_id)
        emit_progress("complete", 100)
        emit_log("info", f"Chapter download complete: {len(output_files)} files")
        emit_result({
            "output_files": output_files,
            "title": title,
            "chapter_count": len(output_files),
        })
    else:
        # SponsorBlock (85-100%)
        if args.sponsorblock:
            emit_log("info", "Checking SponsorBlock...")
            from python.sponsorblock import remove_sponsors
            sponsored_path = remove_sponsors(
                video_path=str(final_path),
                video_id=video_id,
                stage_offset=85,
                stage_weight=15,
            )
            if sponsored_path:
                final_path = Path(sponsored_path)

        # Cleanup temp files
        _cleanup_temp(temp_dir, video_id)

        emit_progress("complete", 100)
        emit_log("info", f"Download complete: {final_path.name}")
        emit_result({
            "output_path": str(final_path),
            "title": title,
            "size": final_path.stat().st_size if final_path.exists() else 0,
        })


def _fetch_title(url: str, args) -> str:
    """Quick title fetch for naming the output file."""
    cmd = build_ytdlp_cmd([
        "--get-title", "--no-playlist", url,
    ])
    if args.cookies_browser:
        cookie_str = args.cookies_browser
        if args.cookies_profile:
            cookie_str += f":{args.cookies_profile}"
        cmd.extend(["--cookies-from-browser", cookie_str])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=get_env())
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().split("\n")[0]
    except Exception:
        pass
    return "video"


def _cleanup_temp(directory: str, video_id: str):
    """Remove temp files for a video ID."""
    try:
        for f in Path(directory).iterdir():
            if video_id in f.name and ("_temp_" in f.name or f.name.endswith(".part")):
                f.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--url", required=True)
    run_parser.add_argument("--quality", default="1080p")
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--audio-only", action="store_true")
    run_parser.add_argument("--sponsorblock", action="store_true")
    run_parser.add_argument("--trim-start")
    run_parser.add_argument("--trim-end")
    run_parser.add_argument("--cookies-browser")
    run_parser.add_argument("--cookies-profile")
    run_parser.add_argument("--bitrate-mode", default="auto")
    run_parser.add_argument("--custom-bitrate", type=int, default=None)
    run_parser.add_argument("--per-res-bitrates", default=None)
    run_parser.add_argument("--chapters", default=None, help="JSON array of chapters to split")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(args)
    else:
        emit_error("usage", "Usage: python -m python.download run --url URL ...")


if __name__ == "__main__":
    main()
