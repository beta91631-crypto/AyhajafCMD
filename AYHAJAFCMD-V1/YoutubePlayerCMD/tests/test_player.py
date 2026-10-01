import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from youtubecmd.config import Config
from youtubecmd.player import _render_dimensions, _start_video, main
from youtubecmd.streams import StreamInfo


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.stream = StreamInfo(
            title="Test", duration=10, fps=30, width=640, height=360,
            video_url="video", audio_url="audio",
        )

    def test_render_grid_preserves_video_ratio_for_half_block(self):
        width, height = _render_dimensions(self.stream, Config(), 100, 30)

        self.assertLessEqual(width, 100)
        self.assertLessEqual(height, 58)
        self.assertAlmostEqual(width / height, 16 / 9, delta=0.04)

    def test_ascii_grid_accounts_for_terminal_cell_shape(self):
        width, height = _render_dimensions(
            self.stream, Config(renderer_mode="ASCII"), 100, 30
        )

        self.assertLessEqual(width, 100)
        self.assertLessEqual(height, 29)
        self.assertAlmostEqual((width / height) * 0.5, 16 / 9, delta=0.04)

    def test_render_grid_never_exceeds_terminal_at_legacy_quality_value(self):
        width, height = _render_dimensions(
            self.stream, Config(quality_level=1.5), 80, 24
        )

        self.assertLessEqual(width, 80)
        self.assertLessEqual(height, 46)

    @patch("youtubecmd.player.subprocess.Popen")
    def test_ascii_ffmpeg_filter_scales_into_character_grid(self, popen):
        _start_video(self.stream, 0, 100, 56, "ASCII", 30)

        command = popen.call_args.args[0]
        filter_value = command[command.index("-vf") + 1]
        self.assertIn("fps=30.000,scale=100:56:flags=fast_bilinear", filter_value)
        self.assertNotIn("pad=", filter_value)

    @patch("youtubecmd.player.enable_ansi", return_value=True)
    @patch("youtubecmd.player.check_runtime", return_value=[])
    def test_invalid_url_is_a_clean_error(self, _runtime, _ansi):
        output = io.StringIO()

        with redirect_stderr(output):
            result = main(["https://example.com/video"])

        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue().strip(), "Invalid YouTube URL.")


if __name__ == "__main__":
    unittest.main()