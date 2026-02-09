"""
Browser cookie detection and testing module.

Detects installed browsers and profiles on macOS.
Tests cookie health by attempting to fetch video info.

Usage:
  python -m python.cookies detect
  python -m python.cookies test <browser> <profile>
"""

import configparser
import json
import os
import subprocess
import sys
from pathlib import Path

from python.protocol import emit_result, emit_error, emit_log
from python.exec_resolve import build_ytdlp_cmd, get_env


# Browser paths on macOS
BROWSER_PATHS = {
    "chrome": Path.home() / "Library" / "Application Support" / "Google" / "Chrome",
    "firefox": Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles",
    "edge": Path.home() / "Library" / "Application Support" / "Microsoft Edge",
    "safari": Path.home() / "Library" / "Safari",
}


def detect_browsers() -> list[dict]:
    """
    Detect installed browsers and their profiles.
    Returns list of {browser, profiles: [{name, path, is_default}]}
    """
    results = []

    # Chrome
    chrome_path = BROWSER_PATHS["chrome"]
    if chrome_path.exists():
        profiles = _detect_chrome_profiles(chrome_path)
        if profiles:
            results.append({"browser": "chrome", "profiles": profiles})

    # Firefox
    firefox_path = BROWSER_PATHS["firefox"]
    if firefox_path.parent.exists():
        profiles = _detect_firefox_profiles()
        if profiles:
            results.append({"browser": "firefox", "profiles": profiles})

    # Edge
    edge_path = BROWSER_PATHS["edge"]
    if edge_path.exists():
        profiles = _detect_chrome_profiles(edge_path)  # Same format as Chrome
        if profiles:
            results.append({"browser": "edge", "profiles": profiles})

    # Safari
    safari_path = BROWSER_PATHS["safari"]
    if safari_path.exists():
        results.append({
            "browser": "safari",
            "profiles": [{"name": "Default", "path": str(safari_path), "is_default": True}],
        })

    return results


def _detect_chrome_profiles(browser_dir: Path) -> list[dict]:
    """Detect Chrome/Edge profiles by reading Local State JSON."""
    profiles = []

    local_state = browser_dir / "Local State"
    if local_state.exists():
        try:
            with open(local_state) as f:
                data = json.load(f)
            info_cache = data.get("profile", {}).get("info_cache", {})
            for dir_name, info in info_cache.items():
                profile_path = browser_dir / dir_name
                if profile_path.exists():
                    profiles.append({
                        "name": info.get("name", dir_name),
                        "path": dir_name,
                        "is_default": dir_name == "Default",
                    })
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: scan for profile directories
    if not profiles:
        if (browser_dir / "Default").exists():
            profiles.append({"name": "Default", "path": "Default", "is_default": True})
        for d in browser_dir.iterdir():
            if d.is_dir() and d.name.startswith("Profile "):
                profiles.append({"name": d.name, "path": d.name, "is_default": False})

    return profiles


def _detect_firefox_profiles() -> list[dict]:
    """Detect Firefox profiles by parsing profiles.ini."""
    profiles = []
    profiles_ini = Path.home() / "Library" / "Application Support" / "Firefox" / "profiles.ini"

    if not profiles_ini.exists():
        return profiles

    config = configparser.ConfigParser()
    config.read(str(profiles_ini))

    for section in config.sections():
        if not section.startswith("Profile"):
            continue
        name = config.get(section, "Name", fallback="")
        path = config.get(section, "Path", fallback="")
        is_default = config.get(section, "Default", fallback="0") == "1"

        if name and path:
            profiles.append({
                "name": name,
                "path": path,
                "is_default": is_default,
            })

    return profiles


def test_cookies(browser: str, profile: str) -> dict:
    """
    Test if cookies from the specified browser/profile work.
    Attempts to fetch info for a known video.
    """
    cookie_str = browser
    if profile:
        cookie_str += f":{profile}"

    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    cmd = build_ytdlp_cmd([
        "--cookies-from-browser", cookie_str,
        "-J", "--no-playlist",
        test_url,
    ])

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=30, env=get_env()
        )
        if proc.returncode == 0:
            try:
                data = json.loads(proc.stdout)
                return {
                    "success": True,
                    "message": f"Cookies working! Detected as: {data.get('channel', 'Unknown')}",
                }
            except json.JSONDecodeError:
                pass

        return {
            "success": False,
            "message": "Cookie test failed. Make sure the browser is fully closed (Cmd+Q) and you're signed in.",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Cookie test timed out. Make sure the browser is fully closed.",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {e}",
        }


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.cookies <detect|test> ...")
        return

    command = sys.argv[1]

    if command == "detect":
        browsers = detect_browsers()
        emit_result({"browsers": browsers})
    elif command == "test":
        if len(sys.argv) < 4:
            emit_error("usage", "Usage: python -m python.cookies test <browser> <profile>")
            return
        result = test_cookies(sys.argv[2], sys.argv[3])
        emit_result(result)
    else:
        emit_error("usage", f"Unknown command: {command}")


if __name__ == "__main__":
    main()
