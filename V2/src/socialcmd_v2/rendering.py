"""Pixel-art scaling and true-color half-block terminal rendering."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image


@dataclass
class RenderSettings:
    pixel_size: int = 1
    colors: int = 256
    dither: str = "floyd"

    def validate(self) -> None:
        if not 1 <= self.pixel_size <= 8:
            raise ValueError("Pixel size must be between 1 and 8.")
        if not 2 <= self.colors <= 256:
            raise ValueError("Palette size must be between 2 and 256.")
        if self.dither not in {"none", "floyd"}:
            raise ValueError("Dither must be none or floyd.")


def terminal_dimensions(columns: int, rows: int) -> tuple[int, int]:
    return min(320, max(1, columns)), min(120, max(4, rows))


def prepare_image(
    screenshot: bytes,
    columns: int,
    rows: int,
    settings: RenderSettings,
) -> Image.Image:
    settings.validate()
    if not 1 <= columns <= 320 or rows < 4:
        raise ValueError("Terminal dimensions are outside the supported range.")
    with Image.open(BytesIO(screenshot)) as source:
        image = source.convert("RGB")
    height = max(2, (rows - 3) * 2)
    scale = min(columns / image.width, height / image.height)
    image_width = max(1, int(image.width * scale))
    image_height = max(2, int(image.height * scale))
    image_height -= image_height % 2
    image = image.resize((image_width, image_height), Image.Resampling.LANCZOS)

    pixel_size = settings.pixel_size
    if pixel_size > 1:
        reduced = (max(1, image_width // pixel_size), max(2, image_height // pixel_size))
        reduced = (reduced[0], reduced[1] - reduced[1] % 2)
        image = image.resize(reduced, Image.Resampling.BILINEAR)
        image = image.resize((image_width, image_height), Image.Resampling.NEAREST)

    dither = Image.Dither.FLOYDSTEINBERG if settings.dither == "floyd" else Image.Dither.NONE
    image = image.quantize(colors=settings.colors, dither=dither).convert("RGB")
    canvas = Image.new("RGB", (columns, max(2, height - height % 2)), (0, 0, 0))
    canvas.paste(image, ((columns - image_width) // 2, (canvas.height - image_height) // 2))
    return canvas


def render_halfblocks(image: Image.Image) -> str:
    image = image.convert("RGB")
    width, height = image.size
    if width < 1 or height < 2:
        raise ValueError("Image is too small to render.")
    if height % 2:
        image = image.crop((0, 0, width, height - 1))
        height -= 1

    pixels = image.load()
    output: list[str] = []
    for row in range(0, height, 2):
        foreground = None
        background = None
        for column in range(width):
            top = pixels[column, row]
            bottom = pixels[column, row + 1]
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


def render_screenshot(
    screenshot: bytes,
    columns: int,
    rows: int,
    settings: RenderSettings,
) -> str:
    image = prepare_image(screenshot, columns, rows, settings)
    return render_halfblocks(image)
