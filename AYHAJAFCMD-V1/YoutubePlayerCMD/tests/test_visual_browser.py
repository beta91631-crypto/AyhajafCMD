import unittest
import base64
from io import StringIO
from unittest.mock import patch

from youtubecmd.visual_browser import (
    ChromePage,
    DEFAULT_FPS,
    INTERACTIVE_SCRIPT,
    MAX_FPS,
    VisualBrowserError,
    _browser_headless_variants,
    _profile_directory,
    run_visual_browser,
    _write_terminal,
    _run_command,
    resolve_youtube_input,
)


class FakePage:
    def __init__(self):
        self.url = "https://www.youtube.com/"
        self.clicked = []
        self.navigated = []
        self.typed = []
        self.pressed = []
        self.scrolled = []
        self.commands = []
        self.hovered = []
        self.control_pages = []

    def click(self, number):
        self.clicked.append(number)
        return f"Clicked {number}: control"

    def hover(self, number):
        self.hovered.append(number)
        return f"Hovering {number}: control"

    def page_controls(self, direction):
        self.control_pages.append(direction)
        return f"Showing {direction} controls"

    def navigate(self, url):
        self.navigated.append(url)

    def type_text(self, value):
        self.typed.append(value)

    def press_key(self, value):
        self.pressed.append(value)

    def scroll(self, value):
        self.scrolled.append(value)

    def command(self, method, params):
        self.commands.append((method, params))

    def visible_elements(self):
        return []

    def screenshot(self):
        return "encoded-image"


class VisualBrowserTests(unittest.TestCase):
    def test_search_query_opens_youtube_results(self):
        self.assertEqual(
            resolve_youtube_input("Arryadia TV"),
            "https://www.youtube.com/results?search_query=Arryadia+TV",
        )

    def test_direct_youtube_url_is_preserved(self):
        url = "https://www.youtube.com/watch?v=abcdefghijk"
        self.assertEqual(resolve_youtube_input(url), url)

    def test_rejects_non_web_schemes(self):
        with self.assertRaises(VisualBrowserError):
            resolve_youtube_input("file:///etc/passwd")

    def test_refresh_rate_defaults_to_smooth_bounded_values(self):
        self.assertEqual(DEFAULT_FPS, 8)
        self.assertEqual(MAX_FPS, 15)
        with self.assertRaises(VisualBrowserError):
            run_visual_browser(fps=MAX_FPS + 1)

    def test_browser_stays_headless_and_uses_persistent_profile(self):
        self.assertEqual(
            _browser_headless_variants("Chrome"),
            ("--headless=new", "--headless", "--headless=old"),
        )
        self.assertEqual(_profile_directory().name, "browser-profile-v2")

    def test_screenshot_capture_uses_lossless_png(self):
        page = ChromePage("https://www.youtube.com/")
        image = base64.b64encode(b"\x89PNG\r\n\x1a\nimage").decode("ascii")

        with patch.object(page, "command", return_value={"data": image}) as command:
            self.assertEqual(page.screenshot(), image)

        self.assertEqual(command.call_args.args[1]["format"], "png")

    def test_terminal_commands_click_search_type_and_submit(self):
        browser = FakePage()

        status, running = _run_command(browser, "7")
        self.assertTrue(running)
        self.assertEqual(status, "Clicked 7: control")
        self.assertEqual(browser.clicked, [7])

        status, _running = _run_command(browser, "h 7")
        self.assertEqual(status, "Hovering 7: control")
        self.assertEqual(browser.hovered, [7])

        _run_command(browser, "more")
        _run_command(browser, "prev")
        self.assertEqual(browser.control_pages, ["next", "previous"])

        _run_command(browser, "/Arryadia")
        self.assertEqual(
            browser.navigated[-1],
            "https://www.youtube.com/results?search_query=Arryadia",
        )

        _run_command(browser, "t match highlights")
        _run_command(browser, "enter")
        _run_command(browser, "escape")
        self.assertEqual(browser.typed, ["match highlights"])
        self.assertEqual(browser.pressed, ["enter", "escape"])

    def test_visible_interactive_script_keeps_number_to_dom_mapping(self):
        self.assertIn("window.__youtubecmdTargets = targets", INTERACTIVE_SCRIPT)
        self.assertIn("document.querySelectorAll(selectors)", INTERACTIVE_SCRIPT)
        self.assertIn("targets.length >= 40", INTERACTIVE_SCRIPT)

    def test_page_click_and_hover_dispatch_to_selected_element(self):
        page = ChromePage("https://www.youtube.com/")
        page._targets = [{
            "number": 1, "label": "Play", "tag": "button",
            "x": 20, "y": 30, "width": 40, "height": 20,
        }]

        with patch.object(page, "command") as command:
            self.assertEqual(page.click(1), "Clicked 1: Play")
        self.assertEqual(command.call_count, 2)
        self.assertEqual(command.call_args_list[0].args[0], "Input.dispatchMouseEvent")
        self.assertEqual(command.call_args_list[0].args[1]["type"], "mousePressed")
        self.assertEqual(command.call_args_list[1].args[1]["type"], "mouseReleased")

        with patch.object(page, "command") as command:
            self.assertEqual(page.hover(1), "Hovering 1: Play")
        command.assert_called_once_with(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": 40.0, "y": 40.0},
        )

    def test_page_controls_updates_dom_pagination_offset(self):
        page = ChromePage("https://www.youtube.com/")
        page._has_more = True

        with patch.object(page, "evaluate") as evaluate:
            self.assertEqual(
                page.page_controls("next"), "Showing controls 41-80"
            )

        evaluate.assert_called_once_with("window.__youtubecmdOffset = 40")

    @patch("youtubecmd.visual_browser.prepare_terminal_pixels", return_value=(bytes(10 * 14 * 3), 10, 14, []))
    @patch("youtubecmd.visual_browser.render_rgb_frame", return_value="PIXELS")
    def test_terminal_footer_stays_inside_available_rows(self, _render, _prepare):
        output = StringIO()
        with patch("youtubecmd.visual_browser.sys.stdout", output):
            _write_terminal(FakePage(), "", "Ready", 10, 10)

        rendered = output.getvalue()
        self.assertIn("\x1b[10;1H", rendered)
        self.assertNotIn("\x1b[11;1H", rendered)


if __name__ == "__main__":
    unittest.main()