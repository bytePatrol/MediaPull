"""
SponsorBlock integration: query API and remove sponsor segments.

Uses SHA256 hash prefix for privacy-preserving API queries.

Usage:
  python -m python.sponsorblock remove --video FILE --video-id ID --output FILE
"""

import hashlib
import json
import re
import subprocess
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError

from python.protocol import emit_result, emit_error, emit_log, emit_progress
from python.exec_resolve import find_ffmpeg, get_env


API_BASE = "https://sponsor.ajay.app/api/skipSegments"

CATEGORIES = [
    "sponsor", "intro", "outro", "selfpromo",
    "preview", "music_offtopic", "interaction", "filler",
]


def fetch_segments(video_id: str, categories: list[str] | None = None) -> list[dict]:
    """
    Fetch sponsor segments from SponsorBlock API using hash prefix.
    Returns list of segments: [{"start": float, "end": float, "category": str}, ...]
    """
    if not categories:
        categories = CATEGORIES

    # SHA256 hash prefix (first 4 chars) for privacy
    hash_full = hashlib.sha256(video_id.encode()).hexdigest()
    hash_prefix = hash_full[:4]

    # Build category params
    cat_params = "&".join(f"category={c}" for c in categories)
    url = f"{API_BASE}/{hash_prefix}?{cat_params}"

    try:
        req = Request(url, headers={"User-Agent": "YouTube4KDownloader/1.0"})
        response = urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
    except URLError:
        emit_log("debug", "SponsorBlock API unavailable")
        return []
    except json.JSONDecodeError:
        return []

    # Find matching video in response
    segments = []
    for entry in data:
        if entry.get("videoID") != video_id:
            continue
        for seg in entry.get("segments", []):
            segments.append({
                "start": seg["segment"][0],
                "end": seg["segment"][1],
                "category": seg.get("category", "sponsor"),
            })

    return segments


def build_ffmpeg_filter(segments: list[dict], duration: float) -> str:
    """
    Build an ffmpeg select/aselect filter to KEEP non-sponsor parts.
    """
    if not segments:
        return ""

    # Sort segments by start time
    segments.sort(key=lambda s: s["start"])

    # Merge overlapping segments
    merged = []
    for seg in segments:
        if merged and seg["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], seg["end"])
        else:
            merged.append(dict(seg))

    # Build "keep" intervals
    keep_parts = []
    last_end = 0.0
    for seg in merged:
        if seg["start"] > last_end:
            keep_parts.append(f"between(t,{last_end},{seg['start']})")
        last_end = seg["end"]

    if last_end < duration:
        keep_parts.append(f"between(t,{last_end},{duration})")

    if not keep_parts:
        return ""

    select_expr = "+".join(keep_parts)
    return f"select='{select_expr}',setpts=N/FRAME_RATE/TB", f"aselect='{select_expr}',asetpts=N/SR/TB"


def remove_sponsors(
    video_path: str,
    video_id: str,
    stage_offset: float = 85.0,
    stage_weight: float = 15.0,
    categories: list[str] | None = None,
) -> str | None:
    """
    Remove sponsor segments from a video file.
    Returns the output path (may be same as input if no segments found).
    """
    emit_progress("sponsorblock", stage_offset)

    segments = fetch_segments(video_id, categories)
    if not segments:
        emit_log("info", "No sponsor segments found")
        emit_progress("sponsorblock", stage_offset + stage_weight)
        return video_path

    total_removed = sum(s["end"] - s["start"] for s in segments)
    emit_log("info", f"Found {len(segments)} sponsor segments ({total_removed:.0f}s total)")

    # Get video duration
    ffmpeg = find_ffmpeg()
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", video_path],
            capture_output=True, text=True, timeout=15
        )
        m = re.search(r"Duration:\s+(\d{2}):(\d{2}):(\d{2})\.(\d{2})", proc.stderr)
        if m:
            duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 100.0
        else:
            duration = 0
    except Exception:
        duration = 0

    if duration <= 0:
        emit_log("warning", "Could not determine duration, skipping SponsorBlock")
        return video_path

    filter_result = build_ffmpeg_filter(segments, duration)
    if not filter_result:
        return video_path

    video_filter, audio_filter = filter_result

    # Re-encode with segments removed
    output_path = video_path.replace(".mp4", "_nosponsor.mp4")
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "h264_videotoolbox",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=get_env()
        )

        for line in proc.stderr:
            line = line.strip()
            time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})", line)
            if time_match:
                h = int(time_match.group(1))
                m = int(time_match.group(2))
                s = int(time_match.group(3))
                current = h * 3600 + m * 60 + s
                if duration > 0:
                    pct = min(current / duration, 1.0)
                    overall = stage_offset + pct * stage_weight
                    emit_progress("sponsorblock", overall)

        proc.wait(timeout=3600)

        if proc.returncode == 0:
            # Replace original with processed version
            import os
            os.replace(output_path, video_path)
            emit_log("info", "Sponsor segments removed successfully")
            return video_path
        else:
            emit_log("warning", "SponsorBlock processing failed, keeping original")
            # Clean up failed output
            try:
                os.unlink(output_path)
            except Exception:
                pass
            return video_path

    except Exception as e:
        emit_log("warning", f"SponsorBlock error: {e}")
        return video_path


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.sponsorblock remove --video FILE --video-id ID")
        return

    if sys.argv[1] == "remove":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("remove")
        parser.add_argument("--video", required=True)
        parser.add_argument("--video-id", required=True)
        parser.add_argument("--output")
        args = parser.parse_args()

        result = remove_sponsors(args.video, args.video_id)
        if result:
            emit_result({"output_path": result})


if __name__ == "__main__":
    main()
