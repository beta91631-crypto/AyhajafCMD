"""Persistent user preferences."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CONFIG = {
    "renderer_mode": "HALF_BLOCK",
    "quality_level": 1.0,
    "volume": 80,
    "color_mode": "color",
}


@dataclass
class Config:
    renderer_mode: str = "HALF_BLOCK"
    quality_level: float = 1.0
    volume: int = 80
    color_mode: str = "color"


def load_config(path: str | Path) -> Config:
    config_path = Path(path)
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Config()
    except (OSError, json.JSONDecodeError):
        return Config()

    if not isinstance(values, dict):
        return Config()

    mode = str(values.get("renderer_mode", "HALF_BLOCK")).upper()
    if mode not in {"HALF_BLOCK", "ASCII", "ANSI_COLOR"}:
        mode = "HALF_BLOCK"

    try:
        quality = float(values.get("quality_level", 1.0))
    except (TypeError, ValueError):
        quality = 1.0
    if not 0.5 <= quality <= 1.0:
        quality = min(1.0, max(0.5, quality))

    try:
        volume = int(values.get("volume", 80))
    except (TypeError, ValueError):
        volume = 80

    color_mode = str(values.get("color_mode", "color")).lower()
    if color_mode not in {"grayscale", "color"}:
        color_mode = "grayscale"

    return Config(
        renderer_mode=mode,
        quality_level=quality,
        volume=min(100, max(0, volume)),
        color_mode=color_mode,
    )


def save_config(path: str | Path, config: Config) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_path, config_path)