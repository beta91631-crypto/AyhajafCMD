import base64
from io import BytesIO
import unittest

from PIL import Image

from youtubecmd.visual_terminal import (
    prepare_terminal_pixels,
    render_control_markers,
    render_rgb_frame,
)


class VisualTerminalTests(unittest.TestCase):
    def test_half_block_preserves_two_independent_rgb_pixels(self):
        rendered = render_rgb_frame(bytes((255, 0, 0, 0, 0, 255)), 1, 2)

        self.assertEqual(
            rendered,
            "\x1b[38;2;255;0;0m\x1b[48;2;0;0;255m▀\x1b[0m",
        )

    def test_odd_height_fills_missing_bottom_pixel_with_black(self):
        rendered = render_rgb_frame(bytes((0, 255, 0)), 1, 1)

        self.assertIn("\x1b[48;2;0;0;0m", rendered)

    def test_rejects_mismatched_frame(self):
        with self.assertRaises(ValueError):
            render_rgb_frame(b"\x00", 1, 1)

    def test_screenshot_is_fitted_and_interactive_controls_are_marked(self):
        source = Image.new("RGB", (8, 4), (20, 30, 40))
        encoded = BytesIO()
        source.save(encoded, format="JPEG", quality=100)
        screenshot = base64.b64encode(encoded.getvalue()).decode("ascii")

        pixels, width, height, markers = prepare_terminal_pixels(
            screenshot,
            [{"number": 1, "x": 0, "y": 0, "width": 4, "height": 4}],
            terminal_width=8,
            terminal_rows=5,
            viewport_width=8,
            viewport_height=4,
        )

        self.assertEqual((width, height), (8, 4))
        self.assertEqual(len(pixels), width * height * 3)
        self.assertEqual(markers, [(1, 0, 0)])
        self.assertNotIn(bytes((0, 170, 220)), pixels)

        overlay = render_control_markers(markers, width, height // 2)
        self.assertIn("\x1b[48;2;0;170;220m", overlay)
        self.assertIn(" 1 ", overlay)

    def test_marker_labels_remain_small_terminal_text(self):
        rendered = render_control_markers([(17, 2, 4)], 20, 10)

        self.assertIn("\x1b[3;5H", rendered)
        self.assertIn(" 17 ", rendered)

    def test_rejects_bad_screenshot_data(self):
        with self.assertRaises(ValueError):
            prepare_terminal_pixels("not-base64", [], 8, 5, 8, 4)


if __name__ == "__main__":
    unittest.main()