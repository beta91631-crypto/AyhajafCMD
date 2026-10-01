"""Pixel-art scaling and true-color half-block terminal rendering."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import shutil
import subprocess

from PIL import Image


@dataclass
class RenderSettings:
    pixel_size: int = 1
    colors: int = 256
    dither: str = "floyd"
    zoom: float = 1.0
    mode: str = "halfblock"

    def validate(self) -> None:
        if not 1 <= self.pixel_size <= 8:
            raise ValueError("Pixel size must be between 1 and 8.")
        if not 2 <= self.colors <= 256:
            raise ValueError("Palette size must be between 2 and 256.")
        if self.dither not in {"none", "floyd"}:
            raise ValueError("Dither must be none or floyd.")
        if not 0.5 <= self.zoom <= 2.0:
            raise ValueError("Zoom must be between 0.5 and 2.0.")
        if self.mode not in {"halfblock", "sixel"}:
            raise ValueError("Render mode must be halfblock or sixel.")


def terminal_dimensions(columns: int, rows: int) -> tuple[int, int]:
    return min(320, max(1, columns)), min(120, max(4, rows))


def prepare_image(
    screenshot: bytes,
    columns: int,
    rows: int,
    settings: RenderSettings,
) -> Image.Image:
    settings.validate()
    if not 1 <= columns <= 4096 or rows < 4:
        raise ValueError("Terminal dimensions are outside the supported range.")
    with Image.open(BytesIO(screenshot)) as source:
        image = source.convert("RGB")
    height = max(2, (rows - 3) * 2)
    frame_size = (columns, max(2, height - height % 2))
    scale = min(frame_size[0] / image.width, frame_size[1] / image.height)
    content_size = (max(1, int(image.width * scale)), max(2, int(image.height * scale)))
    content_size = (content_size[0], content_size[1] - content_size[1] % 2)
    image = image.resize(content_size, Image.Resampling.LANCZOS)

    zoomed_size = (max(1, int(content_size[0] * settings.zoom)), max(2, int(content_size[1] * settings.zoom)))
    zoomed_size = (zoomed_size[0], zoomed_size[1] - zoomed_size[1] % 2)
    image = image.resize(zoomed_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", frame_size, (0, 0, 0))
    if image.width > columns or image.height > frame_size[1]:
        left = max(0, (image.width - columns) // 2)
        top = max(0, (image.height - frame_size[1]) // 2)
        image = image.crop((left, top, left + min(columns, image.width), top + min(frame_size[1], image.height)))
        canvas.paste(image, (0, 0))
    else:
        canvas.paste(image, ((columns - image.width) // 2, (frame_size[1] - image.height) // 2))
    image = canvas

    if settings.pixel_size > 1:
        reduced_size = (max(1, columns // settings.pixel_size), max(2, frame_size[1] // settings.pixel_size))
        reduced_size = (reduced_size[0], reduced_size[1] - reduced_size[1] % 2)
        image = image.resize(reduced_size, Image.Resampling.BILINEAR)
        image = image.resize(frame_size, Image.Resampling.NEAREST)

    dither = Image.Dither.FLOYDSTEINBERG if settings.dither == "floyd" else Image.Dither.NONE
    return image.quantize(colors=settings.colors, dither=dither).convert("RGB")


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
    if settings.mode == "halfblock":
        return render_halfblocks(prepare_image(screenshot, columns, rows, settings))
    chafa = shutil.which("chafa")
    if chafa is None:
        raise RuntimeError("Sixel mode needs Chafa installed and available on PATH; use mode halfblock otherwise.")
    image = prepare_image(screenshot, min(4096, columns * 8), max(4, (rows - 3) * 16), settings)
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    color_mode = "2" if settings.colors <= 2 else "16" if settings.colors <= 16 else "256" if settings.colors < 256 else "full"
    dither = "diffusion" if settings.dither == "floyd" else "none"
    result = subprocess.run(
        [chafa, "-f", "sixels", "-s", f"{columns}x{max(1, rows - 3)}", "-c", color_mode,
         "--dither", dither, "-"],
        input=encoded.getvalue(), capture_output=True, check=True, timeout=15,
    )
    return result.stdout.decode("utf-8", errors="replace")
