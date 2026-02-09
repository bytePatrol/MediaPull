"""
Custom error types and yt-dlp stderr error classifier.
"""


class YtDlpError(Exception):
    """Base error for yt-dlp related failures."""
    code = "ytdlp_error"

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class AgeRestrictedError(YtDlpError):
    """Video requires age verification / sign-in."""
    code = "age_restricted"

    def __init__(self, message: str = ""):
        super().__init__(
            message or "This video is age-restricted. Enable cookies from a signed-in browser to download it."
        )


class PrivateVideoError(YtDlpError):
    """Video is private."""
    code = "private_video"

    def __init__(self, message: str = ""):
        super().__init__(message or "This video is private and cannot be downloaded.")


class VideoUnavailableError(YtDlpError):
    """Video is deleted, region-locked, or otherwise unavailable."""
    code = "video_unavailable"

    def __init__(self, message: str = ""):
        super().__init__(message or "This video is unavailable.")


class LoginRequiredError(YtDlpError):
    """Video requires YouTube authentication."""
    code = "login_required"

    def __init__(self, message: str = ""):
        super().__init__(
            message or "This video requires login. Enable cookies from a signed-in browser."
        )


class UnviewablePlaylistError(YtDlpError):
    """Playlist cannot be viewed (private, etc.)."""
    code = "unviewable_playlist"

    def __init__(self, message: str = ""):
        super().__init__(message or "This playlist is not accessible.")


class DownloadError(YtDlpError):
    """Generic download failure (403, network, etc.)."""
    code = "download_error"


class ConversionError(YtDlpError):
    """FFmpeg conversion failure."""
    code = "conversion_error"


def classify_error(stderr: str) -> YtDlpError:
    """
    Parse yt-dlp stderr output and return the appropriate error type.
    This is critical for providing actionable error messages to users.
    """
    stderr_lower = stderr.lower()

    if "sign in to confirm your age" in stderr_lower or "age-restricted" in stderr_lower:
        return AgeRestrictedError()

    if "private video" in stderr_lower:
        return PrivateVideoError()

    if "video unavailable" in stderr_lower or "this video has been removed" in stderr_lower:
        return VideoUnavailableError()

    if "this content is not available" in stderr_lower:
        return VideoUnavailableError("This video is not available in your region.")

    if "requires login" in stderr_lower or "cookies" in stderr_lower and "please" in stderr_lower:
        return LoginRequiredError()

    if "unable to recognize playlist" in stderr_lower or "not a valid url" in stderr_lower:
        return UnviewablePlaylistError()

    if "http error 403" in stderr_lower or "forbidden" in stderr_lower:
        return DownloadError(
            "HTTP 403 Forbidden. YouTube is blocking the download. Try:\n"
            "1. Update yt-dlp to the latest version\n"
            "2. Enable cookies from a browser with a signed-in account\n"
            "3. Wait a few minutes and try again"
        )

    if "http error 429" in stderr_lower:
        return DownloadError(
            "Rate limited by YouTube. Wait a few minutes before trying again."
        )

    # Generic error with the actual stderr message
    # Take the last meaningful line from stderr
    lines = [l.strip() for l in stderr.strip().split("\n") if l.strip() and "WARNING" not in l.upper()]
    msg = lines[-1] if lines else stderr.strip()[:200]
    return YtDlpError(msg or "Unknown yt-dlp error")
