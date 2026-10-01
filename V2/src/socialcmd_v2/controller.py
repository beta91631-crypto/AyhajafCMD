"""Keyboard controls for live terminal-render settings."""

from __future__ import annotations

from socialcmd_v2.rendering import RenderSettings


SETTING_CONTROLS = {
    "[": "pixel-",
    "]": "pixel+",
    "-": "colors-",
    "+": "colors+",
    "z": "zoom+",
    "x": "zoom-",
    "d": "dither",
    "m": "mode",
}


def adjust_setting(settings: RenderSettings, control: str) -> None:
    if control == "pixel+":
        settings.pixel_size = min(8, settings.pixel_size + 1)
    elif control == "pixel-":
        settings.pixel_size = max(1, settings.pixel_size - 1)
    elif control == "colors+":
        settings.colors = min(256, settings.colors + 8)
    elif control == "colors-":
        settings.colors = max(2, settings.colors - 8)
    elif control == "zoom+":
        settings.zoom = min(2.0, round(settings.zoom + 0.1, 1))
    elif control == "zoom-":
        settings.zoom = max(0.5, round(settings.zoom - 0.1, 1))
    elif control == "dither":
        settings.dither = "none" if settings.dither == "floyd" else "floyd"
    elif control == "mode":
        settings.mode = "sixel" if settings.mode == "halfblock" else "halfblock"
    else:
        raise ValueError(f"Unknown settings control: {control}")
    settings.validate()


def settings_panel(settings: RenderSettings) -> str:
    return (
        "RENDER SETTINGS\n"
        f"Pixel block: {settings.pixel_size} (1 is finest) | Palette: {settings.colors} colors\n"
        f"Dither: {settings.dither} | Zoom: {settings.zoom:.1f}x | Mode: {settings.mode}\n"
        "Controller: [ ] pixel | - + colors | z/x zoom | d dither | m render mode\n"
        "Commands: pixel N | colors N | zoom N | dither none|floyd | mode halfblock|sixel"
    )