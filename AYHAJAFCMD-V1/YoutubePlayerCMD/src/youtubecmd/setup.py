"""Checks external tools needed by the playback pipeline."""

from __future__ import annotations

import shutil
import sys


def check_runtime() -> list[str]:
    problems = []
    if sys.version_info < (3, 10):
        problems.append("Python 3.10 or newer is required.")
    if not shutil.which("ffmpeg"):
        problems.append(
            "FFmpeg was not found in PATH. Install FFmpeg and reopen the terminal."
        )
    if not shutil.which("ffplay"):
        problems.append(
            "ffplay was not found in PATH. Install an FFmpeg build that includes ffplay."
        )
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        problems.append("yt-dlp is missing. Run YouTubeCMD.bat to install dependencies.")
    return problems


def enable_ansi() -> bool:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetConsoleMode.restype = wintypes.BOOL
        kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.SetConsoleMode.restype = wintypes.BOOL
        handle = kernel32.GetStdHandle(-11)
        mode = wintypes.DWORD()
        if not handle or not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    return sys.stdout.isatty()