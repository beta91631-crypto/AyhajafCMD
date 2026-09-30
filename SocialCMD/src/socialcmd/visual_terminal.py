"""True-color image rendering primitives for the terminal browser."""

from __future__ import annotations

import base64
from io import BytesIO
import math

from PIL import Image

MAX_SCREENSHOT_BYTES = 16 * 1024 * 1024


def prepare_terminal_pixels(
    screenshot: str,
    elements: list[dict],
    terminal_width: int,
    terminal_rows: int,
    viewport_width: int,
    viewport_height: int,
) -> tuple[bytes, int, int, list[tuple[int, int, int]]]:
    if not 1 <= terminal_width <= 240 or terminal_rows < 4:
        raise ValueError("Terminal dimensions are outside the supported range.")
    if viewport_width < 1 or viewport_height < 1:
        raise ValueError("Browser viewport dimensions must be positive.")
    if not isinstance(screenshot, str) or len(screenshot) > MAX_SCREENSHOT_BYTES * 2:
        raise ValueError("Browser screenshot exceeds the encoded size limit.")
    try:
        image_bytes = base64.b64decode(screenshot, validate=True)
        with Image.open(BytesIO(image_bytes)) as source:
            if source.width > 8192 or source.height > 8192 or source.width * source.height > 64_000_000:
                raise ValueError("Browser screenshot dimensions exceed the size limit.")
            image = source.convert("RGB")
    except (ValueError, OSError) as error:
        raise ValueError("Browser returned an invalid screenshot.") from error
    if len(image_bytes) > MAX_SCREENSHOT_BYTES:
        raise ValueError("Browser screenshot exceeds the decoded size limit.")

    source_width, source_height = image.size
    width = terminal_width
    height = (terminal_rows - 3) * 2
    scale = min(width / source_width, height / source_height)
    image_width = max(1, int(source_width * scale))
    image_height = max(1, int(source_height * scale))
    image = image.resize((image_width, image_height), Image.Resampling.NEAREST)
    canvas_height = max(2, height - height % 2)
    canvas = Image.new("RGB", (width, canvas_height), (0, 0, 0))
    left = (width - image_width) // 2
    top = (canvas_height - image_height) // 2
    canvas.paste(image, (left, top))

    markers: list[tuple[int, int, int]] = []
    occupied: dict[int, list[tuple[int, int]]] = {}
    for item in elements:
        try:
            number = int(item["number"])
            x = float(item["x"])
            y = float(item["y"])
            item_width = float(item["width"])
            item_height = float(item["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (x, y, item_width, item_height)):
            continue
        factor_x = image_width / viewport_width
        factor_y = image_height / viewport_height
        x0 = max(left, min(width - 1, left + int(x * factor_x)))
        y0 = max(top, min(canvas_height - 1, top + int(y * factor_y)))
        x1 = max(x0, min(left + image_width - 1, left + int((x + item_width) * factor_x)))
        y1 = max(y0, min(top + image_height - 1, top + int((y + item_height) * factor_y)))
        label_width = len(str(number)) + 2
        first_column = min(x0, max(0, width - label_width))
        last_column = max(first_column, min(x1 - label_width + 1, width - label_width))
        first_row = min(y0 // 2, canvas_height // 2 - 1)
        last_row = min(y1 // 2, canvas_height // 2 - 1)
        candidate_rows = sorted(
            range(first_row, last_row + 1),
            key=lambda candidate: abs(candidate - first_row),
        )
        placed = None
        for row in candidate_rows:
            ranges = occupied.setdefault(row, [])
            for column in range(first_column, last_column + 1):
                if all(
                    column + label_width <= start or column >= end
                    for start, end in ranges
                ):
                    placed = (number, row, column)
                    ranges.append((column, column + label_width))
                    break
            if placed is not None:
                break
        if placed is not None:
            markers.append(placed)
    return canvas.tobytes(), width, canvas_height, markers


def render_rgb_frame(pixels: bytes, width: int, height: int) -> str:
    if width < 1 or height < 1 or len(pixels) != width * height * 3:
        raise ValueError("RGB frame dimensions do not match its pixel data.")

    output: list[str] = []
    for row in range(0, height, 2):
        foreground = None
        background = None
        for column in range(width):
            top_offset = (row * width + column) * 3
            top = tuple(pixels[top_offset:top_offset + 3])
            if row + 1 < height:
                bottom_offset = ((row + 1) * width + column) * 3
                bottom = tuple(pixels[bottom_offset:bottom_offset + 3])
            else:
                bottom = (0, 0, 0)

            if top != foreground:
                output.append(f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m")
                foreground = top
            if bottom != background:
                output.append(f"\x1b[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m")
                background = bottom
            output.append("▀")
        output.append("\x1b[0m")
        if row + 2 < height:
            output.append("\r\n")
    return "".join(output)


def render_control_markers(
    markers: list[tuple[int, int, int]], width: int, height: int
) -> str:
    if width < 1 or height < 1:
        raise ValueError("Marker bounds must be positive.")
    output: list[str] = []
    for number, row, column in markers:
        label = f" {number} "
        if number < 1 or row < 0 or row >= height or column < 0:
            continue
        label = label[:max(0, width - column)]
        if not label:
            continue
        output.append(
            f"\x1b[{row + 1};{column + 1}H"
            f"\x1b[48;2;0;170;220m\x1b[38;2;0;0;0m{label}\x1b[0m"
        )
    return "".join(output)