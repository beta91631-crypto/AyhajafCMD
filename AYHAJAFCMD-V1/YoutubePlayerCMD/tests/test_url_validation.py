import unittest

from youtubecmd.streams import StreamError, choose_formats, validate_youtube_url


class UrlValidationTests(unittest.TestCase):
    def test_accepts_supported_video_urls_and_extra_parameters(self):
        urls = (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=5",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123",
            "https://youtube.com/shorts/dQw4w9WgXcQ",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(validate_youtube_url(url))

    def test_rejects_bad_hosts_schemes_and_video_ids(self):
        urls = (
            "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
            "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=short",
            "https://youtube.com/playlist?list=PL123",
            "not a url",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(validate_youtube_url(url))

    def test_selects_separate_video_and_audio_under_height_limit(self):
        info = {
            "formats": [
                {"url": "v360", "vcodec": "avc1", "acodec": "none", "height": 360},
                {"url": "v720", "vcodec": "avc1", "acodec": "none", "height": 720},
                {"url": "a128", "vcodec": "none", "acodec": "mp4a", "abr": 128},
            ]
        }

        video, audio = choose_formats(info, max_height=480)

        self.assertEqual(video["url"], "v360")
        self.assertEqual(audio["url"], "a128")

    def test_uses_combined_format_when_split_streams_are_unavailable(self):
        combined = {"url": "combined", "vcodec": "avc1", "acodec": "mp4a", "height": 360}

        video, audio = choose_formats({"formats": [combined]}, max_height=480)

        self.assertIs(video, audio)

    def test_best_quality_selects_highest_available_video(self):
        info = {
            "formats": [
                {"url": "v720", "vcodec": "avc1", "acodec": "none", "height": 720},
                {"url": "v1080", "vcodec": "avc1", "acodec": "none", "height": 1080},
                {"url": "a128", "vcodec": "none", "acodec": "mp4a", "abr": 128},
            ]
        }

        video, _audio = choose_formats(info, max_height=None)

        self.assertEqual(video["url"], "v1080")

    def test_rejects_metadata_without_audio_video(self):
        with self.assertRaises(StreamError):
            choose_formats({"formats": []})


if __name__ == "__main__":
    unittest.main()