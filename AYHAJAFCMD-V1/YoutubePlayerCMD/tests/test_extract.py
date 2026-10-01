import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from youtubecmd.extract import main, stream_payload
from youtubecmd.streams import StreamInfo


class ExtractTests(unittest.TestCase):
    @patch("youtubecmd.extract.extract_streams")
    def test_stream_payload_contains_native_player_contract(self, extract_streams):
        extract_streams.return_value = StreamInfo(
            title="test", duration=12.5, fps=30, width=640, height=360,
            video_url="video-url", audio_url="audio-url",
        )

        payload = stream_payload("https://youtu.be/abcdefghijk")

        self.assertEqual(payload["video_url"], "video-url")
        self.assertEqual(payload["audio_url"], "audio-url")
        self.assertEqual(payload["title"], "test")
        self.assertEqual(payload["duration"], 12.5)
        self.assertEqual(payload["fps"], 30)
        extract_streams.assert_called_once_with(
            "https://youtu.be/abcdefghijk", max_height=720
        )

    @patch("youtubecmd.extract.stream_payload", return_value={"title": "test"})
    def test_video_quality_option_selects_source_resolution(self, stream_payload):
        output = StringIO()

        with redirect_stdout(output):
            result = main([
                "https://youtu.be/abcdefghijk", "--video-quality", "1080"
            ])

        self.assertEqual(result, 0)
        stream_payload.assert_called_once_with(
            "https://youtu.be/abcdefghijk", max_height=1080
        )

    @patch("youtubecmd.extract.stream_payload", return_value={"title": "test"})
    def test_best_video_quality_removes_source_resolution_cap(self, stream_payload):
        with redirect_stdout(StringIO()):
            result = main([
                "https://youtu.be/abcdefghijk", "--video-quality", "best"
            ])

        self.assertEqual(result, 0)
        stream_payload.assert_called_once_with(
            "https://youtu.be/abcdefghijk", max_height=None
        )

    @patch("youtubecmd.extract.input", return_value="https://youtu.be/abcdefghijk")
    @patch("youtubecmd.extract.stream_payload", return_value={"title": "test"})
    def test_prompt_does_not_pollute_json_stdout(self, _payload, _input):
        output = StringIO()
        errors = StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            result = main([])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), '{"title": "test"}\n')
        self.assertEqual(errors.getvalue(), "YouTube URL: ")


if __name__ == "__main__":
    unittest.main()