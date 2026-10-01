"""Extract playable YouTube stream metadata for the native player."""

from __future__ import annotations

import argparse
import json
import sys

from youtubecmd.streams import StreamError, extract_streams


def stream_payload(url: str, max_height: int | None = 720) -> dict[str, object]:
    stream = extract_streams(url, max_height=max_height)
    return {
        "video_url": stream.video_url,
        "audio_url": stream.audio_url,
        "title": stream.title,
        "duration": stream.duration,
        "fps": stream.fps,
        "width": stream.width,
        "height": stream.height,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract YouTube streams for renderer.exe")
    parser.add_argument("url", nargs="?", help="YouTube URL (prompted if omitted)")
    parser.add_argument(
        "--video-quality",
        choices=("360", "480", "720", "1080", "best"),
        default="720",
        help="maximum source video resolution (default: 720p)",
    )
    args = parser.parse_args(argv)
    try:
        if args.url:
            url = args.url
        else:
            print("YouTube URL: ", end="", file=sys.stderr, flush=True)
            url = input().strip()
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