import socket

import pytest

from socialcmd.visual_browser import (
    PLATFORMS,
    ChromePage,
    VisualBrowserError,
    _control_lines,
    _page_lines,
    _reserve_debug_port,
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


def test_empty_input_opens_default_platform():
    assert resolve_social_input(None) == PLATFORMS["reddit"]


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
        [{"type": "page"}],
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

    assert browser._wait_for_page_list(9222) == [{"type": "page"}]


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


def test_page_text_wraps_and_removes_terminal_escape_sequences():
    lines = _page_lines("A readable heading\n\x1b[31mhidden formatting", 12)

    assert lines[0] == "A readable"
    assert all("\x1b" not in line for line in lines)


def test_control_list_includes_link_destination():
    lines = _control_lines(
        [{"number": 1, "tag": "a", "label": "Open page", "href": "https://example.org"}],
        40,
    )

    assert any("Open page" in line for line in lines)
    assert any("https://example.org" in line for line in lines)


@pytest.mark.parametrize("source", ["file:///etc/passwd", "ftp://example.org", "https:///missing-host"])
def test_non_http_or_malformed_urls_are_rejected(source):
    with pytest.raises(VisualBrowserError):
        resolve_social_input(source)