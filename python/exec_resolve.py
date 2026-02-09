"""
Binary resolution: find yt-dlp, ffmpeg, ffprobe, and deno executables.

Priority chain (highest to lowest):
1. User-updated binary in ~/Library/Application Support/Media Pull/
2. Bundled binary in app resources
3. Python module (yt-dlp only)
4. Homebrew (/opt/homebrew/bin or /usr/local/bin)
5. System PATH
"""

import os
import shutil
import subprocess
from pathlib import Path

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Media Pull"


def _is_executable(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def _find_in_path(name: str) -> str | None:
    """Find an executable in system PATH."""
    return shutil.which(name)


def find_ytdlp() -> tuple[str, str]:
    """
    Find yt-dlp executable.
    Returns (command, mode) where mode is 'binary' or 'module'.
    """
    # 1. User-updated binary
    user_bin = APP_SUPPORT_DIR / "yt-dlp"
    if _is_executable(user_bin):
        return str(user_bin), "binary"

    # 2. Bundled binary (set by Rust via environment)
    bundled = os.environ.get("YTDLP_BUNDLED_PATH")
    if bundled and _is_executable(Path(bundled)):
        return bundled, "binary"

    # 3. Python module
    try:
        result = subprocess.run(
            ["python3", "-c", "import yt_dlp"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return "python3", "module"
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 4. Homebrew
    for prefix in ["/opt/homebrew/bin", "/usr/local/bin"]:
        p = Path(prefix) / "yt-dlp"
        if _is_executable(p):
            return str(p), "binary"

    # 5. System PATH
    found = _find_in_path("yt-dlp")
    if found:
        return found, "binary"

    raise FileNotFoundError(
        "yt-dlp not found. Install it with: brew install yt-dlp"
    )


def find_ffmpeg() -> str:
    """Find ffmpeg executable."""
    # Bundled
    bundled = os.environ.get("FFMPEG_BUNDLED_PATH")
    if bundled and _is_executable(Path(bundled)):
        return bundled

    # Homebrew
    for prefix in ["/opt/homebrew/bin", "/usr/local/bin"]:
        p = Path(prefix) / "ffmpeg"
        if _is_executable(p):
            return str(p)

    # System PATH
    found = _find_in_path("ffmpeg")
    if found:
        return found

    raise FileNotFoundError(
        "ffmpeg not found. Install it with: brew install ffmpeg"
    )


def find_ffprobe() -> str | None:
    """Find ffprobe executable. Returns None if not found (non-critical)."""
    bundled = os.environ.get("FFPROBE_BUNDLED_PATH")
    if bundled and _is_executable(Path(bundled)):
        return bundled

    for prefix in ["/opt/homebrew/bin", "/usr/local/bin"]:
        p = Path(prefix) / "ffprobe"
        if _is_executable(p):
            return str(p)

    return _find_in_path("ffprobe")


def find_deno() -> str | None:
    """Find deno executable. Returns None if not found (non-critical)."""
    bundled = os.environ.get("DENO_BUNDLED_PATH")
    if bundled and _is_executable(Path(bundled)):
        return bundled

    for prefix in ["/opt/homebrew/bin", "/usr/local/bin"]:
        p = Path(prefix) / "deno"
        if _is_executable(p):
            return str(p)

    return _find_in_path("deno")


def build_ytdlp_cmd(extra_args: list[str] | None = None) -> list[str]:
    """
    Build a yt-dlp command list with proper ffmpeg location and environment.
    """
    ytdlp_path, mode = find_ytdlp()
    ffmpeg_path = find_ffmpeg()
    ffmpeg_dir = str(Path(ffmpeg_path).parent)

    if mode == "module":
        cmd = ["python3", "-m", "yt_dlp"]
    else:
        cmd = [ytdlp_path]

    cmd.extend(["--ffmpeg-location", ffmpeg_dir])

    if extra_args:
        cmd.extend(extra_args)

    return cmd


def get_env() -> dict[str, str]:
    """Get environment variables for subprocess calls."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # Set PATH to include binary locations
    extra_paths = []
    for prefix in ["/opt/homebrew/bin", "/usr/local/bin"]:
        if os.path.isdir(prefix):
            extra_paths.append(prefix)

    deno = find_deno()
    if deno:
        extra_paths.append(str(Path(deno).parent))

    if extra_paths:
        env["PATH"] = ":".join(extra_paths) + ":" + env.get("PATH", "")

    return env
