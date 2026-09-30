import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from youtubecmd.browse import SearchResult, main, search_videos, select_video


class BrowseTests(unittest.TestCase):
    def test_search_maps_flat_results_to_video_urls(self):
        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return None

            def extract_info(self, query, download):
                self.query = query
                self.download = download
                return {"entries": [{
                    "id": "abcdefghijk",
                    "title": "Example",
                    "channel": "Channel",
                    "duration": 125,
                }]}

        with patch.dict(sys.modules, {"yt_dlp": SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            videos = search_videos("  test query  ")

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].title, "Example")
        self.assertEqual(videos[0].duration, 125)
        self.assertEqual(videos[0].url, "https://www.youtube.com/watch?v=abcdefghijk")

    @patch("youtubecmd.browse.search_videos")
    def test_select_video_accepts_numbered_search_result(self, search):
        search.return_value = [
            SearchResult("First", "Channel", 90, "https://youtu.be/abcdefghijk"),
            SearchResult("Second", "Channel", 120, "https://youtu.be/lmnopqrstuv"),
        ]
        output = StringIO()

        with patch("builtins.input", return_value="2"), redirect_stderr(output):
            selected = select_video("music")

        self.assertEqual(selected, "https://youtu.be/lmnopqrstuv")
        self.assertIn("YouTube search results", output.getvalue())

    @patch("youtubecmd.browse.search_videos")
    def test_direct_video_url_skips_search(self, search):
        url = "https://youtu.be/abcdefghijk"

        self.assertEqual(select_video(url), url)
        search.assert_not_called()

    @patch("youtubecmd.browse.stream_payload", return_value={"title": "Example"})
    @patch("youtubecmd.browse.select_video", return_value="https://youtu.be/abcdefghijk")
    def test_main_preserves_quality_selection_and_json_stdout(self, _select, stream_payload):
        output = StringIO()

        with redirect_stdout(output), redirect_stderr(StringIO()):
            result = main(["music", "--video-quality", "1080"])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), '{"title": "Example"}\n')
        stream_payload.assert_called_once_with(
            "https://youtu.be/abcdefghijk", max_height=1080
        )

    @patch("youtubecmd.browse.stream_payload", return_value={"title": "Example"})
    @patch("youtubecmd.browse.select_video", return_value="https://youtu.be/abcdefghijk")
    def test_main_prompts_for_source_quality_after_video_selection(
        self, select_video, stream_payload
    ):
        output = StringIO()

        with patch("builtins.input", return_value="4"), redirect_stdout(output), \
                redirect_stderr(StringIO()):
            result = main([])

        self.assertEqual(result, 0)
        select_video.assert_called_once()
        stream_payload.assert_called_once_with(
            "https://youtu.be/abcdefghijk", max_height=1080
        )


if __name__ == "__main__":
    unittest.main()