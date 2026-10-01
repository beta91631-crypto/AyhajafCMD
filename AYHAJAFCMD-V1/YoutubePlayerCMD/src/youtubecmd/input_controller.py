"""Nonblocking key input for Windows consoles and POSIX terminals."""

from __future__ import annotations

import os
import sys


class InputController:
    def __init__(self) -> None:
        self._old_terminal = None

    def __enter__(self):
        if os.name != "nt" and sys.stdin.isatty():
            import termios
            import tty

            self._old_terminal = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, *_exc) -> None:
        if self._old_terminal is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_terminal)

    def poll(self) -> str | None:
        if os.name == "nt":
            return self._poll_windows()
        return self._poll_posix()

    @staticmethod
    def _poll_windows() -> str | None:
        import msvcrt

        if not msvcrt.kbhit():
            return None
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            return {
                "H": "up",
                "P": "down",
                "K": "left",
                "M": "right",
            }.get(msvcrt.getwch())
        return _normalize_key(key)

    @staticmethod
    def _poll_posix() -> str | None:
        import select

        if not sys.stdin.isatty() or not select.select([sys.stdin], [], [], 0)[0]:
            return None
        key = sys.stdin.read(1)
        if key != "\x1b":
            return _normalize_key(key)
        if not select.select([sys.stdin], [], [], 0)[0]:
            return "quit"
        if sys.stdin.read(1) != "[" or not select.select([sys.stdin], [], [], 0)[0]:
            return None
        return {"A": "up", "B": "down", "C": "right", "D": "left"}.get(
            sys.stdin.read(1)
        )


def _normalize_key(key: str) -> str | None:
    normalized = key.lower()
    if normalized in ("q", "\x1b"):
        return "quit"
    if normalized == " ":
        return "pause"
    if normalized in {"r", "f", "+", "-", "m"}:
        return normalized
    return None