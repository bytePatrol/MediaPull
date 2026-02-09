"""
IPC Protocol: JSON line emission for Python → Rust communication.

Every Python module writes one JSON object per line to stdout.
Rust reads line-by-line, parses the 'event' field, and routes accordingly.
"""

import json
import sys


def _emit(obj: dict):
    """Write a JSON object as a single line to stdout and flush."""
    line = json.dumps(obj, ensure_ascii=False, default=str)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def emit_progress(stage: str, percent: float, speed_mbps: float = 0.0,
                  eta_seconds: float = 0.0, fps: float = 0.0):
    """Emit a progress event to the frontend."""
    _emit({
        "event": "progress",
        "stage": stage,
        "percent": round(percent, 1),
        "speed_mbps": round(speed_mbps, 2),
        "eta_seconds": round(eta_seconds, 1),
        "fps": round(fps, 1),
    })


def emit_result(data):
    """Emit the final result. Must be the last event on success."""
    _emit({
        "event": "result",
        "data": data,
    })


def emit_error(code: str, message: str):
    """Emit an error. Must be the last event on failure."""
    _emit({
        "event": "error",
        "code": code,
        "message": message,
    })


def emit_log(level: str, message: str):
    """Emit a log message. Level: info, warning, error, debug."""
    _emit({
        "event": "log",
        "level": level,
        "message": message,
    })
