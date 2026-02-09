"""
Utility functions: filename sanitization, URL parsing, file finding, time formatting.
"""

import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """
    Sanitize a string for safe use as a filename.
    Removes non-ASCII, shell-dangerous characters, and truncates.
    """
    if not name:
        return "untitled"

    # Remove non-ASCII
    name = name.encode("ascii", errors="ignore").decode("ascii")

    # Replace shell-dangerous characters
    dangerous = r'[&;$|`\\<>{}()\[\]!#^~\'\"*?]'
    name = re.sub(dangerous, "", name)

    # Replace path separators and other problematic chars
    name = name.replace("/", "-").replace(":", "-")

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()

    # Remove leading/trailing dots and spaces
    name = name.strip(". ")

    # Truncate
    if len(name) > max_length:
        name = name[:max_length].strip()

    return name or "untitled"


def unique_filepath(path: Path) -> Path:
    """
    If path exists, append (1), (2), etc. to make it unique.
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        new_path = parent / f"{stem} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def parse_youtube_url(url: str) -> dict:
    """
    Parse a YouTube URL and extract video_id, playlist_id, and URL type.
    Returns dict with keys: video_id, playlist_id, is_playlist, is_mix
    """
    result = {
        "video_id": None,
        "playlist_id": None,
        "is_playlist": False,
        "is_mix": False,
        "url": url.strip(),
    }

    try:
        parsed = urlparse(url.strip())
        params = parse_qs(parsed.query)
    except Exception:
        return result

    # Extract video ID
    if "v" in params:
        result["video_id"] = params["v"][0]
    elif parsed.hostname in ("youtu.be",):
        result["video_id"] = parsed.path.lstrip("/").split("/")[0]

    # Extract playlist ID
    if "list" in params:
        result["playlist_id"] = params["list"][0]
        playlist_id = params["list"][0]

        # Detect Mix playlists (auto-generated Radio playlists)
        if playlist_id.startswith("RD"):
            result["is_mix"] = True

    # Determine if this is a playlist URL
    if parsed.path == "/playlist" or (
        result["playlist_id"] and not result["video_id"]
    ):
        result["is_playlist"] = True

    return result


def find_temp_file(
    directory: str,
    video_id: str,
    prefix: str = "_temp_video",
    exclude_prefix: str = "_temp_audio",
    max_wait: float = 3.0,
) -> str | None:
    """
    Find a temp file after yt-dlp download. Handles filesystem race conditions.
    Searches multiple patterns and waits for filesystem sync.
    """
    extensions = [".mp4", ".webm", ".mkv", ".m4a", ".opus", ".f137.mp4",
                  ".f313.webm", ".f315.webm", ".f271.webm"]
    dir_path = Path(directory)

    # Attempt 1: exact prefix match
    for f in dir_path.iterdir():
        if f.name.startswith(video_id + prefix) and f.suffix in extensions:
            if exclude_prefix and exclude_prefix in f.name:
                continue
            if f.stat().st_size > 1024:
                return str(f)

    # Attempt 2: wait and retry
    time.sleep(min(max_wait, 2.0))

    # Attempt 3: broader search by video_id
    for f in dir_path.iterdir():
        if video_id in f.name and prefix.lstrip("_") in f.name:
            if exclude_prefix and exclude_prefix in f.name:
                continue
            if f.stat().st_size > 1024:
                return str(f)

    # Attempt 4: glob search
    for pattern in [f"*{video_id}*{prefix}*", f"*{video_id}*"]:
        matches = list(dir_path.glob(pattern))
        for m in matches:
            if exclude_prefix and exclude_prefix in m.name:
                continue
            if m.is_file() and m.stat().st_size > 1024:
                return str(m)

    return None


def format_size(bytes_val: int | float) -> str:
    """Format byte count to human readable string."""
    if bytes_val <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def estimate_filesize(bitrate_kbps: float, duration_secs: float) -> int:
    """Estimate file size from bitrate and duration."""
    return int((bitrate_kbps * 1000 / 8) * duration_secs)


def parse_time_str(time_str: str) -> float:
    """Parse MM:SS or HH:MM:SS string to seconds."""
    parts = time_str.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return float(parts[0])
    except (ValueError, IndexError):
        return 0.0
