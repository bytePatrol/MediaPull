"""
macOS notifications via osascript.

Usage:
  python -m python.notify <title> <message>
"""

import re
import subprocess
import sys

from python.protocol import emit_result, emit_error


def _sanitize(text: str) -> str:
    """Sanitize text for safe use in osascript to prevent injection."""
    # Remove characters that could break AppleScript strings
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    # Remove control characters
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    # Truncate
    return text[:200]


def send_notification(title: str, message: str):
    """Send a macOS notification."""
    safe_title = _sanitize(title)
    safe_message = _sanitize(message)

    script = f'display notification "{safe_message}" with title "{safe_title}"'

    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass  # Notifications are non-critical


def main():
    if len(sys.argv) < 3:
        emit_error("usage", "Usage: python -m python.notify <title> <message>")
        return

    title = sys.argv[1]
    message = sys.argv[2]
    send_notification(title, message)
    emit_result({"success": True})


if __name__ == "__main__":
    main()
