import pytest

from socialcmd.visual_browser import (
    PLATFORMS,
    ChromePage,
    VisualBrowserError,
    _control_lines,
    _page_lines,
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


def test_wait_for_debug_port_reads_selected_profile(tmp_path):
    (tmp_path / "DevToolsActivePort").write_text("9222\n/devtools/browser/test", encoding="ascii")

    class RunningProcess:
        def poll(self):
            return None

    browser = ChromePage("https://reddit.com/")
    browser._process = RunningProcess()

    assert browser._wait_for_debug_port(str(tmp_path)) == 9222


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


def test_lightweight_mode_blocks_visual_resources():
    calls = []
    browser = ChromePage("https://example.org")
    browser.command = lambda method, params=None: calls.append((method, params))

    browser.configure_resource_loading()

    assert [method for method, _ in calls] == ["Network.enable", "Network.setBlockedURLs"]
    blocked_types = {
        pattern["resourceType"]
        for pattern in calls[1][1]["urlPatterns"]
    }
    assert blocked_types == {"Image", "Media", "Font"}


def test_visual_resources_can_be_enabled_for_compatibility():
    calls = []
    browser = ChromePage("https://example.org", load_visual_resources=True)
    browser.command = lambda method, params=None: calls.append(method)

    browser.configure_resource_loading()

    assert calls == []


@pytest.mark.parametrize("source", ["file:///etc/passwd", "ftp://example.org", "https:///missing-host"])
def test_non_http_or_malformed_urls_are_rejected(source):
    with pytest.raises(VisualBrowserError):
        resolve_social_input(source)