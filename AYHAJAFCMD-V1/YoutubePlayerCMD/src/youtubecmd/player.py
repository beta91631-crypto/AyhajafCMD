"""YouTube terminal player powered by yt-dlp, FFmpeg, and ffplay."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from youtubecmd.config import Config, load_config, save_config
from youtubecmd.input_controller import InputController
from youtubecmd.renderer import RENDERER_MODES, fit_dimensions, render_frame, render_half_block
from youtubecmd.setup import check_runtime, enable_ansi
from youtubecmd.streams import StreamError, StreamInfo, extract_streams, validate_youtube_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.json"
MAX_SOURCE_HEIGHT = 1080
MAX_RENDER_FPS = 30.0
SEEK_SECONDS = 5.0
RESIZE_DEBOUNCE_SECONDS = 0.15
STATUS_UPDATE_INTERVAL = 0.25


def _terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return max(1, size.columns), max(2, size.lines)


def _render_dimensions(
    stream: StreamInfo, config: Config, columns: int, lines: int
) -> tuple[int, int]:
    scale = min(1.0, max(0.5, config.quality_level))
    max_width = max(1, int(columns * scale))
    rows_for_video = max(1, lines - 1)
    if config.renderer_mode == "ASCII":
        max_height = max(1, int(rows_for_video * scale))
        cell_aspect = 0.5
    else:
        max_height = max(1, int(rows_for_video * 2 * scale))
        cell_aspect = 1.0
    return fit_dimensions(
        stream.width,
        stream.height,
        max_width,
        max_height,
        cell_aspect=cell_aspect,
    )


def _start_audio(stream: StreamInfo, position: float, volume: int) -> subprocess.Popen:
    command = [
        "ffplay",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nodisp",
        "-autoexit",
        "-volume",
        str(volume),
        "-ss",
        f"{max(0.0, position):.3f}",
        "-i",
        stream.audio_url,
    ]
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _start_video(
    stream: StreamInfo,
    position: float,
    width: int,
    height: int,
    renderer_mode: str,
    fps: float,
) -> subprocess.Popen:
    fps_filter = f"fps={min(MAX_RENDER_FPS, fps):.3f}"
    if renderer_mode != "ASCII":
        filter_value = (
            f"{fps_filter},scale={width}:{height}:force_original_aspect_ratio=decrease:flags=fast_bilinear,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        )
    else:
        filter_value = f"{fps_filter},scale={width}:{height}:flags=fast_bilinear,setsar=1"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, position):.3f}",
        "-i",
        stream.video_url,
        "-an",
        "-vf",
        filter_value,
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _read_frame(process: subprocess.Popen, byte_count: int) -> bytes | None:
    if process.stdout is None:
        return None
    frame = bytearray()
    while len(frame) < byte_count:
        chunk = process.stdout.read(byte_count - len(frame))
        if not chunk:
            return None
        frame.extend(chunk)
    return bytes(frame)


def _format_time(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    total_seconds = max(0, int(seconds))
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


def _status_line(
    stream: StreamInfo,
    config: Config,
    position: float,
    paused: bool,
    width: int,
    height: int,
    columns: int,
) -> str:
    duration = _format_time(stream.duration)
    state = "PAUSED" if paused else "PLAYING"
    details = (
        f" {state}  {_format_time(position)}/{duration}  Vol {config.volume}%"
        f"  {config.renderer_mode}  {width}x{height}"
    )
    return details[:columns].ljust(columns)


def _write_status(
    stream: StreamInfo,
    config: Config,
    position: float,
    paused: bool,
    width: int,
    height: int,
) -> None:
    columns, lines = _terminal_size()
    status = _status_line(
        stream, config, position, paused, width, height, columns
    )
    sys.stdout.write(f"\x1b[{lines};1H\x1b[2K{status}")
    sys.stdout.flush()


def _show_fullscreen(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetConsoleWindow.restype = wintypes.HWND
        window = kernel32.GetConsoleWindow()
        if window:
            user32 = ctypes.windll.user32
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindow(window, 3 if enabled else 9)
    except (AttributeError, OSError):
        pass


def _cleanup_terminal() -> None:
    sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H\r\n")
    sys.stdout.flush()


def play(stream: StreamInfo, config: Config) -> None:
    paused = False
    fullscreen = False
    position = 0.0
    playback_started_at = 0.0
    audio_process = None
    video_process = None
    dimensions = (0, 0)
    resize_candidate = None
    resize_observed_at = 0.0
    columns, lines = _terminal_size()
    if lines < 8 or columns < 40:
        print("Terminal is small; video will use the available area.")

    sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H")
    sys.stdout.flush()

    def stop_processes() -> None:
        nonlocal audio_process, video_process
        _stop_process(video_process)
        _stop_process(audio_process)
        video_process = None
        audio_process = None

    def launch(at: float) -> None:
        nonlocal audio_process, video_process, dimensions, columns, lines
        nonlocal playback_started_at
        columns, lines = _terminal_size()
        dimensions = _render_dimensions(stream, config, columns, lines)
        audio_process = _start_audio(stream, at, config.volume)
        video_process = _start_video(
            stream, at, *dimensions, config.renderer_mode, stream.fps
        )
        playback_started_at = time.monotonic()

    try:
        with InputController() as controls:
            launch(position)
            frame_interval = 1.0 / min(MAX_RENDER_FPS, stream.fps)
            next_frame_at = time.monotonic()
            next_status_at = next_frame_at
            running = True
            while running:
                key = controls.poll()
                if key == "quit":
                    break
                if not paused and (
                    video_process is None
                    or video_process.poll() is not None
                    or audio_process is None
                    or audio_process.poll() is not None
                ):
                    if video_process is not None and video_process.returncode not in (None, 0):
                        print("FFmpeg could not decode this video stream.")
                    elif audio_process is not None and audio_process.returncode not in (None, 0):
                        print("Audio playback stopped unexpectedly.")
                    break

                if key == "pause":
                    if paused:
                        paused = False
                        launch(position)
                        next_frame_at = time.monotonic()
                        _write_status(stream, config, position, False, *dimensions)
                    else:
                        position += max(0.0, time.monotonic() - playback_started_at)
                        stop_processes()
                        paused = True
                        _write_status(stream, config, position, True, *dimensions)
                    continue

                current_position = position
                if not paused:
                    current_position += max(0.0, time.monotonic() - playback_started_at)

                restart = False
                if key == "left":
                    position = max(0.0, current_position - SEEK_SECONDS)
                    restart = True
                elif key == "right":
                    position = current_position + SEEK_SECONDS
                    if stream.duration is not None:
                        position = min(position, stream.duration)
                    restart = True
                elif key == "r":
                    position = 0.0
                    restart = True
                elif key in ("+", "-"):
                    change = 0.1 if key == "+" else -0.1
                    config.quality_level = round(
                        min(1.0, max(0.5, config.quality_level + change)), 2
                    )
                    position = current_position
                    restart = True
                elif key == "m":
                    mode_index = RENDERER_MODES.index(config.renderer_mode)
                    config.renderer_mode = RENDERER_MODES[(mode_index + 1) % len(RENDERER_MODES)]
                    position = current_position
                    restart = True
                elif key in ("up", "down"):
                    config.volume = min(
                        100, max(0, config.volume + (5 if key == "up" else -5))
                    )
                    position = current_position
                    restart = True
                elif key == "f":
                    fullscreen = not fullscreen
                    _show_fullscreen(fullscreen)
                if restart:
                    stop_processes()
                    if stream.duration is not None and position >= stream.duration:
                        break
                    if not paused:
                        launch(position)
                        next_frame_at = time.monotonic()
                    save_config(CONFIG_PATH, config)
                    _write_status(stream, config, position, paused, *dimensions)
                    continue

                if paused:
                    time.sleep(0.05)
                    continue

                current_columns, current_lines = _terminal_size()
                current_dimensions = _render_dimensions(
                    stream, config, current_columns, current_lines
                )
                if current_dimensions != dimensions:
                    now = time.monotonic()
                    if current_dimensions != resize_candidate:
                        resize_candidate = current_dimensions
                        resize_observed_at = now
                    elif now - resize_observed_at >= RESIZE_DEBOUNCE_SECONDS:
                        position = current_position
                        _stop_process(video_process)
                        columns, lines = current_columns, current_lines
                        dimensions = current_dimensions
                        video_process = _start_video(
                            stream, position, *dimensions,
                            config.renderer_mode, stream.fps
                        )
                        playback_started_at = time.monotonic()
                        resize_candidate = None
                        next_frame_at = time.monotonic()
                        sys.stdout.write("\x1b[2J\x1b[H")
                        sys.stdout.flush()
                        _write_status(stream, config, position, False, *dimensions)
                        continue
                else:
                    resize_candidate = None

                frame = _read_frame(video_process, dimensions[0] * dimensions[1] * 3)
                if frame is None:
                    if video_process.poll() not in (None, 0):
                        print("FFmpeg could not decode this video stream.")
                    break
                now = time.monotonic()
                if now > next_frame_at + frame_interval:
                    next_frame_at += frame_interval
                    continue
                if now < next_frame_at:
                    key = None
                    while now < next_frame_at:
                        key = controls.poll()
                        if key is not None:
                            break
                        time.sleep(min(0.01, next_frame_at - now))
                        now = time.monotonic()
                    if key is not None:
                        continue

                if config.renderer_mode == "HALF_BLOCK" and config.color_mode == "color":
                    rendered = render_half_block(*((frame,) + dimensions), color=True)
                else:
                    rendered = render_frame(frame, *dimensions, config.renderer_mode)
                sys.stdout.write("\x1b[H" + rendered.replace("\n", "\x1b[K\r\n"))
                sys.stdout.flush()
                if now >= next_status_at:
                    _write_status(stream, config, current_position, paused, *dimensions)
                    next_status_at = now + STATUS_UPDATE_INTERVAL
                next_frame_at += frame_interval
    finally:
        stop_processes()
        _show_fullscreen(False)
        _cleanup_terminal()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch YouTube in your terminal")
    parser.add_argument("url", nargs="?", help="YouTube video URL (prompted if omitted)")
    args = parser.parse_args(argv)

    problems = check_runtime()
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print("See README.md for installation instructions.", file=sys.stderr)
        return 1
    try:
        ansi_available = enable_ansi()
    except (AttributeError, OSError):
        ansi_available = False
    if not ansi_available:
        print(
            "ANSI terminal support could not be enabled. Use Windows Terminal or another ANSI-compatible terminal.",
            file=sys.stderr,
        )
        return 1

    config = load_config(CONFIG_PATH)
    try:
        url = args.url or input("YouTube URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nPlayback cancelled.")
        return 0
    if not validate_youtube_url(url):
        print("Invalid YouTube URL.", file=sys.stderr)
        return 2

    try:
        stream = extract_streams(url, max_height=MAX_SOURCE_HEIGHT)
        print(f"Playing: {stream.title}")
        play(stream, config)
    except StreamError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPlayback interrupted.")
    except OSError as error:
        print(f"Could not start playback tools: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())