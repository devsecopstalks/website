import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

import generate_cover


class GenerateCoverTests(unittest.TestCase):
    def test_writes_square_png_and_returns_site_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "covers", "110.png")
            path = generate_cover.generate_cover(
                110, "#110 - Can Broken GitHub Actions Get Your AWS Account Blocked?",
                ["Jane Doe"], out_path=out)
            self.assertEqual(path, "/images/covers/110.png")
            with Image.open(out) as im:
                self.assertEqual(im.size, (generate_cover.SIZE, generate_cover.SIZE))
                # Corners, including the bottom row the shifted glow must not leave bare.
                for xy in [(5, 5), (5, generate_cover.SIZE - 5)]:
                    for got, want in zip(im.getpixel(xy), generate_cover.TEAL_DEEP):
                        self.assertLessEqual(abs(got - want), 4, xy)

    def test_keeps_existing_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "007.png")
            with open(out, "wb") as f:
                f.write(b"hand-made")
            self.assertEqual(generate_cover.generate_cover(7, "Title", out_path=out),
                             "/images/covers/007.png")
            with open(out, "rb") as f:
                self.assertEqual(f.read(), b"hand-made")

    def test_clean_title_and_highlight(self):
        self.assertEqual(generate_cover.clean_title("#105 - EU LLMs with Pawel"), "EU LLMs with Pawel")
        words = generate_cover._pick_highlight("EU LLMs with Pawel".split())
        self.assertEqual([w for w, accent in words if accent], ["EU", "LLMs"])


if __name__ == "__main__":
    unittest.main()
