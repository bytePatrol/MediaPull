"""
Download history CRUD module.

Storage: ~/.config/media-pull/history.json

Usage:
  python -m python.history load
  python -m python.history add <json_entry>
  python -m python.history search <query>
  python -m python.history clear
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from python.protocol import emit_result, emit_error


HISTORY_FILE = Path.home() / ".config" / "media-pull" / "history.json"


def _load() -> list:
    """Load history from file."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save(entries: list):
    """Save history to file."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def load_history() -> list:
    """Load all history entries."""
    return _load()


def add_entry(entry: dict) -> dict:
    """Add a new history entry."""
    entries = _load()

    # Ensure required fields
    entry.setdefault("timestamp", datetime.now().isoformat())
    entry.setdefault("title", "Unknown")
    entry.setdefault("url", "")
    entry.setdefault("channel", "")
    entry.setdefault("quality", "")
    entry.setdefault("output_path", "")
    entry.setdefault("file_size", 0)

    entries.insert(0, entry)  # Most recent first

    # Keep max 500 entries
    entries = entries[:500]

    _save(entries)
    return entry


def search_history(query: str) -> list:
    """Search history by title, channel, or URL."""
    entries = _load()
    query_lower = query.lower()

    results = []
    for entry in entries:
        if (query_lower in entry.get("title", "").lower()
                or query_lower in entry.get("channel", "").lower()
                or query_lower in entry.get("url", "").lower()):
            results.append(entry)

    return results


def clear_history() -> dict:
    """Clear all history."""
    _save([])
    return {"success": True, "message": "History cleared"}


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.history <load|add|search|clear>")
        return

    command = sys.argv[1]

    if command == "load":
        entries = load_history()
        emit_result({"entries": entries, "count": len(entries)})

    elif command == "add":
        if len(sys.argv) < 3:
            emit_error("usage", "Usage: python -m python.history add <json>")
            return
        try:
            entry = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            emit_error("parse_error", "Invalid JSON")
            return
        result = add_entry(entry)
        emit_result(result)

    elif command == "search":
        if len(sys.argv) < 3:
            emit_error("usage", "Usage: python -m python.history search <query>")
            return
        results = search_history(sys.argv[2])
        emit_result({"entries": results, "count": len(results)})

    elif command == "clear":
        result = clear_history()
        emit_result(result)

    else:
        emit_error("usage", f"Unknown command: {command}")


if __name__ == "__main__":
    main()
