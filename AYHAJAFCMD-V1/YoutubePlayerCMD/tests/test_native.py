import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GXX = shutil.which("g++")


@unittest.skipUnless(os.name == "posix" and GXX, "requires a POSIX g++ toolchain")
class NativePlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp_dir.name) / "renderer"
        sources = sorted((ROOT / "native" / "src").glob("*.cpp"))
        subprocess.run(
            [GXX, "-O2", "-std=c++17", *(str(source) for source in sources),
             "-o", str(cls.binary)],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def run_raw(self, pixels, width, height, mode):
        return subprocess.run(
            [str(self.binary), "--raw", str(width), str(height), "30", mode],
            input=pixels,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")

    def test_info_reports_stable_frame_rate(self):
        output = subprocess.run(
            [str(self.binary), "--info"], capture_output=True, check=True, text=True
        ).stdout

        self.assertIn("Target FPS: 30", output)

    def test_raw_ascii_grayscale(self):
        output = self.run_raw(bytes((0, 255, 128, 64)), 2, 2, "ascii")

        self.assertIn("@ \n+#", output)

    def test_raw_color_half_block_keeps_rgb(self):
        output = self.run_raw(bytes((255, 0, 0, 0, 0, 255)), 1, 2, "color")

        self.assertIn("38;2;255;0;0m", output)
        self.assertIn("48;2;0;0;255m", output)

    def test_raw_pixel_mode_colors_each_blank_cell_independently(self):
        output = self.run_raw(bytes((255, 0, 0, 0, 255, 0)), 2, 1, "pixel")

        self.assertIn("48;2;255;0;0m ", output)
        self.assertIn("48;2;0;255;0m ", output)

    def test_stream_json_is_parsed_before_media_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            stream_path = Path(directory) / "stream.json"
            stream_path.write_text(
                json.dumps(
                    {
                        "video_url": "https://example.invalid/video",
                        "audio_url": "https://example.invalid/audio",
                        "title": "\u4e2d\u6587 title",
                        "duration": None,
                        "fps": 30,
                        "width": 640,
                        "height": 360,
                    }
                ),
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["PATH"] = directory
            result = subprocess.run(
                [str(self.binary), "--stream", str(stream_path)],
                capture_output=True,
                text=True,
                env=environment,
                timeout=5,
            )

        self.assertIn("FFmpeg stopped before finishing", result.stderr)
        self.assertNotIn("Stream metadata is invalid", result.stderr)


if __name__ == "__main__":
    unittest.main()