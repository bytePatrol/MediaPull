"""
Settings management module.

Two files:
  ~/.config/media-pull/config.json  — app config (window state, output dir)
  ~/.config/media-pull/settings.json — feature settings (cookies, encoding, etc.)

Usage:
  python -m python.settings load
  python -m python.settings save <json_string>
  python -m python.settings get-output-dir
"""

import json
import os
import sys
from pathlib import Path

from python.protocol import emit_result, emit_error


CONFIG_DIR = Path.home() / ".config" / "media-pull"
CONFIG_FILE = CONFIG_DIR / "config.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULT_CONFIG = {
    "output_dir": str(Path.home() / "Downloads"),
    "window_width": 960,
    "window_height": 700,
}

DEFAULT_SETTINGS = {
    "cookies": {
        "enabled": False,
        "browser": "",
        "profile": "",
    },
    "sponsorblock": {
        "enabled": True,
        "categories": [
            "sponsor", "intro", "outro", "selfpromo",
            "preview", "music_offtopic", "interaction", "filler",
        ],
    },
    "subtitles": {
        "enabled": False,
        "languages": ["en"],
        "auto_generated": True,
    },
    "encoding": {
        "encoder": "auto",
        "preset": "medium",
        "bitrate_mode": "auto",
        "audio_bitrate": "192k",
        "custom_bitrate": 15,
        "per_resolution": {
            "2160": 45,
            "1440": 30,
            "1080": 15,
            "720": 10,
            "480": 5,
        },
    },
    "playlist": {
        "default_selection": "all",
        "max_videos": 0,
    },
    "advanced": {
        "debug": False,
    },
}


def _ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load app config."""
    _ensure_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            # Merge with defaults
            result = {**DEFAULT_CONFIG, **data}
            return result
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """Save app config."""
    _ensure_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_settings() -> dict:
    """Load feature settings."""
    _ensure_dir()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
            # Deep merge with defaults
            result = _deep_merge(DEFAULT_SETTINGS, data)
            return result
        except (json.JSONDecodeError, IOError):
            pass
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def save_settings(settings: dict):
    """Save feature settings."""
    _ensure_dir()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def _deep_merge(default: dict, override: dict) -> dict:
    """Deep merge override into default."""
    result = dict(default)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.settings <load|save|get-output-dir>")
        return

    command = sys.argv[1]

    if command == "load":
        config = load_config()
        settings = load_settings()
        emit_result({"config": config, "settings": settings})

    elif command == "save":
        if len(sys.argv) < 3:
            emit_error("usage", "Usage: python -m python.settings save <json>")
            return
        try:
            data = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            emit_error("parse_error", "Invalid JSON")
            return

        if "config" in data:
            save_config(data["config"])
        if "settings" in data:
            save_settings(data["settings"])
        emit_result({"success": True})

    elif command == "get-output-dir":
        config = load_config()
        emit_result({"output_dir": config.get("output_dir", str(Path.home() / "Downloads"))})

    else:
        emit_error("usage", f"Unknown command: {command}")


if __name__ == "__main__":
    main()
