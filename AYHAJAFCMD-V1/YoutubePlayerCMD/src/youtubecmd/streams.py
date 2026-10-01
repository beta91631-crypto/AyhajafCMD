"""YouTube URL validation and yt-dlp format selection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, parse_qs

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
SUPPORTED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}
INVALID_URL_MESSAGE = "Invalid YouTube URL."


class StreamError(Exception):
    """Expected stream extraction or format-selection failure."""


@dataclass(frozen=True)
class StreamInfo:
    title: str
    duration: float | None
    fps: float
    width: int
    height: int
    video_url: str
    audio_url: str


def validate_youtube_url(value: str) -> bool:
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme.lower() not in {"http", "https"} or host not in SUPPORTED_HOSTS:
            return False

        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]
        elif parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 2 or parts[0] not in {"embed", "shorts", "live"}:
                return False
            video_id = parts[1]
        return bool(VIDEO_ID_PATTERN.fullmatch(video_id))
    except (ValueError, AttributeError):
        return False


def _format_rank(item: dict) -> tuple[float, float]:
    return (float(item.get("height") or 0), float(item.get("tbr") or 0))


def choose_formats(info: dict, max_height: int | None = 480) -> tuple[dict, dict]:
    formats = [item for item in info.get("formats", []) if item.get("url")]
    video_only = [
        item
        for item in formats
        if item.get("vcodec") not in (None, "none")
        and item.get("acodec") in (None, "none")
    ]
    audio_only = [
        item
        for item in formats
        if item.get("acodec") not in (None, "none")
        and item.get("vcodec") in (None, "none")
    ]

    if video_only and audio_only:
        eligible_video = [
            item for item in video_only
            if max_height is None or (item.get("height") or 0) <= max_height
        ]
        video = max(eligible_video or video_only, key=_format_rank)
        audio = max(audio_only, key=lambda item: float(item.get("abr") or 0))
        return video, audio

    combined = [
        item
        for item in formats
        if item.get("vcodec") not in (None, "none")
        and item.get("acodec") not in (None, "none")
    ]
    eligible_combined = [
        item for item in combined
        if max_height is None or (item.get("height") or 0) <= max_height
    ]
    if combined:
        selected = max(eligible_combined or combined, key=_format_rank)
        return selected, selected
    raise StreamError("No compatible video and audio formats were found.")


def extract_streams(url: str, max_height: int = 480) -> StreamInfo:
    if not validate_youtube_url(url):
        raise StreamError(INVALID_URL_MESSAGE)
    try:
        import yt_dlp

        options = {"quiet": True, "no_warnings": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
    except ImportError as error:
        raise StreamError("yt-dlp is not installed. Run YouTubeCMD.bat to install it.") from error
    except Exception as error:
        message = str(error).lower()
        if "private" in message:
            summary = "This video is private."
        elif "age" in message or "sign in" in message or "login" in message:
            summary = "This video requires an account or age verification."
        elif "region" in message or "country" in message:
            summary = "This video is unavailable in your region."
        elif "format" in message:
            summary = "No playable video formats were found."
        else:
            summary = "Could not extract this video. Check the URL and network connection."
        raise StreamError(summary) from error

    if not isinstance(info, dict):
        raise StreamError("yt-dlp returned no video information.")
    video, audio = choose_formats(info, max_height=max_height)
    try:
        width = int(video.get("width") or info.get("width") or 640)
        height = int(video.get("height") or info.get("height") or 360)
    except (TypeError, ValueError):
        width, height = 640, 360
    try:
        fps = float(video.get("fps") or info.get("fps") or 30)
    except (TypeError, ValueError):
        fps = 30.0
    try:
        duration = float(info["duration"]) if info.get("duration") is not None else None
    except (TypeError, ValueError):
        duration = None
    return StreamInfo(
        title=str(info.get("title") or "YouTube video"),
        duration=duration,
        fps=max(1.0, fps),
        width=width,
        height=height,
        video_url=str(video["url"]),
        audio_url=str(audio["url"]),
    )