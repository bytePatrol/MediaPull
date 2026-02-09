"""
yt-dlp update check and installation module.

Checks GitHub API for stable and nightly releases.
Downloads yt-dlp_macos binary to ~/Library/Application Support/Media Pull/

Usage:
  python -m python.updater check
  python -m python.updater install <version> <true|false>
"""

import json
import os
import stat
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from python.protocol import emit_result, emit_error, emit_log, emit_progress


APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Media Pull"
VERSION_FILE = APP_SUPPORT_DIR / "yt-dlp-version.txt"

STABLE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
NIGHTLY_API = "https://api.github.com/repos/yt-dlp/yt-dlp-nightly-builds/releases/latest"


def _github_get(url: str) -> dict | None:
    """Fetch JSON from GitHub API."""
    try:
        req = Request(url, headers={
            "User-Agent": "YouTube4KDownloader/1.0",
            "Accept": "application/vnd.github.v3+json",
        })
        response = urlopen(req, timeout=15)
        return json.loads(response.read().decode())
    except (URLError, json.JSONDecodeError):
        return None


def check_updates() -> dict:
    """Check for yt-dlp updates. Returns current + available versions."""
    current_version = ""
    if VERSION_FILE.exists():
        current_version = VERSION_FILE.read_text().strip()

    # Also try to get version from the binary
    if not current_version:
        try:
            import subprocess
            from python.exec_resolve import find_ytdlp, get_env
            ytdlp_path, mode = find_ytdlp()
            if mode == "module":
                cmd = ["python3", "-m", "yt_dlp", "--version"]
            else:
                cmd = [ytdlp_path, "--version"]
            proc = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=10, env=get_env()
            )
            if proc.returncode == 0:
                current_version = proc.stdout.strip()
        except Exception:
            pass

    result = {"current_version": current_version}

    # Check stable
    stable_data = _github_get(STABLE_API)
    if stable_data:
        result["stable_version"] = stable_data.get("tag_name", "")
        result["stable_url"] = ""
        for asset in stable_data.get("assets", []):
            if asset["name"] == "yt-dlp_macos":
                result["stable_url"] = asset["browser_download_url"]
                break

    # Check nightly
    nightly_data = _github_get(NIGHTLY_API)
    if nightly_data:
        result["nightly_version"] = nightly_data.get("tag_name", "")
        result["nightly_url"] = ""
        for asset in nightly_data.get("assets", []):
            if asset["name"] == "yt-dlp_macos":
                result["nightly_url"] = asset["browser_download_url"]
                break

    # Determine if update is available
    result["update_available"] = (
        result.get("stable_version", "") != current_version
        and result.get("stable_version", "") != ""
    )

    return result


def install_update(version: str, nightly: bool = False) -> dict:
    """Download and install a specific yt-dlp version."""
    emit_log("info", f"Downloading yt-dlp {version}...")
    emit_progress("update", 10)

    # Get download URL
    api_url = NIGHTLY_API if nightly else STABLE_API
    data = _github_get(api_url)
    if not data:
        emit_error("update_error", "Failed to fetch release info from GitHub")
        return {"success": False}

    download_url = ""
    for asset in data.get("assets", []):
        if asset["name"] == "yt-dlp_macos":
            download_url = asset["browser_download_url"]
            break

    if not download_url:
        emit_error("update_error", "yt-dlp_macos binary not found in release")
        return {"success": False}

    # Download
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = APP_SUPPORT_DIR / "yt-dlp"

    try:
        emit_progress("update", 30)
        req = Request(download_url, headers={"User-Agent": "YouTube4KDownloader/1.0"})
        response = urlopen(req, timeout=120)
        total = int(response.headers.get("Content-Length", 0))

        with open(output_path, "wb") as f:
            downloaded = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = 30 + (downloaded / total) * 60
                    emit_progress("update", pct)

        # Make executable
        output_path.chmod(output_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        # Save version
        VERSION_FILE.write_text(version)

        emit_progress("update", 100)
        emit_log("info", f"yt-dlp updated to {version}")
        return {"success": True, "version": version, "path": str(output_path)}

    except Exception as e:
        emit_error("update_error", f"Download failed: {e}")
        return {"success": False}


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.updater <check|install>")
        return

    command = sys.argv[1]

    if command == "check":
        result = check_updates()
        emit_result(result)
    elif command == "install":
        if len(sys.argv) < 4:
            emit_error("usage", "Usage: python -m python.updater install <version> <nightly:true|false>")
            return
        version = sys.argv[2]
        nightly = sys.argv[3].lower() == "true"
        result = install_update(version, nightly)
        emit_result(result)
    else:
        emit_error("usage", f"Unknown command: {command}")


if __name__ == "__main__":
    main()
