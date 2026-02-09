"""
Video/playlist analysis module.

Two-phase analysis:
  Phase 1: yt-dlp -J <url> for basic metadata
  Phase 2: yt-dlp --list-formats <url> for reliable format table parsing

Usage:
  python -m python.analyze video <url>
  python -m python.analyze playlist <url>
"""

import json
import re
import subprocess
import sys

from python.protocol import emit_result, emit_error, emit_log, emit_progress
from python.models import VideoInfo, VideoFormat, Chapter, PlaylistItem
from python.errors import classify_error
from python.exec_resolve import build_ytdlp_cmd, get_env
from python.utils import parse_youtube_url


TIMEOUT_VIDEO = 90
TIMEOUT_PLAYLIST = 120


def _get_cookie_args() -> list[str]:
    """Get cookie arguments from environment if set."""
    browser = __import__("os").environ.get("COOKIES_BROWSER")
    profile = __import__("os").environ.get("COOKIES_PROFILE")
    if browser:
        cookie_str = browser
        if profile:
            cookie_str += f":{profile}"
        return ["--cookies-from-browser", cookie_str]
    return []


def analyze_video(url: str) -> dict:
    """Analyze a single video URL. Returns VideoInfo dict."""
    parsed = parse_youtube_url(url)

    # Check for Mix playlists — fall back to single video
    if parsed["is_mix"]:
        emit_log("warning", "Mix/Radio playlists can't be downloaded as playlists. Downloading single video.")
        if parsed["video_id"]:
            url = f"https://www.youtube.com/watch?v={parsed['video_id']}"

    emit_log("info", "Fetching video info...")
    emit_progress("analyze", 10)

    # Phase 1: Basic metadata via -J
    cmd = build_ytdlp_cmd([
        "-J", "--no-playlist",
        *_get_cookie_args(),
        url,
    ])

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=TIMEOUT_VIDEO, env=get_env()
        )
    except subprocess.TimeoutExpired:
        emit_error("timeout", f"Analysis timed out after {TIMEOUT_VIDEO}s")
        return None

    if proc.returncode != 0:
        err = classify_error(proc.stderr)
        emit_error(err.code, err.message)
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        emit_error("parse_error", "Failed to parse yt-dlp output")
        return None

    emit_progress("analyze", 50)

    # Build VideoInfo from JSON
    info = VideoInfo(
        id=data.get("id", ""),
        title=data.get("title", "Unknown"),
        channel=data.get("channel", data.get("uploader", "Unknown")),
        duration=data.get("duration", 0) or 0,
        views=data.get("view_count", 0) or 0,
        url=url,
        thumbnail_url=data.get("thumbnail", ""),
        upload_date=data.get("upload_date", ""),
    )

    # Parse chapters
    for ch in data.get("chapters", []) or []:
        info.chapters.append(Chapter(
            title=ch.get("title", ""),
            start_time=ch.get("start_time", 0),
            end_time=ch.get("end_time", 0),
        ))

    emit_log("info", "Fetching format table...")
    emit_progress("analyze", 60)

    # Phase 2: Format table parsing (more reliable than -J formats)
    fmt_cmd = build_ytdlp_cmd([
        "--list-formats", "--no-playlist",
        *_get_cookie_args(),
        url,
    ])

    try:
        fmt_proc = subprocess.run(
            fmt_cmd, capture_output=True, text=True,
            timeout=TIMEOUT_VIDEO, env=get_env()
        )
        if fmt_proc.returncode == 0:
            info.formats = _parse_format_table(fmt_proc.stdout)
    except subprocess.TimeoutExpired:
        emit_log("warning", "Format table fetch timed out, using JSON formats")
        # Fallback to -J formats
        info.formats = _parse_json_formats(data.get("formats", []))

    # If format table parsing returned nothing, fall back
    if not info.formats:
        info.formats = _parse_json_formats(data.get("formats", []))

    emit_progress("analyze", 100)
    emit_log("info", f"Found {len(info.formats)} formats, {len(info.chapters)} chapters")

    return info.to_dict()


def _parse_format_table(output: str) -> list[VideoFormat]:
    """
    Parse yt-dlp --list-formats text table output.
    This is more reliable than -J for finding all available formats.
    """
    formats = []
    in_table = False

    for line in output.split("\n"):
        line = line.strip()

        # Detect table start
        if line.startswith("ID") and "EXT" in line:
            in_table = True
            continue
        if line.startswith("---"):
            continue
        if not in_table or not line:
            continue

        # Parse format line
        parts = line.split()
        if len(parts) < 3:
            continue

        fmt = VideoFormat(format_id=parts[0], ext=parts[1])

        # Try to extract resolution
        for part in parts:
            m = re.match(r"(\d{3,4})x(\d{3,4})", part)
            if m:
                fmt.width = int(m.group(1))
                fmt.height = int(m.group(2))
                break
            # Also try standalone height like "1080p"
            m2 = re.match(r"(\d{3,4})p", part)
            if m2:
                fmt.height = int(m2.group(1))
                break

        # Extract codec info
        for part in parts:
            if part.startswith("avc1") or part.startswith("h264"):
                fmt.vcodec = part
            elif part.startswith("vp9") or part.startswith("vp09"):
                fmt.vcodec = part
            elif part.startswith("av01"):
                fmt.vcodec = part
            elif part.startswith("mp4a") or part.startswith("aac"):
                fmt.acodec = part
            elif part.startswith("opus"):
                fmt.acodec = part

        # Extract FPS
        for part in parts:
            m = re.match(r"(\d+)fps", part)
            if m:
                fmt.fps = float(m.group(1))
                break

        # Extract bitrate
        for part in parts:
            m = re.match(r"~?(\d+\.?\d*)k", part, re.IGNORECASE)
            if m:
                fmt.tbr = float(m.group(1))
                break

        # Extract filesize
        for part in parts:
            m = re.match(r"~?(\d+\.?\d*)(Mi|Gi|Ki)B", part)
            if m:
                val = float(m.group(1))
                unit = m.group(2)
                if unit == "Gi":
                    fmt.filesize_approx = int(val * 1024 * 1024 * 1024)
                elif unit == "Mi":
                    fmt.filesize_approx = int(val * 1024 * 1024)
                elif unit == "Ki":
                    fmt.filesize_approx = int(val * 1024)
                break

        # Determine format note
        if "video only" in line.lower():
            fmt.format_note = "video only"
        elif "audio only" in line.lower():
            fmt.format_note = "audio only"

        if fmt.height > 0 or fmt.acodec:
            formats.append(fmt)

    return formats


def _parse_json_formats(json_formats: list) -> list[VideoFormat]:
    """Fallback: parse formats from -J JSON output."""
    formats = []
    for f in json_formats:
        fmt = VideoFormat(
            format_id=f.get("format_id", ""),
            ext=f.get("ext", ""),
            height=f.get("height", 0) or 0,
            width=f.get("width", 0) or 0,
            fps=f.get("fps", 0) or 0,
            vcodec=f.get("vcodec", "none") or "none",
            acodec=f.get("acodec", "none") or "none",
            tbr=f.get("tbr", 0) or 0,
            filesize=f.get("filesize"),
            filesize_approx=f.get("filesize_approx"),
            format_note=f.get("format_note", ""),
        )
        if fmt.height > 0 or (fmt.acodec and fmt.acodec != "none"):
            formats.append(fmt)
    return formats


def analyze_playlist(url: str) -> dict:
    """Analyze a playlist URL. Returns dict with playlist info and items."""
    emit_log("info", "Fetching playlist info...")
    emit_progress("analyze", 10)

    cmd = build_ytdlp_cmd([
        "-J", "--flat-playlist",
        *_get_cookie_args(),
        url,
    ])

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=TIMEOUT_PLAYLIST, env=get_env()
        )
    except subprocess.TimeoutExpired:
        emit_error("timeout", f"Playlist analysis timed out after {TIMEOUT_PLAYLIST}s")
        return None

    if proc.returncode != 0:
        err = classify_error(proc.stderr)
        emit_error(err.code, err.message)
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        emit_error("parse_error", "Failed to parse playlist data")
        return None

    items = []
    for i, entry in enumerate(data.get("entries", []) or []):
        if not entry:
            continue
        items.append(PlaylistItem(
            id=entry.get("id", ""),
            title=entry.get("title", f"Video {i+1}"),
            url=entry.get("url", f"https://www.youtube.com/watch?v={entry.get('id', '')}"),
            duration=entry.get("duration", 0) or 0,
            channel=entry.get("channel", entry.get("uploader", "")),
            index=i + 1,
            is_available=entry.get("title") != "[Private video]" and entry.get("title") != "[Deleted video]",
        ))

    emit_progress("analyze", 100)
    emit_log("info", f"Found {len(items)} videos in playlist")

    result = {
        "playlist_title": data.get("title", "Playlist"),
        "playlist_id": data.get("id", ""),
        "items": [item.to_dict() for item in items],
    }

    return result


def main():
    if len(sys.argv) < 3:
        emit_error("usage", "Usage: python -m python.analyze <video|playlist> <url>")
        return

    command = sys.argv[1]
    url = sys.argv[2]

    if command == "video":
        result = analyze_video(url)
        if result:
            emit_result(result)
    elif command == "playlist":
        result = analyze_playlist(url)
        if result:
            emit_result(result)
    else:
        emit_error("usage", f"Unknown command: {command}")


if __name__ == "__main__":
    main()
