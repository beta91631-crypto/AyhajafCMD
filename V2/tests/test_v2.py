from io import BytesIO

from PIL import Image
import pytest

from socialcmd_v2.browser import HOME_URL, profile_directory, resolve_target
from socialcmd_v2.rendering import RenderSettings, prepare_image, render_halfblocks, terminal_dimensions


def test_default_target_is_duckduckgo():
    assert resolve_target("") == HOME_URL


def test_search_terms_use_duckduckgo():
    assert resolve_target("terminal pixels") == "https://duckduckgo.com/?q=terminal+pixels"


def test_only_http_addresses_are_opened_directly():
    assert resolve_target("https://example.org/path") == "https://example.org/path"
    assert resolve_target("HTTPS://example.org/path") == "HTTPS://example.org/path"
    with pytest.raises(ValueError, match="Only HTTP and HTTPS"):
        resolve_target("file:///etc/passwd")


def test_persistent_profile_is_separate_for_v2():
    assert profile_directory().parts[-3:] == ("AYHAJAFCMD", "V2", "chromium-profile")


def test_terminal_dimensions_support_wide_windows():
    assert terminal_dimensions(400, 200) == (320, 120)


def test_pixel_settings_validate_supported_ranges():
    settings = RenderSettings(pixel_size=4, colors=32, dither="none")
    settings.validate()
    with pytest.raises(ValueError, match="Pixel size"):
        RenderSettings(pixel_size=9).validate()
    with pytest.raises(ValueError, match="Palette size"):
        RenderSettings(colors=300).validate()


def test_image_preparation_and_halfblock_rendering():
    source = BytesIO()
    Image.new("RGB", (16, 8), (100, 40, 200)).save(source, format="PNG")
    settings = RenderSettings(pixel_size=2, colors=16, dither="floyd")

    image = prepare_image(source.getvalue(), 20, 10, settings)
    frame = render_halfblocks(image)

    assert image.size == (20, 14)
    assert "\x1b[38;2;" in frame
    assert "\x1b[48;2;" in frame
    assert "▀" in frame
