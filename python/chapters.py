"""
Chapter splitting module.

3-stage pipeline: download once → encode once → split with -c copy (instant).
Output: Video Title/01 - Chapter Name.mp4

Usage:
  python -m python.chapters split --video FILE --chapters JSON --output-dir DIR
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from python.protocol import emit_result, emit_error, emit_log, emit_progress
from python.exec_resolve import find_ffmpeg, get_env
from python.utils import sanitize_filename


def split_chapters(
    video_file: str,
    chapters: list[dict],
    output_dir: str,
    title: str = "Video",
    stage_offset: float = 0,
    stage_weight: float = 100,
) -> list[str]:
    """
    Split a video into chapters using stream copy (instant, no re-encoding).
    Chapters format: [{"title": str, "start_time": float, "end_time": float}, ...]
    Returns list of output file paths.
    """
    ffmpeg = find_ffmpeg()
    safe_title = sanitize_filename(title)
    chapter_dir = Path(output_dir) / safe_title
    chapter_dir.mkdir(parents=True, exist_ok=True)

    output_files = []
    total = len(chapters)

    for i, ch in enumerate(chapters):
        chapter_title = ch.get("title", f"Chapter {i+1}")
        start = ch.get("start_time", 0)
        end = ch.get("end_time", 0)

        safe_chapter = sanitize_filename(chapter_title)
        filename = f"{i+1:02d} - {safe_chapter}.mp4"
        output_path = str(chapter_dir / filename)

        pct = stage_offset + (i / total) * stage_weight
        emit_progress("split_chapters", pct)
        emit_log("info", f"Splitting chapter {i+1}/{total}: {chapter_title}")

        cmd = [
            ffmpeg, "-y",
            "-i", video_file,
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=120, env=get_env()
            )
            if proc.returncode == 0:
                output_files.append(output_path)
            else:
                emit_log("warning", f"Failed to split chapter: {chapter_title}")
        except subprocess.TimeoutExpired:
            emit_log("warning", f"Chapter split timed out: {chapter_title}")

    emit_progress("split_chapters", stage_offset + stage_weight)
    emit_log("info", f"Split {len(output_files)}/{total} chapters")
    return output_files


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.chapters split ...")
        return

    if sys.argv[1] == "split":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("split")
        parser.add_argument("--video", required=True)
        parser.add_argument("--chapters", required=True, help="JSON string of chapters array")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--title", default="Video")
        args = parser.parse_args()

        chapters = json.loads(args.chapters)
        files = split_chapters(args.video, chapters, args.output_dir, args.title)
        emit_result({"output_files": files, "count": len(files)})


if __name__ == "__main__":
    main()
