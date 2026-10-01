import json
import tempfile
import unittest
from pathlib import Path

from youtubecmd.config import Config, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_missing_config_uses_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(Path(directory) / "config.json")
            self.assertEqual(config, Config())
            self.assertEqual(config.color_mode, "color")

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "config.json"
            original = Config("ASCII", 0.75, 45, "color")

            save_config(path, original)

            self.assertEqual(load_config(path), original)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_invalid_values_are_clamped_or_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps({"renderer_mode": "bad", "quality_level": 9, "volume": -5}),
                encoding="utf-8",
            )

            config = load_config(path)

            self.assertEqual(config.renderer_mode, "HALF_BLOCK")
            self.assertEqual(config.quality_level, 1.0)
            self.assertEqual(config.volume, 0)


if __name__ == "__main__":
    unittest.main()