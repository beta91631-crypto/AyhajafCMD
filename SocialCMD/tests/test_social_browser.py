import pytest

from socialcmd.visual_browser import (
    PLATFORMS,
    ChromePage,
    VisualBrowserError,
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


@pytest.mark.parametrize("source", ["file:///etc/passwd", "ftp://example.org", "https:///missing-host"])
def test_non_http_or_malformed_urls_are_rejected(source):
    with pytest.raises(VisualBrowserError):
        resolve_social_input(source)