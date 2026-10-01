import unittest
from unittest.mock import patch

from youtubecmd.renderer import (
    ASCII_RAMP,
    fit_dimensions,
    luminance,
    render_ascii,
    render_frame,
    render_half_block,
)


class RendererTests(unittest.TestCase):
    def test_fit_dimensions_preserves_physical_aspect_ratio(self):
        width, height = fit_dimensions(1920, 1080, 100, 28, cell_aspect=0.5)

        self.assertLessEqual(width, 100)
        self.assertLessEqual(height, 28)
        self.assertAlmostEqual((width / height) * 0.5, 16 / 9, delta=0.04)

    def test_fit_dimensions_rejects_non_positive_values(self):
        with self.assertRaises(ValueError):
            fit_dimensions(0, 10, 20, 20)

    def test_luminance_maps_black_and_white(self):
        self.assertEqual(luminance(0, 0, 0), 0)
        self.assertEqual(luminance(255, 255, 255), 255)

    def test_ascii_output_has_expected_dimensions_and_extremes(self):
        frame = bytes((0, 0, 0, 255, 255, 255))

        result = render_ascii(frame, 2, 1)

        self.assertEqual(result, ASCII_RAMP[0] + ASCII_RAMP[-1])
        self.assertEqual(len(result.splitlines()), 1)
        self.assertEqual(len(result.splitlines()[0]), 2)

    def test_half_block_uses_two_pixels_per_cell(self):
        frame = bytes((255, 0, 0, 0, 0, 255))

        result = render_half_block(frame, 1, 2)

        self.assertIn("▀", result)
        self.assertEqual(len(result.splitlines()), 1)
        self.assertIn("38;2;76;76;76m", result)
        self.assertIn("48;2;29;29;29m", result)

    def test_color_half_block_preserves_rgb_channels(self):
        result = render_half_block(
            bytes((255, 0, 0, 0, 0, 255)), 1, 2, color=True
        )

        self.assertIn("38;2;255;0;0m", result)
        self.assertIn("48;2;0;0;255m", result)

    def test_native_and_python_renderers_match(self):
        frame = bytes((255, 0, 0, 5, 100, 200, 0, 0, 0))
        for color in (False, True):
            with patch("youtubecmd.renderer._native_render_half_block", None):
                expected = render_half_block(frame, 1, 3, color=color)
            actual = render_half_block(frame, 1, 3, color=color)

            self.assertEqual(actual, expected)

    def test_native_and_python_ascii_renderers_match(self):
        frame = bytes((255, 0, 0, 5, 100, 200, 0, 0, 0))
        with patch("youtubecmd.renderer._native_render_ascii", None):
            expected = render_ascii(frame, 1, 3)

        self.assertEqual(render_ascii(frame, 1, 3), expected)

    def test_odd_half_block_height_fills_bottom_with_black(self):
        result = render_half_block(bytes((255, 255, 255)), 1, 1)

        self.assertIn("48;2;0;0;0m", result)

    def test_renderer_rejects_mismatched_frame_size(self):
        with self.assertRaises(ValueError):
            render_frame(b"\x00", 1, 1, "ASCII")


if __name__ == "__main__":
    unittest.main()