import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

import generate_cover


class GenerateCoverTests(unittest.TestCase):
    def test_draws_square_png_with_inputs_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "covers", "110.png")
            path = generate_cover.draw_cover(
                110, "#110 - Can Broken GitHub Actions Get Your AWS Account Blocked?",
                ["Jane Doe"], out_path=out)
            self.assertEqual(path, out)
            with Image.open(out) as im:
                self.assertEqual(im.size, (generate_cover.SIZE, generate_cover.SIZE))
                # Corners, including the bottom row the shifted glow must not leave bare.
                for xy in [(5, 5), (5, generate_cover.SIZE - 5)]:
                    for got, want in zip(im.getpixel(xy), generate_cover.TEAL_DEEP):
                        self.assertLessEqual(abs(got - want), 4, xy)
            with open(out + ".inputs") as f:
                self.assertEqual(f.read(), generate_cover.cover_inputs_digest(
                    110, "#110 - Can Broken GitHub Actions Get Your AWS Account Blocked?", ["Jane Doe"]))

    def test_redraws_only_when_inputs_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "007.png")
            with mock.patch.object(generate_cover, "render_cover") as render:
                generate_cover.draw_cover(7, "Title", ["A"], out_path=out)
                self.assertEqual(render.call_count, 1)
                with open(out, "wb") as f:
                    f.write(b"png")
                generate_cover.draw_cover(7, "Title", ["A"], out_path=out)
                self.assertEqual(render.call_count, 1)
                generate_cover.draw_cover(7, "New title", ["A"], out_path=out)
                self.assertEqual(render.call_count, 2)
                generate_cover.draw_cover(7, "New title", ["A", "B"], out_path=out)
                self.assertEqual(render.call_count, 3)

    def test_cover_without_sidecar_is_redrawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "007.png")
            with open(out, "wb") as f:
                f.write(b"old")
            with mock.patch.object(generate_cover, "render_cover") as render:
                generate_cover.draw_cover(7, "Title", out_path=out)
            render.assert_called_once()

    def test_render_is_deterministic(self):
        # Unchanged inputs must give the same bytes, or a redraw would mint a new R2 key.
        with tempfile.TemporaryDirectory() as tmp:
            a, b = os.path.join(tmp, "a.png"), os.path.join(tmp, "b.png")
            generate_cover.render_cover(9, "Same Title Here", ["X"], a)
            generate_cover.render_cover(9, "Same Title Here", ["X"], b)
            with open(a, "rb") as fa, open(b, "rb") as fb:
                self.assertEqual(fa.read(), fb.read())

    def test_clean_title_and_highlight(self):
        self.assertEqual(generate_cover.clean_title("#105 - EU LLMs with Pawel"), "EU LLMs with Pawel")
        words = generate_cover._pick_highlight("EU LLMs with Pawel".split())
        self.assertEqual([w for w, accent in words if accent], ["EU", "LLMs"])


if __name__ == "__main__":
    unittest.main()
