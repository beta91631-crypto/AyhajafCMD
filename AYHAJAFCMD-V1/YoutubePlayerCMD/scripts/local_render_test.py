"""Render a generated color gradient without network or media tools."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youtubecmd.renderer import fit_dimensions, render_frame


def make_gradient(width: int, height: int) -> bytes:
    frame = bytearray()
    for y in range(height):
        for x in range(width):
            frame.extend((x * 255 // max(1, width - 1), y * 255 // max(1, height - 1), 128))
    return bytes(frame)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("HALF_BLOCK", "ASCII", "ANSI_COLOR"), default="HALF_BLOCK")
    args = parser.parse_args()

    terminal = shutil.get_terminal_size(fallback=(80, 24))
    width, height = fit_dimensions(
        64,
        32,
        terminal.columns,
        max(1, (terminal.lines - 1) * (1 if args.mode == "ASCII" else 2)),
        cell_aspect=0.5 if args.mode == "ASCII" else 1.0,
    )
    source = make_gradient(width, height)
    sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H")
    try:
        sys.stdout.write(render_frame(source, width, height, args.mode) + "\n")
        sys.stdout.write(f"Offline renderer check: {args.mode} {width}x{height}\n")
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())