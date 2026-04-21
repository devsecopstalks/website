"""Unit tests for pure helpers (no network, no subprocess). Run from repo: cd tools && uv run python -m unittest discover -s tests -v"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest

# Tests live under tools/tests/; package imports use tools/ on path.
_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

from youtube import status_to_youtube_embed_url, youtube_embed_url_to_video_id  # noqa: E402
import podbean  # noqa: E402
from r2_staging import wants_r2_staging_for_local_video  # noqa: E402


class TestYoutubeEmbedParsing(unittest.TestCase):
    def test_status_list_results_youtube(self):
        status = {
            "status": "completed",
            "results": [
                {"platform": "youtube", "platform_post_id": "dQw4w9WgXcQ"},
            ],
        }
        self.assertEqual(
            status_to_youtube_embed_url(status),
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        )

    def test_embed_url_to_video_id(self):
        self.assertEqual(
            youtube_embed_url_to_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )


class TestPodbeanTextHelpers(unittest.TestCase):
    def test_title_to_url_safe(self):
        self.assertEqual(podbean.title_to_url_safe("Hello World!"), "hello-world-")

    def test_yaml_escape_double_quoted(self):
        self.assertEqual(podbean.yaml_escape_double_quoted('say "hi"'), 'say \\"hi\\"')

    def test_resolve_youtube_video_id(self):
        self.assertEqual(podbean.resolve_youtube_video_id(""), "")
        self.assertEqual(podbean.resolve_youtube_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_checkpoint_prefix(self):
        self.assertEqual(podbean.checkpoint_prefix(97), "episode097")

    def test_build_youtube_description_plain_has_full_urls(self):
        text = podbean.build_youtube_description_plain(
            "Teaser line.", 97, "Shift Left Example"
        )
        self.assertIn("https://www.linkedin.com/company/devsecops-talks/", text)
        self.assertIn("https://devsecops.fm/episodes/097-", text)
        self.assertNotIn("…", text)

    def test_participants_yaml_line(self):
        self.assertEqual(
            podbean._participants_yaml_line(["Paulina", "Mattias", "Andrey"]),
            'participants: ["Paulina", "Mattias", "Andrey"]',
        )

    def test_hugo_shortcode_braces_in_template(self):
        """podbean_line must emit {{< not {< — f-strings need {{{{ for literal {{."""
        line = f' {{{{<  podbean id "Title"  >}}}} '
        self.assertTrue(line.lstrip().startswith("{{<"))


class TestR2StagingPolicy(unittest.TestCase):
    def test_wants_r2_respects_threshold_and_opt_out(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x")
            path = f.name
        old_thr = os.environ.get("YOUTUBE_VIDEO_R2_THRESHOLD_MB")
        try:
            os.environ["YOUTUBE_VIDEO_R2_THRESHOLD_MB"] = "999999"
            args = types.SimpleNamespace(youtube_no_r2_staging=False, youtube_via_r2=False)
            self.assertFalse(wants_r2_staging_for_local_video(path, args))
            os.environ["YOUTUBE_VIDEO_R2_THRESHOLD_MB"] = "0"
            self.assertTrue(wants_r2_staging_for_local_video(path, args))
            args_opt = types.SimpleNamespace(youtube_no_r2_staging=True, youtube_via_r2=False)
            self.assertFalse(wants_r2_staging_for_local_video(path, args_opt))
            args_force = types.SimpleNamespace(youtube_no_r2_staging=False, youtube_via_r2=True)
            os.environ["YOUTUBE_VIDEO_R2_THRESHOLD_MB"] = "999999"
            self.assertTrue(wants_r2_staging_for_local_video(path, args_force))
        finally:
            if old_thr is None:
                os.environ.pop("YOUTUBE_VIDEO_R2_THRESHOLD_MB", None)
            else:
                os.environ["YOUTUBE_VIDEO_R2_THRESHOLD_MB"] = old_thr
            os.unlink(path)


class TestEpisodePipelineNumberedPick(unittest.TestCase):
    def test_select_from_numbered_output(self):
        from episode_pipeline import _select_from_numbered_codex_output  # noqa: E402

        text = "1. First title\n2. Second title\n"
        self.assertEqual(_select_from_numbered_codex_output(text, "1"), "First title")
        self.assertEqual(_select_from_numbered_codex_output(text, "2"), "Second title")


if __name__ == "__main__":
    unittest.main()
