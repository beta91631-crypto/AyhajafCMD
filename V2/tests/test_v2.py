from io import BytesIO

from PIL import Image
import pytest

from socialcmd_v2.browser import HOME_URL, profile_directory, resolve_target
from socialcmd_v2.controller import adjust_setting, settings_panel
from socialcmd_v2.main import _dispatch
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


def test_settings_controller_changes_live_render_options():
    settings = RenderSettings()

    adjust_setting(settings, "pixel+")
    adjust_setting(settings, "colors-")
    adjust_setting(settings, "zoom+")
    adjust_setting(settings, "dither")
    adjust_setting(settings, "mode")

    assert settings.pixel_size == 2
    assert settings.colors == 248
    assert settings.zoom == 1.1
    assert settings.dither == "none"
    assert settings.mode == "sixel"
    assert "Zoom: 1.1x" in settings_panel(settings)


def test_settings_controller_enforces_limits():
    settings = RenderSettings(pixel_size=8, colors=256, zoom=2.0)

    adjust_setting(settings, "pixel+")
    adjust_setting(settings, "colors+")
    adjust_setting(settings, "zoom+")

    assert settings.pixel_size == 8
    assert settings.colors == 256
    assert settings.zoom == 2.0


def test_controller_commands_update_render_settings():
    class FakeSession:
        pass

    settings = RenderSettings()
    session = FakeSession()

    assert _dispatch("settings", session, settings, []) == settings_panel(settings)
    _dispatch("]", session, settings, [])
    _dispatch("z", session, settings, [])
    _dispatch("d", session, settings, [])

    assert (settings.pixel_size, settings.zoom, settings.dither) == (2, 1.1, "none")


def test_controller_does_not_switch_to_missing_sixel(monkeypatch):
    class FakeSession:
        pass

    monkeypatch.setattr("socialcmd_v2.main.shutil.which", lambda _: None)
    settings = RenderSettings()

    result = _dispatch("m", FakeSession(), settings, [])

    assert "install Chafa" in result
    assert settings.mode == "halfblock"


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


def test_pixel_size_and_zoom_change_the_rendered_image():
    source = BytesIO()
    image = Image.new("RGB", (32, 16))
    for y in range(16):
        for x in range(32):
            image.putpixel((x, y), (x * 7, y * 13, (x + y) * 4))
    image.save(source, format="PNG")
    screenshot = source.getvalue()

    fine = prepare_image(screenshot, 40, 20, RenderSettings())
    coarse = prepare_image(screenshot, 40, 20, RenderSettings(pixel_size=4))
    zoomed = prepare_image(screenshot, 40, 20, RenderSettings(zoom=1.5))

    assert fine.tobytes() != coarse.tobytes()
    assert fine.tobytes() != zoomed.tobytes()
