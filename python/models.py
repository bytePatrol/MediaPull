"""
Data models for Media Pull.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


@dataclass
class VideoFormat:
    format_id: str = ""
    ext: str = ""
    height: int = 0
    width: int = 0
    fps: float = 0.0
    vcodec: str = ""
    acodec: str = ""
    tbr: float = 0.0  # total bitrate in kbps
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    format_note: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Chapter:
    title: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def duration_str(self) -> str:
        return format_duration(self.duration)

    @property
    def start_time_str(self) -> str:
        return format_duration(self.start_time)

    @property
    def safe_filename(self) -> str:
        from python.utils import sanitize_filename
        return sanitize_filename(self.title)

    def to_dict(self):
        d = asdict(self)
        d["duration"] = self.duration
        d["duration_str"] = self.duration_str
        d["start_time_str"] = self.start_time_str
        return d


@dataclass
class PlaylistItem:
    id: str = ""
    title: str = ""
    url: str = ""
    duration: float = 0.0
    channel: str = ""
    index: int = 0
    is_available: bool = True

    def to_dict(self):
        return asdict(self)


@dataclass
class VideoInfo:
    id: str = ""
    title: str = ""
    channel: str = ""
    duration: float = 0.0
    views: int = 0
    url: str = ""
    thumbnail_url: str = ""
    upload_date: str = ""
    formats: list = field(default_factory=list)
    chapters: list = field(default_factory=list)
    playlist_items: list = field(default_factory=list)
    playlist_title: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "channel": self.channel,
            "duration": self.duration,
            "duration_str": format_duration(self.duration),
            "views": self.views,
            "views_str": format_views(self.views),
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "upload_date": self.upload_date,
            "formats": [f.to_dict() if hasattr(f, 'to_dict') else f for f in self.formats],
            "chapters": [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.chapters],
            "playlist_items": [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.playlist_items],
            "playlist_title": self.playlist_title,
        }


class DownloadStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


# Resolution presets: height -> (label, recommended codec note)
RESOLUTION_PRESETS = {
    2160: ("4K", "H.265 / VP9"),
    1440: ("1440p", "VP9"),
    1080: ("1080p", "H.264"),
    720: ("720p", "H.264"),
    480: ("480p", "H.264"),
}

# Per-resolution bitrates for H.264 encoding (kbps)
BITRATE_PRESETS = {
    2160: {"bitrate": "45M", "maxrate": "50M", "bufsize": "90M"},
    1440: {"bitrate": "20M", "maxrate": "24M", "bufsize": "40M"},
    1080: {"bitrate": "8M", "maxrate": "10M", "bufsize": "16M"},
    720: {"bitrate": "5M", "maxrate": "6M", "bufsize": "10M"},
    480: {"bitrate": "2M", "maxrate": "3M", "bufsize": "4M"},
}

# Format selectors for yt-dlp
FORMAT_SELECTORS = {
    # For <=1080p: prefer H.264
    "h264_pref": "bv*[vcodec^=avc1][height<={h}]/bv*[height<={h}][ext=mp4]/bv*[height<={h}]/bv*",
    # For 4K+: resolution first
    "resolution_first": "bv*[height>=2160]/bv*[height>=1440]/bv*",
    # Audio
    "audio": "bestaudio[acodec^=mp4a][ext=m4a]/bestaudio[ext=m4a]/bestaudio/best",
    # Generic fallback
    "generic": "bv*[height<={h}]/bv*",
}


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS string."""
    if seconds <= 0:
        return "0:00"
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_views(views: int) -> str:
    """Format view count into human-readable string."""
    if views >= 1_000_000_000:
        return f"{views / 1_000_000_000:.1f}B views"
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M views"
    if views >= 1_000:
        return f"{views / 1_000:.1f}K views"
    return f"{views} views"
