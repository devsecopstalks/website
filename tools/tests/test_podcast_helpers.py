"""Unit tests for pure helpers (no network, no subprocess). Run from repo: cd tools && uv run python -m unittest discover -s tests -v"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

# Tests live under tools/tests/; package imports use tools/ on path.
_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

from youtube import (  # noqa: E402
    status_to_youtube_embed_url,
    youtube_embed_url_to_video_id,
    youtube_status_error_message,
)
import podbean  # noqa: E402
from r2_staging import (  # noqa: E402
    load_r2_youtube_staging_marker,
    remove_r2_youtube_staging_marker,
    save_r2_youtube_staging_marker,
    wants_r2_staging_for_local_video,
)


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

    def test_youtube_status_error_message_when_platform_failed(self):
        status = {
            "status": "completed",
            "results": [
                {"platform": "youtube", "success": False, "error_message": "Session expired"},
            ],
        }
        self.assertEqual(youtube_status_error_message(status), "Session expired")

    def test_youtube_status_error_message_when_success(self):
        status = {
            "results": [
                {"platform": "youtube", "success": True},
            ],
        }
        self.assertIsNone(youtube_status_error_message(status))


class TestR2YoutubeStagingMarker(unittest.TestCase):
    def test_marker_save_load_roundtrip(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            path = f.name
        try:
            save_r2_youtube_staging_marker(
                path,
                "https://cdn.example.com/podcast/youtube-staging/099-abc.mp4",
                "podcast/youtube-staging/099-abc.mp4",
                99,
            )
            loaded = load_r2_youtube_staging_marker(path, 99)
            self.assertEqual(
                loaded,
                (
                    "https://cdn.example.com/podcast/youtube-staging/099-abc.mp4",
                    "podcast/youtube-staging/099-abc.mp4",
                ),
            )
            self.assertIsNone(load_r2_youtube_staging_marker(path, 98))
        finally:
            os.unlink(path)

    def test_marker_requires_https_url(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as f:
            f.write("url=http://insecure.example/x.mp4\nkey=k\nepisode=1\n")
            path = f.name
        try:
            self.assertIsNone(load_r2_youtube_staging_marker(path, 1))
        finally:
            os.unlink(path)

    @patch("r2_staging.delete_r2_object")
    def test_remove_r2_youtube_staging_marker_deletes_key_and_file(self, mock_delete):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as f:
            f.write("url=https://cdn.example/v.mp4\nkey=staging-key-123\nepisode=5\n")
            path = f.name
        try:
            remove_r2_youtube_staging_marker(path)
            mock_delete.assert_called_once_with("staging-key-123")
            self.assertFalse(os.path.isfile(path))
        finally:
            if os.path.isfile(path):
                os.unlink(path)


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
        self.assertIn("https://linkedin.com/company/devsecops-talks/", text)
        self.assertIn("https://devsecops.fm/episodes/097/", text)
        self.assertNotIn("…", text)

    def test_participants_yaml_line(self):
        self.assertEqual(
            podbean._participants_yaml_line(["Paulina", "Mattias", "Andrey"]),
            'participants: ["Paulina", "Mattias", "Andrey"]',
        )

    def test_participants_append_detected_guests_without_manual_override(self):
        guest_context = {
            "guests": [
                {"full_name": "Paul Stack", "participant_name": "Paul Stack"},
                {"full_name": "Cole Bittel", "participant_name": "Cole Bittel"},
            ]
        }
        self.assertEqual(
            podbean._participants_for_episode(None, guest_context),
            ["Paulina", "Mattias", "Andrey", "Paul Stack", "Cole Bittel"],
        )

    def test_participants_manual_override_does_not_append_guests(self):
        guest_context = {"guests": [{"full_name": "Paul Stack"}]}
        self.assertEqual(
            podbean._participants_for_episode("Mattias,Paul Stack", guest_context),
            ["Mattias", "Paul Stack"],
        )

    def test_text_includes_guest_names(self):
        guest_context = {"guests": [{"full_name": "Paul Stack"}]}
        self.assertTrue(
            podbean._text_includes_guest_names(
                "Agent-Native Infra with Paul Stack", guest_context
            )
        )
        self.assertFalse(
            podbean._text_includes_guest_names("Agent-Native Infra", guest_context)
        )

    def test_hugo_shortcode_braces_in_template(self):
        """podbean_line must emit {{< not {< — f-strings need {{{{ for literal {{."""
        line = f' {{{{<  podbean id "Title"  >}}}} '
        self.assertTrue(line.lstrip().startswith("{{<"))

    def test_prompt_podbean_episode_status_defaults_to_draft(self):
        with redirect_stdout(StringIO()):
            self.assertEqual(podbean.prompt_podbean_episode_status(lambda: ""), "draft")

    def test_prompt_podbean_episode_status_accepts_publish(self):
        with redirect_stdout(StringIO()):
            self.assertEqual(podbean.prompt_podbean_episode_status(lambda: "p"), "publish")

    def test_resolve_podbean_episode_status_uses_cli_value(self):
        self.assertEqual(podbean.resolve_podbean_episode_status("draft"), "draft")
        self.assertEqual(podbean.resolve_podbean_episode_status("publish"), "publish")


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

    def test_load_prompt_expands_context_and_style(self):
        from episode_pipeline import DRAFT_PROMPT  # noqa: E402

        self.assertNotIn("{{CONTEXT}}", DRAFT_PROMPT)
        self.assertNotIn("{{STYLE}}", DRAFT_PROMPT)
        self.assertIn("DevSecOps Talks", DRAFT_PROMPT)

    def test_guest_context_to_prompt_text(self):
        from episode_pipeline import guest_context_to_prompt_text  # noqa: E402

        text = guest_context_to_prompt_text(
            {
                "status": "verified",
                "guests": [
                    {
                        "full_name": "Paul Stack",
                        "role": "Founder",
                        "company": "System Initiative",
                        "professional_summary": "Works on Swamp.",
                        "links": [
                            {
                                "label": "Swamp",
                                "url": "https://github.com/systeminit/swamp",
                                "type": "project",
                            }
                        ],
                    }
                ],
            }
        )
        self.assertIn("Detected guest(s): Paul Stack.", text)
        self.assertIn("every title option must include all guest full names", text)
        self.assertIn("https://github.com/systeminit/swamp", text)

    def test_normalize_guest_context_preserves_needs_operator_without_names(self):
        from episode_pipeline import normalize_guest_context  # noqa: E402

        data = normalize_guest_context(
            {
                "status": "needs_operator",
                "guests": [{"full_name": "", "question": "Which Ian is this?"}],
                "notes": "Ambiguous first name.",
            }
        )
        self.assertEqual(data["status"], "needs_operator")
        self.assertEqual(data["guests"], [])
        self.assertEqual(data["notes"], "Ambiguous first name.")

    def test_extract_json_object_tolerates_fence(self):
        from episode_pipeline import _extract_json_object  # noqa: E402

        self.assertEqual(_extract_json_object('```json\n{"status":"no_guests"}\n```'), {"status": "no_guests"})

    def test_review_ends_good_to_go(self):
        from episode_pipeline import _review_ends_good_to_go  # noqa: E402

        self.assertTrue(_review_ends_good_to_go("Some notes.\nGOOD_TO_GO"))
        self.assertFalse(_review_ends_good_to_go("Some issues.\n1. Fix this"))


if __name__ == "__main__":
    unittest.main()
