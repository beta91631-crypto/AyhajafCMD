import base64
from io import BytesIO
import socket

import pytest
from PIL import Image

from socialcmd.visual_terminal import prepare_terminal_pixels
from socialcmd.visual_browser import (
    PLATFORMS,
    ChromePage,
    VisualBrowserError,
    _render_browser_frame,
    _reserve_debug_port,
    choose_start_url,
    resolve_social_input,
)


@pytest.mark.parametrize(
    ("source", "platform"),
    [
        ("facebook", "facebook"),
        ("ig", "instagram"),
        ("linkedin", "linkedin"),
        ("pinterest", "pinterest"),
        ("reddit", "reddit"),
        ("threads", "threads"),
        ("tiktok", "tiktok"),
        ("twitter", "x"),
        ("x", "x"),
    ],
)
def test_platform_shortcuts(source, platform):
    assert resolve_social_input(source) == PLATFORMS[platform]


def test_empty_input_requires_a_user_choice():
    with pytest.raises(VisualBrowserError, match="Choose a social site"):
        resolve_social_input(None)


def test_site_menu_uses_the_selected_platform(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "6")

    assert choose_start_url() == PLATFORMS["threads"]


def test_site_menu_accepts_a_custom_url(monkeypatch):
    answers = iter(("u", "https://example.org/feed"))
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert choose_start_url() == "https://example.org/feed"


def test_http_url_is_opened_directly():
    assert resolve_social_input("https://example.org/path") == "https://example.org/path"


def test_search_text_is_encoded():
    assert resolve_social_input("cats and dogs") == "https://duckduckgo.com/?q=cats+and+dogs"


def test_debug_port_is_available_on_loopback():
    port = _reserve_debug_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as endpoint:
        endpoint.bind(("127.0.0.1", port))


def test_wait_for_page_list_retries_connection_refused(monkeypatch):
    class RunningProcess:
        def poll(self):
            return None

    responses = [
        VisualBrowserError("Could not contact the local browser endpoint."),
        [{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}],
    ]
    browser = ChromePage("https://reddit.com/")
    browser.label = "Chrome"
    browser._process = RunningProcess()
    browser._get_json = lambda port, path: (
        (_ for _ in ()).throw(responses.pop(0))
        if isinstance(responses[0], Exception)
        else responses.pop(0)
    )
    monkeypatch.setattr("socialcmd.visual_browser.time.sleep", lambda _: None)

    assert browser._wait_for_page_list(9222) == [
        {"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}
    ]


def test_wait_for_page_list_retries_until_page_target_exists(monkeypatch):
    class RunningProcess:
        def poll(self):
            return None

    responses = iter(([], [{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/page/1"}]))
    browser = ChromePage("https://reddit.com/")
    browser.label = "Chrome"
    browser._process = RunningProcess()
    browser._get_json = lambda port, path: next(responses)
    monkeypatch.setattr("socialcmd.visual_browser.time.sleep", lambda _: None)

    assert browser._wait_for_page_list(9222) == [
        {"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/page/1"}
    ]


@pytest.mark.parametrize("load_visual_resources", [False, True])
def test_browser_launch_uses_reserved_debug_port(monkeypatch, load_visual_resources):
    port = 9321
    launch_arguments = []
    waited_ports = []

    class ExitedProcess:
        def poll(self):
            return 0

    class FakeSocket:
        def close(self):
            pass

    monkeypatch.setattr("socialcmd.visual_browser._find_browser", lambda: ("Edge", "msedge.exe"))
    monkeypatch.setattr("socialcmd.visual_browser._reserve_debug_port", lambda: port)
    monkeypatch.setattr(
        "socialcmd.visual_browser.subprocess.Popen",
        lambda arguments, **options: launch_arguments.extend(arguments) or ExitedProcess(),
    )
    monkeypatch.setattr(
        ChromePage,
        "_wait_for_page_list",
        lambda self, actual_port: waited_ports.append(actual_port) or [
            {"type": "page", "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/page/1"}
        ],
    )
    monkeypatch.setattr("socialcmd.visual_browser.connect", lambda *args, **kwargs: FakeSocket())
    monkeypatch.setattr(ChromePage, "command", lambda self, method, params=None: {})
    monkeypatch.setattr(ChromePage, "navigate", lambda self, url: None)

    with ChromePage(
        "https://reddit.com/",
        private=True,
        load_visual_resources=load_visual_resources,
    ):
        pass

    assert f"--remote-debugging-port={port}" in launch_arguments
    assert waited_ports == [port]
    assert ("--blink-settings=imagesEnabled=false" in launch_arguments) is not load_visual_resources


def test_browser_command_error_includes_method_name():
    class ErrorSocket:
        def send(self, payload):
            pass

        def recv(self, timeout):
            return '{"id":1,"error":{"message":"Invalid parameters"}}'

    browser = ChromePage("https://example.org")
    browser._socket = ErrorSocket()

    with pytest.raises(VisualBrowserError, match="Page.enable: Invalid parameters"):
        browser.command("Page.enable")


def test_rgb_frame_preserves_full_color_and_control_markers():
    source = BytesIO()
    Image.new("RGB", (8, 4), (235, 40, 170)).save(source, format="PNG")
    screenshot = base64.b64encode(source.getvalue()).decode("ascii")

    frame, footer_row = _render_browser_frame(
        screenshot,
        [{"number": 1, "x": 100, "y": 100, "width": 200, "height": 100}],
        40,
        12,
    )

    assert footer_row == 9
    assert "\x1b[38;2;235;40;170m" in frame
    assert "\x1b[48;2;235;40;170m" in frame
    assert " 1 " in frame


def test_terminal_scaling_keeps_pixel_colors_crisp():
    image = Image.new("RGB", (2, 1))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (0, 0, 255))
    encoded = BytesIO()
    image.save(encoded, format="PNG")

    pixels, _, _, _ = prepare_terminal_pixels(
        base64.b64encode(encoded.getvalue()).decode("ascii"), [], 8, 7, 2, 1
    )

    colors = {tuple(pixels[index:index + 3]) for index in range(0, len(pixels), 3)}
    assert colors <= {(255, 0, 0), (0, 0, 255), (0, 0, 0)}


@pytest.mark.parametrize("source", ["file:///etc/passwd", "ftp://example.org", "https:///missing-host"])
def test_non_http_or_malformed_urls_are_rejected(source):
    with pytest.raises(VisualBrowserError):
        resolve_social_input(source)