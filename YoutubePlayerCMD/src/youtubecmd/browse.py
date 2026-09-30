"""Search YouTube from the terminal and select a video for playback."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

from youtubecmd.extract import stream_payload
from youtubecmd.streams import StreamError, validate_youtube_url


@dataclass(frozen=True)
class SearchResult:
    title: str
    uploader: str
    duration: int | None
    url: str


def search_videos(query: str, limit: int = 10) -> list[SearchResult]:
    if not query.strip():
        raise StreamError("Enter a search query or YouTube URL.")
    try:
        import yt_dlp

        options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "playlistend": limit,
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            result = downloader.extract_info(
                f"ytsearch{limit}:{query.strip()}", download=False
            )
    except ImportError as error:
        raise StreamError("yt-dlp is not installed. Run YouTubeCMD.bat to install it.") from error
    except Exception as error:
        raise StreamError("Could not search YouTube. Check the query and network connection.") from error

    entries = result.get("entries", []) if isinstance(result, dict) else []
    videos = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or "")
        url = str(entry.get("webpage_url") or entry.get("url") or "")
        if not validate_youtube_url(url):
            url = f"https://www.youtube.com/watch?v={video_id}"
        if not validate_youtube_url(url):
            continue
        try:
            duration = int(entry["duration"]) if entry.get("duration") is not None else None
        except (TypeError, ValueError):
            duration = None
        videos.append(SearchResult(
            title=str(entry.get("title") or "Untitled video"),
            uploader=str(entry.get("channel") or entry.get("uploader") or "YouTube"),
            duration=duration,
            url=url,
        ))
    if not videos:
        raise StreamError("No videos found for that search.")
    return videos[:limit]


def _display_text(value: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", value)


def _duration_text(seconds: int | None) -> str:
    if seconds is None:
        return "--:--"
    minutes, remaining = divmod(max(0, seconds), 60)
    return f"{minutes}:{remaining:02d}"


def _prompt_input(prompt: str) -> str:
    print(prompt, end="", file=sys.stderr, flush=True)
    return input()


def _prompt_video_quality() -> int | None:
    quality_limits = {"1": 360, "2": 480, "3": 720, "4": 1080, "5": None}
    print("\nSource quality", file=sys.stderr)
    print("  1. 360p   2. 480p   3. 720p   4. 1080p   5. Best available", file=sys.stderr)
    while True:
        choice = _prompt_input("Choose quality [3]: ").strip() or "3"
        if choice in quality_limits:
            return quality_limits[choice]
        print("Enter a number from 1 to 5.", file=sys.stderr)


def select_video(source: str) -> str | None:
    source = source.strip()
    if validate_youtube_url(source):
        return source
    if source.lower().startswith(("http://", "https://")):
        raise StreamError("Invalid YouTube URL.")

    videos = search_videos(source)
    print("\nYouTube search results", file=sys.stderr)
    for index, video in enumerate(videos, start=1):
        print(
            f"{index:>2}. {_display_text(video.title)}  "
            f"{_duration_text(video.duration)}  {_display_text(video.uploader)}",
            file=sys.stderr,
        )
    print("", file=sys.stderr)
    choice = _prompt_input(f"Choose a video (1-{len(videos)}, q to cancel): ").strip().lower()
    if choice in {"q", "quit"}:
        return None
    try:
        selected = int(choice)
    except ValueError as error:
        raise StreamError("Enter one of the displayed result numbers.") from error
    if selected < 1 or selected > len(videos):
        raise StreamError("That result number is out of range.")
    return videos[selected - 1].url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search YouTube or play a video URL")
    parser.add_argument("source", nargs="?", help="search terms or YouTube video URL")
    parser.add_argument(
        "--video-quality",
        choices=("360", "480", "720", "1080", "best"),
        help="maximum source video resolution (prompted if omitted)",
    )
    args = parser.parse_args(argv)
    try:
        if args.source:
            source = args.source
        else:
            print("Search YouTube or paste a video URL.", file=sys.stderr)
            source = _prompt_input("> ").strip()
        url = select_video(source)
        if url is None:
            print("Playback cancelled.", file=sys.stderr)
            return 0
        if args.video_quality is None:
            max_height = _prompt_video_quality()
        else:
            max_height = None if args.video_quality == "best" else int(args.video_quality)
        payload = stream_payload(url, max_height=max_height)
    except (EOFError, KeyboardInterrupt):
        print("Playback cancelled.", file=sys.stderr)
        return 0
    except StreamError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())