"""Small, dependency-free RGB frame renderers for terminal cells."""

from __future__ import annotations

try:
    from ._native_renderer import (
        render_ascii as _native_render_ascii,
        render_half_block as _native_render_half_block,
    )
except ImportError:
    _native_render_ascii = None
    _native_render_half_block = None

ASCII_RAMP = "@%#*+=-:. "
RENDERER_MODES = ("HALF_BLOCK", "ASCII", "ANSI_COLOR")


def fit_dimensions(
    source_width: int,
    source_height: int,
    max_width: int,
    max_height: int,
    *,
    cell_aspect: float = 1.0,
) -> tuple[int, int]:
    """Fit a source into a cell grid, accounting for the terminal cell shape."""
    if min(source_width, source_height, max_width, max_height) < 1:
        raise ValueError("Image and target dimensions must be positive")
    if cell_aspect <= 0:
        raise ValueError("Cell aspect ratio must be positive")

    target_ratio = (source_width / source_height) / cell_aspect
    if max_width / max_height > target_ratio:
        height = max_height
        width = max(1, round(height * target_ratio))
    else:
        width = max_width
        height = max(1, round(width / target_ratio))
    return min(width, max_width), min(height, max_height)


def _check_frame(frame: bytes, width: int, height: int) -> None:
    if width < 1 or height < 1:
        raise ValueError("Frame dimensions must be positive")
    if len(frame) != width * height * 3:
        raise ValueError("RGB frame byte count does not match its dimensions")


def luminance(red: int, green: int, blue: int) -> int:
    return (299 * red + 587 * green + 114 * blue) // 1000


def render_ascii(frame: bytes, width: int, height: int) -> str:
    _check_frame(frame, width, height)
    if _native_render_ascii is not None:
        return _native_render_ascii(frame, width, height)
    ramp_max = len(ASCII_RAMP) - 1
    lines = []
    for y in range(height):
        line = []
        for x in range(width):
            offset = (y * width + x) * 3
            value = luminance(*frame[offset : offset + 3])
            line.append(ASCII_RAMP[value * ramp_max // 255])
        lines.append("".join(line))
    return "\n".join(lines)


def render_half_block(
    frame: bytes,
    width: int,
    height: int,
    *,
    color: bool = False,
) -> str:
    _check_frame(frame, width, height)
    if _native_render_half_block is not None:
        return _native_render_half_block(frame, width, height, color)
    return _render_half_block_python(frame, width, height, color=color)


def _render_half_block_python(
    frame: bytes, width: int, height: int, *, color: bool = False
) -> str:
    lines = []
    for y in range(0, height, 2):
        line = []
        for x in range(width):
            top_offset = (y * width + x) * 3
            top = tuple(frame[top_offset : top_offset + 3])
            if y + 1 < height:
                bottom_offset = ((y + 1) * width + x) * 3
                bottom = tuple(frame[bottom_offset : bottom_offset + 3])
            else:
                bottom = (0, 0, 0)

            if color:
                line.append(
                    f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m"
                    f"\x1b[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m▀"
                )
            else:
                top_gray = luminance(*top)
                bottom_gray = luminance(*bottom)
                line.append(
                    f"\x1b[38;2;{top_gray};{top_gray};{top_gray}m"
                    f"\x1b[48;2;{bottom_gray};{bottom_gray};{bottom_gray}m▀"
                )
        lines.append("".join(line) + "\x1b[0m")
    return "\n".join(lines)


def render_frame(frame: bytes, width: int, height: int, mode: str) -> str:
    normalized_mode = mode.upper()
    if normalized_mode == "ASCII":
        return render_ascii(frame, width, height)
    if normalized_mode == "HALF_BLOCK":
        return render_half_block(frame, width, height)
    if normalized_mode == "ANSI_COLOR":
        return render_half_block(frame, width, height, color=True)
    raise ValueError(f"Unsupported renderer mode: {mode}")