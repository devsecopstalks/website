"""Helper and publishing-flow tests with network and subprocess calls mocked.

Run from repo: cd tools && uv run python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Tests live under tools/tests/; package imports use tools/ on path.
_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

from youtube import (  # noqa: E402
    scheduled_upload_job_id,
    status_to_youtube_embed_url,
    youtube_embed_url_to_video_id,
    youtube_status_error_message,
)
import podbean  # noqa: E402
import episode_pipeline  # noqa: E402
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

    def test_scheduled_upload_job_id(self):
        self.assertEqual(
            scheduled_upload_job_id(
                {
                    "success": True,
                    "job_id": "job_123",
                    "scheduled_date": "2026-07-01T09:00:00Z",
                }
            ),
            "job_123",
        )
        self.assertIsNone(scheduled_upload_job_id({"request_id": "req_123"}))


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
    def test_stage_downloads_can_replace_existing_raw_contents(self):
        with (
            tempfile.TemporaryDirectory() as downloads_dir,
            tempfile.TemporaryDirectory() as raw_dir,
        ):
            downloads = Path(downloads_dir)
            raw = Path(raw_dir)
            (downloads / "new.mp3").write_bytes(b"new audio")
            (downloads / "new.mp4").write_bytes(b"new video")
            (raw / "old.mp3").write_bytes(b"old audio")
            (raw / "old-notes.md").write_text("old notes")
            (raw / ".gitignore").write_text("*.mp3\n")

            with (
                patch.object(podbean, "DOWNLOADS_DIR", downloads_dir),
                patch.object(podbean, "RAW_DIR", raw_dir),
                patch("builtins.input", return_value=""),
                redirect_stdout(StringIO()),
            ):
                podbean.stage_downloads_to_raw()

            self.assertEqual(
                sorted(path.name for path in raw.iterdir()),
                [".gitignore", "new.mp3", "new.mp4"],
            )
            self.assertEqual(list(downloads.iterdir()), [])

    def test_stage_downloads_decline_preserves_both_locations(self):
        with (
            tempfile.TemporaryDirectory() as downloads_dir,
            tempfile.TemporaryDirectory() as raw_dir,
        ):
            downloads = Path(downloads_dir)
            raw = Path(raw_dir)
            (downloads / "new.mp3").write_bytes(b"new audio")
            (raw / "old.mp3").write_bytes(b"old audio")

            with (
                patch.object(podbean, "DOWNLOADS_DIR", downloads_dir),
                patch.object(podbean, "RAW_DIR", raw_dir),
                patch("builtins.input", return_value="n"),
                redirect_stdout(StringIO()),
                self.assertRaises(SystemExit) as exit_context,
            ):
                podbean.stage_downloads_to_raw()

            self.assertEqual(exit_context.exception.code, 0)
            self.assertTrue((downloads / "new.mp3").exists())
            self.assertTrue((raw / "old.mp3").exists())

    def test_title_to_url_safe(self):
        self.assertEqual(podbean.title_to_url_safe("Hello World!"), "hello-world-")

    def test_yaml_escape_double_quoted(self):
        self.assertEqual(podbean.yaml_escape_double_quoted('say "hi"'), 'say \\"hi\\"')

    def test_resolve_youtube_video_id(self):
        self.assertEqual(podbean.resolve_youtube_video_id(""), "")
        self.assertEqual(podbean.resolve_youtube_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_checkpoint_prefix(self):
        self.assertEqual(podbean.checkpoint_prefix(97), "episode097")

    def test_checkpoint_source_identity_rejects_different_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.mp3"
            second = Path(directory) / "second.mp3"
            first.write_bytes(b"first recording")
            second.write_bytes(b"second recording")
            out_base = str(Path(directory) / "episode104")

            podbean.validate_or_bind_checkpoint_source(out_base, str(first), [])
            with self.assertRaisesRegex(ValueError, "checkpoint source mismatch"):
                podbean.validate_or_bind_checkpoint_source(out_base, str(second), [])

    def test_legacy_checkpoint_source_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "episode.mp3"
            checkpoint = Path(directory) / "episode104.txt"
            audio.write_bytes(b"recording")
            checkpoint.write_text("transcript")
            out_base = str(Path(directory) / "episode104")

            with self.assertRaisesRegex(ValueError, "reuse was not confirmed"):
                podbean.validate_or_bind_checkpoint_source(
                    out_base,
                    str(audio),
                    [checkpoint],
                    input_func=lambda: "",
                )
            podbean.validate_or_bind_checkpoint_source(
                out_base,
                str(audio),
                [checkpoint],
                input_func=lambda: "y",
            )
            self.assertEqual(
                json.loads(Path(f"{out_base}-source.json").read_text())["filename"],
                "episode.mp3",
            )

    def test_infer_resume_episode_number_uses_unfinished_adjacent_checkpoint(self):
        with tempfile.TemporaryDirectory() as out_dir, tempfile.TemporaryDirectory() as episodes_dir:
            (Path(out_dir) / "episode104-article.md").write_text("article")
            with (
                patch.object(podbean, "OUT_DIR", out_dir),
                patch.object(podbean, "EPISODES_DIR", episodes_dir),
            ):
                self.assertEqual(podbean.infer_resume_episode_number(105), 104)

    def test_infer_resume_episode_number_ignores_completed_page(self):
        with tempfile.TemporaryDirectory() as out_dir, tempfile.TemporaryDirectory() as episodes_dir:
            (Path(out_dir) / "episode104-article.md").write_text("article")
            (Path(episodes_dir) / "104-finished.md").write_text("page")
            with (
                patch.object(podbean, "OUT_DIR", out_dir),
                patch.object(podbean, "EPISODES_DIR", episodes_dir),
            ):
                self.assertIsNone(podbean.infer_resume_episode_number(105))

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

    def test_scheduled_episode_request_queues_future_publication(self):
        schedule = podbean.publish_schedule_from_datetime(
            datetime.datetime(2099, 7, 1, 11, tzinfo=datetime.timezone.utc),
            "test",
        )
        with patch("podbean.requests.post") as post:
            podbean.create_podbean_episode(
                "token", "title", "content", 123, media_key="audio.mp3",
                status=podbean.podbean_creation_status(schedule),
                publish_timestamp=schedule.podbean_timestamp,
            )
        data = post.call_args.kwargs["data"]
        self.assertEqual(data["status"], "future")
        self.assertEqual(data["publish_timestamp"], str(schedule.podbean_timestamp))

    def test_immediate_episode_request_publishes_without_timestamp(self):
        with patch("podbean.requests.post") as post:
            podbean.create_podbean_episode(
                "token", "title", "content", 123, media_key="audio.mp3",
                status=podbean.podbean_creation_status(None),
            )
        data = post.call_args.kwargs["data"]
        self.assertEqual(data["status"], "publish")
        self.assertNotIn("publish_timestamp", data)

    def test_validate_podbean_schedule_requires_matching_status_and_time(self):
        schedule = podbean.publish_schedule_from_datetime(
            datetime.datetime(2099, 7, 1, 11, tzinfo=datetime.timezone.utc), "test",
        )
        for timestamp_key in ("publish_time", "publish_timestamp"):
            with self.subTest(timestamp_key=timestamp_key):
                podbean.validate_podbean_schedule(
                    {"episode": {"status": "future", timestamp_key: schedule.podbean_timestamp}},
                    schedule,
                )
        for episode in (
            {"status": "draft", "publish_time": schedule.podbean_timestamp},
            {"status": "publish", "publish_time": schedule.podbean_timestamp},
            {"publish_time": schedule.podbean_timestamp},
            {"status": "future"},
            {"status": "future", "publish_time": schedule.podbean_timestamp + 60},
        ):
            with self.subTest(episode=episode), self.assertRaises(ValueError):
                podbean.validate_podbean_schedule({"episode": episode}, schedule)

    def test_podbean_player_id_uses_query_parameter(self):
        response = {
            "episode": {
                "player_url": (
                    "https://www.podbean.com/media/player/abc?from=site"
                    "&i=f9i9z-1aeab7f-pb&skin=1"
                )
            }
        }
        self.assertEqual(
            podbean.podbean_player_id(response),
            "f9i9z-1aeab7f-pb",
        )

    def test_podbean_player_id_falls_back_to_episode_id(self):
        self.assertEqual(
            podbean.podbean_player_id({"episode": {"id": "abc12-1b23456-pb"}}),
            "abc12-1b23456-pb",
        )

    def test_podbean_player_id_reports_api_error_description(self):
        with self.assertRaisesRegex(
            ValueError,
            "Podbean rejected episode creation: invalid_request: publish time is invalid",
        ):
            podbean.podbean_player_id(
                {
                    "error": "invalid_request",
                    "error_description": "publish time is invalid",
                }
            )

    def test_find_podbean_episode_by_numbered_title(self):
        episode = {"id": "episode-id", "title": "#104 - Existing"}
        self.assertIs(
            podbean.find_podbean_episode({"episodes": [episode]}, 104),
            episode,
        )

    def test_publish_schedule_from_existing_podbean_episode(self):
        schedule = podbean.publish_schedule_from_podbean_episode(
            {
                "title": "#104 - Scheduled",
                "status": "future",
                "publish_time": 4086579600,
            },
            local_tz=datetime.timezone.utc,
        )
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.podbean_timestamp, 4086579600)
        self.assertEqual(schedule.upload_post_scheduled_date, "2099-07-01T09:00:00Z")

    def test_future_dated_draft_is_not_a_confirmed_schedule(self):
        episode = {"status": "draft", "publish_time": 4086579600, "episode_number": 104}
        self.assertIsNone(podbean.publish_schedule_from_podbean_episode(episode))
        # Keep the intended slot reserved while the operator repairs old drafts.
        plan = podbean.episode_plan_from_podbean_response({"episodes": [episode]})
        self.assertEqual(plan.anchor_episode, episode)

    def test_create_podbean_episode_includes_publish_timestamp(self):
        with patch("podbean.requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            response = podbean.create_podbean_episode(
                "token",
                "title",
                "content",
                123,
                media_key="audio.mp3",
                status="publish",
                publish_timestamp=4086579600,
                url="https://example.test/episodes",
            )
        self.assertEqual(response, {"ok": True})
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"]["publish_timestamp"], "4086579600")

    def test_episode_plan_uses_highest_episode_number_and_latest_schedule(self):
        tz = datetime.timezone.utc
        data = {
            "count": 2,
            "episodes": [
                {
                    "title": "#104 - Scheduled",
                    "episode_number": 104,
                    "publish_time": 4086579600,
                    "status": "future",
                },
                {
                    "title": "#103 - Published",
                    "episode_number": 103,
                    "publish_time": 4085974800,
                    "status": "publish",
                },
                {
                    "title": "#200 - Draft",
                    "episode_number": 200,
                    "publish_time": 0,
                    "status": "draft",
                },
            ],
        }
        plan = podbean.episode_plan_from_podbean_response(data, local_tz=tz)
        self.assertEqual(plan.next_episode_number, 201)
        self.assertEqual(plan.anchor_episode["title"], "#104 - Scheduled")
        self.assertEqual(plan.anchor_datetime, datetime.datetime(2099, 7, 1, 9, tzinfo=tz))
        self.assertEqual(len(plan.publish_datetimes), 2)

    def test_next_available_monday_uses_today_before_1100_utc(self):
        tz = datetime.timezone.utc
        plan = podbean.episode_plan_from_podbean_response({}, local_tz=tz)
        self.assertEqual(
            podbean.next_available_monday(
                plan,
                now=datetime.datetime(2099, 6, 22, 10, tzinfo=tz),
            ),
            datetime.datetime(2099, 6, 22, 11, tzinfo=tz),
        )

    def test_next_available_monday_uses_next_week_after_1100_utc(self):
        tz = datetime.timezone.utc
        plan = podbean.episode_plan_from_podbean_response({}, local_tz=tz)
        self.assertEqual(
            podbean.next_available_monday(
                plan,
                now=datetime.datetime(2099, 6, 22, 11, tzinfo=tz),
            ),
            datetime.datetime(2099, 6, 29, 11, tzinfo=tz),
        )

    def test_next_available_monday_follows_latest_scheduled_episode(self):
        tz = datetime.timezone.utc
        latest = datetime.datetime(2099, 6, 30, 11, tzinfo=tz)
        plan = podbean.episode_plan_from_podbean_response(
            {
                "episodes": [
                    {
                        "title": "#104 - Scheduled",
                        "status": "publish",
                        "publish_time": int(latest.timestamp()),
                    }
                ]
            },
            local_tz=tz,
        )
        self.assertEqual(
            podbean.next_available_monday(
                plan,
                now=datetime.datetime(2099, 6, 22, 10, tzinfo=tz),
            ),
            datetime.datetime(2099, 7, 6, 11, tzinfo=tz),
        )

    def test_next_available_monday_skips_occupied_monday(self):
        tz = datetime.timezone.utc
        occupied = datetime.datetime(2099, 6, 22, 9, tzinfo=tz)
        plan = podbean.episode_plan_from_podbean_response(
            {
                "episodes": [
                    {
                        "title": "#104 - Published",
                        "status": "publish",
                        "publish_time": int(occupied.timestamp()),
                    }
                ]
            },
            local_tz=tz,
        )
        self.assertEqual(
            podbean.next_available_monday(
                plan,
                now=datetime.datetime(2099, 6, 22, 10, tzinfo=tz),
            ),
            datetime.datetime(2099, 6, 29, 11, tzinfo=tz),
        )

    def test_prompt_publish_action_defaults_to_schedule(self):
        tz = datetime.timezone.utc
        plan = podbean.episode_plan_from_podbean_response({}, local_tz=tz)
        with redirect_stdout(StringIO()):
            schedule = podbean.prompt_publish_action(
                plan,
                input_func=lambda: "",
                now=datetime.datetime(2099, 6, 22, 10, tzinfo=tz),
            )
        self.assertEqual(
            schedule.podbean_datetime,
            datetime.datetime(2099, 6, 22, 11, tzinfo=tz),
        )

    def test_prompt_publish_action_accepts_publish_now(self):
        tz = datetime.timezone.utc
        plan = podbean.episode_plan_from_podbean_response({}, local_tz=tz)
        with redirect_stdout(StringIO()):
            schedule = podbean.prompt_publish_action(
                plan,
                input_func=lambda: "p",
                now=datetime.datetime(2099, 6, 22, 10, tzinfo=tz),
            )
        self.assertIsNone(schedule)


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


class TestCodexRunner(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("episode_pipeline.shutil.which", return_value="/bin/codex"))
        self.enterContext(patch.object(episode_pipeline, "CODEX_MODEL", "test-model"))
        self.enterContext(patch.object(episode_pipeline, "CODEX_TIMEOUT_S", 1234))

    def test_read_only_invocation_preserves_both_stdin_modes_and_cleans_output(self):
        def succeed(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_text(" result \n", encoding="utf-8")
            return types.SimpleNamespace(returncode=0, stderr="")

        for stdin_text in ("", "article body"):
            with self.subTest(stdin_text=stdin_text), patch(
                "episode_pipeline.subprocess.run", side_effect=succeed,
            ) as run:
                self.assertEqual(episode_pipeline.run_codex("prompt", stdin_text), "result")
                cmd = run.call_args.args[0]
                self.assertEqual(cmd[:2], ["codex", "exec"])
                self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")
                self.assertEqual(cmd[cmd.index("-C") + 1], episode_pipeline.REPO_ROOT)
                self.assertEqual(cmd[cmd.index("--model") + 1], "test-model")
                self.assertNotIn("--full-auto", cmd)
                self.assertNotIn("--add-dir", cmd)
                self.assertEqual(cmd[-1], "prompt" if stdin_text else "-")
                self.assertEqual(run.call_args.kwargs["input"], stdin_text or "prompt")
                self.assertEqual(run.call_args.kwargs["timeout"], 1234)
                self.assertFalse(Path(cmd[cmd.index("-o") + 1]).exists())

    def test_timeout_stops_without_printing_prompt_and_removes_partial_output(self):
        private_prompt = "private editorial guidance"

        def time_out(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_text("partial answer", encoding="utf-8")
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

        output = StringIO()
        with patch("episode_pipeline.subprocess.run", side_effect=time_out) as run:
            with redirect_stdout(output), redirect_stderr(output), self.assertRaises(SystemExit) as error:
                episode_pipeline.run_codex(private_prompt, "article")
        self.assertEqual(error.exception.code, 1)
        self.assertIn("timed out after 1234s", output.getvalue())
        self.assertIn("resume from checkpoints", output.getvalue())
        self.assertNotIn(private_prompt, output.getvalue())
        cmd = run.call_args.args[0]
        self.assertFalse(Path(cmd[cmd.index("-o") + 1]).exists())

    def test_failed_or_empty_response_stops_and_cleans_output(self):
        for returncode, message in ((2, "Codex failed"), (0, "empty response")):
            with self.subTest(returncode=returncode), patch(
                "episode_pipeline.subprocess.run",
                return_value=types.SimpleNamespace(returncode=returncode, stderr=""),
            ) as run:
                output = StringIO()
                with redirect_stdout(output), self.assertRaises(SystemExit) as error:
                    episode_pipeline.run_codex("prompt")
                self.assertEqual(error.exception.code, 1)
                self.assertIn(message, output.getvalue())
                cmd = run.call_args.args[0]
                self.assertFalse(Path(cmd[cmd.index("-o") + 1]).exists())

    def test_previous_review_path_is_resolved_before_codex_changes_root(self):
        relative_path = "out/episode001-review-1.md"
        with patch("episode_pipeline.run_codex", return_value="GOOD_TO_GO") as run:
            with redirect_stdout(StringIO()):
                episode_pipeline.review_with_codex("article", relative_path)
        self.assertIn(os.path.abspath(relative_path), run.call_args.args[0])


TURNS = [
    {"speaker": "A", "start": 0.0, "end": 60.0, "text": "Welcome to DevSecOps Talks."},
    {"speaker": "B", "start": 60.0, "end": 120.0, "text": "Thanks for having me."},
]


class TestPodbeanPublishingFlow(unittest.TestCase):
    UPLOADS = ("upload_cover_to_r2", "upload_file_to_podbean", "create_podbean_episode",
               "upload_to_youtube", "write_episode_markdown", "schedule_episode_announcement")

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.audio = self.root / "recording.mp3"
        self.audio.write_bytes(b"audio")
        self.enterContext(patch.object(podbean, "OUT_DIR", str(self.root)))
        self.enterContext(patch.dict(os.environ, {
            "PODBEAN_CLIENT_ID": "test-id", "PODBEAN_CLIENT_SECRET": "test-secret",
        }))
        self.enterContext(redirect_stdout(StringIO()))
        self.errors = self.enterContext(redirect_stderr(StringIO()))
        with patch.object(sys, "argv", ["podbean.py", "--episode-number", "1"]):
            self.args = podbean.parse_args()
        self.args.guidance = ""
        self.args.title = "Title"
        self.args.description = "Description"
        self.args.skip_youtube_upload = True
        self.schedule = podbean.publish_schedule_from_datetime(
            datetime.datetime(2099, 7, 1, 11, tzinfo=datetime.timezone.utc), "test",
        )
        self.mocks = {}
        for name, result in {
            "get_podbean_auth_token": "token",
            "get_podbean_episodes": {"episodes": []},
            "validate_or_bind_checkpoint_source": None,
            "require_publishing_prerequisites": None,
            "load_or_transcribe": TURNS,
            "confirm_speakers": ({"A": "Mattias Hemmingsson"}, TURNS),
            "identify_guests": (
                {"status": "no_guests", "guests": [], "hosts_present": ["Mattias Hemmingsson"]},
                {"A": "Mattias Hemmingsson", "B": "Jane Doe"},
            ),
            "load_reference_text": "",
            "correct_transcript": TURNS,
            "generate_article": "article",
            "load_or_generate_chapters": "",
            "load_or_generate_metadata": {"subtitle": "Subtitle", "youtube_title": "Hook"},
            "draw_cover": str(self.root / "episode001-cover.png"),
            "cover_public_url": "https://r2.example/covers/001-abc.png",
            "prompt_publish_action": self.schedule,
            "approve_episode_announcement": None,
            "upload_cover_to_r2": "https://r2.example/covers/001-abc.png",
            "get_podbean_upload_link": {"presigned_url": "https://example.test/audio", "file_key": "audio"},
            "upload_file_to_podbean": None,
            "create_podbean_episode": {"episode": {"id": "episode-id", "status": "draft"}},
            "upload_to_youtube": None,
            "write_episode_markdown": "episode.md",
            "schedule_episode_announcement": None,
        }.items():
            self.mocks[name] = self.enterContext(patch.object(podbean, name, return_value=result))

    def _confirm_schedule(self):
        self.mocks["create_podbean_episode"].return_value = {"episode": {
            "id": "episode-id", "status": "future", "media_url": "https://example.test/ep.mp3",
            "publish_time": self.schedule.podbean_timestamp,
        }}

    def assert_nothing_uploaded(self):
        for name in self.UPLOADS:
            self.mocks[name].assert_not_called()

    def test_article_with_disallowed_html_stops_before_any_upload(self):
        self.mocks["generate_article"].return_value = "## A {#a}\n<iframe src=x></iframe>"
        with self.assertRaisesRegex(podbean.PipelineStop, "tag not allowed: <iframe src=x>") as stop:
            podbean.process_audio(str(self.audio), self.args)
        self.assertTrue(stop.exception.checkpoint.endswith("episode001-article.md"))
        self.assert_nothing_uploaded()

    def test_steps_run_in_order_and_nothing_asks_after_the_first_upload(self):
        self._confirm_schedule()
        calls = []
        uploaded = []
        prompts_after_upload = []
        for name, mock in self.mocks.items():
            mock.side_effect = (lambda n, m: lambda *a, **k: (
                calls.append(n), uploaded.append(n) if n in self.UPLOADS else None, m.return_value)[-1])(name, mock)

        def fake_input(*_args):
            if uploaded:
                prompts_after_upload.append(calls[-1])
            return ""

        self.args.guidance = None  # asks for guidance, so input() is exercised
        with patch("builtins.input", side_effect=fake_input) as ask:
            podbean.process_audio(str(self.audio), self.args)
        ask.assert_called()
        self.assertEqual(prompts_after_upload, [])
        order = [name for name in (
            "load_or_transcribe", "confirm_speakers", "identify_guests",
            "correct_transcript", "load_or_generate_chapters", "generate_article", "load_or_generate_metadata",
            "draw_cover", "prompt_publish_action", "approve_episode_announcement", "upload_cover_to_r2",
            "create_podbean_episode", "write_episode_markdown", "schedule_episode_announcement",
        )]
        self.assertEqual([c for c in calls if c in order], order)

    def test_corrected_turns_named_by_voice_and_guest_reach_the_later_steps(self):
        self._confirm_schedule()
        podbean.process_audio(str(self.audio), self.args)
        correct_kwargs = self.mocks["correct_transcript"].call_args.kwargs
        self.assertEqual(correct_kwargs["speaker_names"], {"A": "Mattias Hemmingsson", "B": "Jane Doe"})
        guest_args = self.mocks["identify_guests"].call_args.args
        self.assertEqual(guest_args[2], {"A": "Mattias Hemmingsson"})
        self.assertIs(self.mocks["load_or_generate_chapters"].call_args.args[1], TURNS)
        article_kwargs = self.mocks["generate_article"].call_args.kwargs
        self.assertEqual((article_kwargs["title"], article_kwargs["teaser"]), ("Title", "Description"))

    def test_announcement_is_approved_for_the_predicted_page_and_cover(self):
        self._confirm_schedule()
        podbean.process_audio(str(self.audio), self.args)
        args = self.mocks["approve_episode_announcement"].call_args.args
        self.assertTrue(args[2].startswith("https://devsecops.fm/episodes/001-"))
        self.assertEqual(args[7], self.schedule.podbean_datetime)
        self.assertEqual(args[9], "https://r2.example/covers/001-abc.png")
        page_kwargs = self.mocks["write_episode_markdown"].call_args.kwargs
        self.assertEqual(page_kwargs["image"], "https://r2.example/covers/001-abc.png")
        self.assertEqual(self.mocks["schedule_episode_announcement"].call_args.args[4],
                         "https://r2.example/covers/001-abc.png")

    def test_unconfirmed_schedule_stops_before_youtube_and_keeps_upload_checkpoint(self):
        with self.assertRaisesRegex(podbean.PipelineStop, "did not confirm scheduled publication") as stop:
            podbean.process_audio(str(self.audio), self.args)
        self.assertTrue(stop.exception.checkpoint.endswith("episode001-podbean-upload.json"))
        create_kwargs = self.mocks["create_podbean_episode"].call_args.kwargs
        self.assertEqual(create_kwargs["status"], "future")
        self.assertEqual(create_kwargs["publish_timestamp"], self.schedule.podbean_timestamp)
        self.assertTrue((self.root / "episode001-podbean-upload.json").exists())
        self.mocks["upload_to_youtube"].assert_not_called()
        self.mocks["write_episode_markdown"].assert_not_called()

    def test_unauthorized_audio_upload_stops_the_run(self):
        self.mocks["get_podbean_upload_link"].return_value = {"error": "invalid_token"}
        with self.assertRaisesRegex(podbean.PipelineStop, "did not authorize the audio upload"):
            podbean.process_audio(str(self.audio), self.args)
        self.mocks["upload_file_to_podbean"].assert_not_called()
        self.mocks["create_podbean_episode"].assert_not_called()

    def test_rejected_episode_creation_stops_the_run(self):
        self.mocks["create_podbean_episode"].return_value = {"error": "invalid_request"}
        with self.assertRaisesRegex(podbean.PipelineStop, "Podbean rejected episode creation"):
            podbean.process_audio(str(self.audio), self.args)
        self.mocks["upload_to_youtube"].assert_not_called()

    def test_immediate_release_records_the_approved_release_time(self):
        self.mocks["prompt_publish_action"].return_value = None
        self.mocks["create_podbean_episode"].return_value = {"episode": {"id": "episode-id", "status": "publish"}}
        with patch.object(podbean, "record_announcement_eligibility") as record:
            podbean.process_audio(str(self.audio), self.args)
        approved_release = self.mocks["approve_episode_announcement"].call_args.args[7]
        self.assertIsNotNone(approved_release)
        self.assertIs(record.call_args.args[1], approved_release)

    def test_existing_draft_stops_before_publishing_or_creating_duplicate(self):
        for timestamp in (1, self.schedule.podbean_timestamp):
            with self.subTest(timestamp=timestamp):
                self.mocks["get_podbean_episodes"].return_value = {"episodes": [{
                    "id": "existing-id", "episode_number": 1,
                    "status": "draft", "publish_time": timestamp,
                }]}
                with self.assertRaisesRegex(podbean.PipelineStop, "still a draft"):
                    podbean.process_audio(str(self.audio), self.args)
                self.mocks["prompt_publish_action"].assert_not_called()
                self.mocks["generate_article"].assert_not_called()
                self.assert_nothing_uploaded()

    def test_confirmed_schedule_completes_and_clears_audio_upload_checkpoint(self):
        self._confirm_schedule()
        podbean.process_audio(str(self.audio), self.args)
        self.assertFalse((self.root / "episode001-podbean-upload.json").exists())
        self.assertTrue((self.root / "episode001-announcement-eligible.json").exists())
        page_kwargs = self.mocks["write_episode_markdown"].call_args.kwargs
        self.assertEqual(page_kwargs["publish_datetime"], self.schedule.podbean_datetime)

    def test_existing_scheduled_episode_resumes_without_duplicate_or_new_prompt(self):
        self.mocks["get_podbean_episodes"].return_value = {"episodes": [{
            "id": "existing-id", "episode_number": 1, "status": "future",
            "publish_time": self.schedule.podbean_timestamp,
        }]}
        podbean.process_audio(str(self.audio), self.args)
        self.mocks["prompt_publish_action"].assert_not_called()
        self.mocks["upload_file_to_podbean"].assert_not_called()
        self.mocks["create_podbean_episode"].assert_not_called()
        # No release from this run: only an earlier eligibility record could announce it.
        self.assertIsNone(self.mocks["approve_episode_announcement"].call_args.args[7])
        page_kwargs = self.mocks["write_episode_markdown"].call_args.kwargs
        self.assertEqual(page_kwargs["publish_datetime"], self.schedule.podbean_datetime)

    def test_existing_draft_allows_draft_only_work(self):
        self.mocks["get_podbean_episodes"].return_value = {"episodes": [{
            "id": "existing-id", "episode_number": 1, "status": "draft",
        }]}
        self.args.draft_only = True
        podbean.process_audio(str(self.audio), self.args)
        self.mocks["generate_article"].assert_called_once()
        self.mocks["require_publishing_prerequisites"].assert_not_called()
        self.mocks["load_or_generate_metadata"].assert_not_called()
        self.assert_nothing_uploaded()

    def test_missing_prerequisites_stop_before_any_question(self):
        self.mocks["require_publishing_prerequisites"].side_effect = podbean.PipelineStop("no video")
        with patch("builtins.input") as ask, self.assertRaisesRegex(podbean.PipelineStop, "no video"):
            podbean.process_audio(str(self.audio), self.args)
        ask.assert_not_called()
        self.mocks["load_or_transcribe"].assert_not_called()

    def test_codex_description_failure_stops_before_any_upload_and_preserves_title(self):
        self.args.description = None
        with ExitStack() as stack:
            stack.enter_context(patch("episode_pipeline.shutil.which", return_value="/bin/codex"))
            stack.enter_context(patch("episode_pipeline.subprocess.run", side_effect=
                subprocess.TimeoutExpired(cmd=["codex", "private prompt"], timeout=900)))
            with self.assertRaises((podbean.PipelineStop, SystemExit)):
                podbean.process_audio(str(self.audio), self.args)
        self.assertTrue((self.root / "episode001-title.txt").exists())
        self.assertFalse((self.root / "episode001-description.txt").exists())
        self.mocks["generate_article"].assert_not_called()
        self.assert_nothing_uploaded()

    def test_metadata_failure_stops_before_anything_remote(self):
        self.mocks["load_or_generate_metadata"].side_effect = podbean.PipelineStop("metadata")
        with self.assertRaises(podbean.PipelineStop):
            podbean.process_audio(str(self.audio), self.args)
        for name in ("draw_cover", "prompt_publish_action", "approve_episode_announcement"):
            self.mocks[name].assert_not_called()
        self.assert_nothing_uploaded()

    def test_cover_failure_stops_before_anything_remote(self):
        self.mocks["draw_cover"].side_effect = OSError("disk full")
        with self.assertRaisesRegex(podbean.PipelineStop, "disk full"):
            podbean.process_audio(str(self.audio), self.args)
        self.mocks["prompt_publish_action"].assert_not_called()
        self.assert_nothing_uploaded()

    def test_announcement_failure_after_uploads_stops_the_run(self):
        self._confirm_schedule()
        self.mocks["schedule_episode_announcement"].side_effect = podbean.AnnouncementStop("Buffer failed on x")
        with self.assertRaisesRegex(podbean.AnnouncementStop, "Buffer failed"):
            podbean.process_audio(str(self.audio), self.args)
        self.mocks["write_episode_markdown"].assert_called_once()

    def test_page_gets_metadata_cover_and_show_notes(self):
        self._confirm_schedule()
        podbean.process_audio(str(self.audio), self.args)
        page_kwargs = self.mocks["write_episode_markdown"].call_args.kwargs
        self.assertEqual(page_kwargs["subtitle"], "Subtitle")
        self.assertEqual(page_kwargs["audio_url"], "https://example.test/ep.mp3")
        self.assertEqual(page_kwargs["readtime"], "1 min read")
        content = self.mocks["create_podbean_episode"].call_args.args[2]
        self.assertIn("https://devsecops.fm/episodes/001/", content)


class TestStepInputRecord(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.base = str(self.root / "episode001")
        self.enterContext(redirect_stdout(StringIO()))

    def touch(self, *suffixes):
        for suffix in suffixes:
            Path(f"{self.base}{suffix}").write_text("x", encoding="utf-8")

    def exists(self, suffix):
        return Path(f"{self.base}{suffix}").exists()

    def test_step_with_no_entry_is_rebuilt_with_every_later_step(self):
        self.touch("-turns.json", "-guests.json", "-title.txt", "-article.md", "-youtube-url.txt")
        podbean.refresh_checkpoints(self.base, "guests", "inputs")
        self.assertTrue(self.exists("-turns.json"))
        for suffix in ("-guests.json", "-title.txt", "-article.md"):
            self.assertFalse(self.exists(suffix), suffix)
        # Upload markers are remote state and never discarded.
        self.assertTrue(self.exists("-youtube-url.txt"))

    def test_unchanged_inputs_keep_the_checkpoints(self):
        podbean.refresh_checkpoints(self.base, "title", "chapters", "transcript")
        self.touch("-title.txt", "-draft-v2.md")
        podbean.refresh_checkpoints(self.base, "title", "chapters", "transcript")
        self.assertTrue(self.exists("-title.txt"))
        self.assertTrue(self.exists("-draft-v2.md"))

    def test_changed_inputs_discard_the_step_and_later_entries(self):
        podbean.refresh_checkpoints(self.base, "chapters", ["turns"])
        podbean.refresh_checkpoints(self.base, "title", "chapters")
        self.touch("-chapters-generated.txt", "-title.txt", "-metadata.json")
        podbean.refresh_checkpoints(self.base, "chapters", ["other turns"])
        record = json.loads(Path(f"{self.base}-inputs.json").read_text())
        self.assertEqual(sorted(record), ["chapters"])
        for suffix in ("-chapters-generated.txt", "-title.txt", "-metadata.json"):
            self.assertFalse(self.exists(suffix), suffix)

    def test_unreadable_record_stops(self):
        Path(f"{self.base}-inputs.json").write_text("[", encoding="utf-8")
        with self.assertRaises(podbean.PipelineStop):
            podbean.refresh_checkpoints(self.base, "title", "x")


class TestIdentifyGuests(unittest.TestCase):
    TURNS = [
        {"speaker": "A", "start": 0, "end": 60, "text": "Welcome."},
        {"speaker": "B", "start": 60, "end": 180, "text": "I work on supply chain security."},
        {"speaker": "C", "start": 180, "end": 200, "text": "Thanks."},
    ]
    HOSTS = {"A": "Mattias Hemmingsson"}

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.base = str(self.root / "episode001")
        self.enterContext(redirect_stdout(StringIO()))
        self.research = self.enterContext(patch.object(
            podbean, "research_guests",
            side_effect=lambda people, *a, **k: episode_pipeline.operator_guest_context(people, {}),
        ))

    def identify(self, answers, turns=None):
        replies = iter(answers)
        return podbean.identify_guests(
            self.base, turns or self.TURNS[:2], self.HOSTS, "", "", input_func=lambda: next(replies))

    def test_episode_without_guests_asks_nothing(self):
        context, names = podbean.identify_guests(
            self.base, self.TURNS[:1], self.HOSTS, "", "", input_func=self.fail)
        self.assertEqual(context["guests"], [])
        self.assertEqual(context["hosts_present"], ["Mattias Hemmingsson"])
        self.assertEqual(names, self.HOSTS)
        self.research.assert_not_called()

    def test_operator_names_a_guest_research_never_found(self):
        context, names = self.identify(["Jane Doe, CTO at Acme", ""])
        self.assertEqual(podbean.guest_full_names(context), ["Jane Doe"])
        self.assertEqual(names, {"A": "Mattias Hemmingsson", "B": "Jane Doe"})
        people = self.research.call_args.args[0]
        self.assertEqual(people, [{"name": "Jane Doe", "hint": "CTO at Acme", "labels": ["B"]}])

    def test_same_name_for_two_labels_is_one_guest(self):
        context, names = self.identify(["Jane Doe", "jane doe, Acme", ""], turns=self.TURNS)
        self.assertEqual(podbean.guest_full_names(context), ["Jane Doe"])
        self.assertEqual((names["B"], names["C"]), ("Jane Doe", "Jane Doe"))

    def test_host_name_names_the_label_as_that_host(self):
        context, names = self.identify(["andrey"])
        self.assertEqual(names["B"], "Andrey Devyatkin")
        self.assertEqual(context["guests"], [])
        self.assertIn("Andrey Devyatkin", context["hosts_present"])

    def test_rerun_reuses_the_answers_and_the_research(self):
        first = self.identify(["Jane Doe", ""])
        again = self.identify([""])
        self.assertEqual(again[1], first[1])
        self.assertEqual(podbean.guest_full_names(again[0]), ["Jane Doe"])
        self.assertEqual(self.research.call_count, 1)

    def test_changed_answer_discards_the_transcript_and_later_steps(self):
        self.identify(["Jane Doe", ""])
        podbean.refresh_checkpoints(self.base, "transcript", "turns")
        Path(f"{self.base}-turns-corrected.json").write_text("[]", encoding="utf-8")
        context, _ = self.identify(["new", "John Roe", ""])
        self.assertEqual(podbean.guest_full_names(context), ["John Roe"])
        self.assertFalse(Path(f"{self.base}-turns-corrected.json").exists())

    def test_correction_looks_that_guest_up_again(self):
        self.identify(["Jane Doe", "1 she runs security at Globex", ""])
        self.assertEqual(self.research.call_count, 2)
        self.assertEqual(self.research.call_args.args[0][0]["hint"], "she runs security at Globex")

    def test_no_answer_stops(self):
        def eof():
            raise EOFError
        with self.assertRaises(podbean.PipelineStop):
            podbean.identify_guests(self.base, self.TURNS, self.HOSTS, "", "", input_func=eof)


class TestOperatorGuestContext(unittest.TestCase):
    PEOPLE = [{"name": "Jane Doe", "hint": "", "labels": ["B"]}]

    def test_research_cannot_add_or_drop_a_guest(self):
        research = {"guests": [
            {"full_name": "Jane Doe", "x_handle": "@janed", "company": "Acme"},
            {"full_name": "Bob Mentioned", "company": "Elsewhere"},
        ]}
        context = episode_pipeline.operator_guest_context(self.PEOPLE, research)
        self.assertEqual(podbean.guest_full_names(context), ["Jane Doe"])
        self.assertEqual((context["guests"][0]["x_handle"], context["guests"][0]["company"]), ("janed", "Acme"))
        self.assertEqual(episode_pipeline.operator_guest_context(self.PEOPLE, {})["guests"][0]["full_name"], "Jane Doe")

    def test_operator_spelling_wins_over_research(self):
        context = episode_pipeline.operator_guest_context(
            self.PEOPLE, {"guests": [{"full_name": "Jane A. Doe", "role": "CTO"}]})
        self.assertEqual(context["guests"][0]["full_name"], "Jane Doe")
        self.assertEqual(context["guests"][0]["role"], "CTO")

    def test_failed_research_credits_the_guest_in_plain_text(self):
        with patch.object(episode_pipeline, "run_claude", side_effect=RuntimeError("down")), \
                redirect_stdout(StringIO()):
            context = episode_pipeline.research_guests(self.PEOPLE, "transcript")
        self.assertEqual(podbean.guest_full_names(context), ["Jane Doe"])
        self.assertEqual(context["guests"][0]["x_handle"], "")


class TestPublishingPrerequisites(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.audio = self.root / "ep.mp3"
        self.audio.write_bytes(b"a")
        self.base = str(self.root / "episode001")
        with patch.object(sys, "argv", ["podbean.py"]):
            self.args = podbean.parse_args()
        self.enterContext(patch.dict(os.environ, {"UPLOAD_POST_API_KEY": "k", "UPLOAD_POST_USER": "u"}))
        self.enterContext(patch.object(podbean, "require_cover_client", return_value=object()))
        self.lifecycle = self.enterContext(patch.object(podbean, "check_cover_lifecycle"))
        self.buffer = self.enterContext(patch.object(podbean, "preflight_buffer"))

    def check(self, existing=None):
        podbean.require_publishing_prerequisites(self.args, str(self.audio), self.base, existing)

    def test_all_present_passes(self):
        (self.root / "ep.mp4").write_bytes(b"v")
        self.check()
        self.buffer.assert_called_once()

    def test_every_missing_piece_is_named_at_once(self):
        os.environ.pop("UPLOAD_POST_USER")
        self.lifecycle.side_effect = podbean.R2CoverError("rule tmp could expire covers/")
        self.buffer.side_effect = podbean.AnnouncementStop("Threads: no channel id")
        with self.assertRaises(podbean.PipelineStop) as stop:
            self.check()
        message = str(stop.exception)
        for part in ("UPLOAD_POST_USER", "no video for ep.mp3", "could expire covers/", "Threads"):
            self.assertIn(part, message)

    def test_finished_youtube_upload_needs_no_video_or_keys(self):
        os.environ.pop("UPLOAD_POST_API_KEY")
        Path(f"{self.base}-youtube-url.txt").write_text("https://www.youtube.com/embed/x\n", encoding="utf-8")
        self.check()

    def test_old_episode_without_eligibility_needs_no_buffer(self):
        self.args.skip_youtube_upload = True
        self.check(existing={"id": "x"})
        self.buffer.assert_not_called()


class TestStops(unittest.TestCase):
    def test_missing_cli_is_named_and_grok_is_not_needed_for_drafts(self):
        which = lambda tool: None if tool == "grok" else f"/bin/{tool}"  # noqa: E731
        with self.assertRaisesRegex(podbean.PipelineStop, "grok"):
            podbean.require_tools(which=which)
        with patch.object(podbean, "resolve_cli"), patch.object(podbean.voice_match, "load_host_voices"):
            podbean.require_tools(draft_only=True, which=which)

    def test_stale_voice_prints_stop_up_front(self):
        error = podbean.voice_match.VoicePrintError("built with another pin")
        with patch.object(podbean, "resolve_cli"), \
                patch.object(podbean.voice_match, "load_host_voices", side_effect=error):
            with self.assertRaisesRegex(podbean.PipelineStop, "another pin"):
                podbean.require_tools(which=lambda tool: "/bin/x")

    def test_main_prints_a_stop_once_and_exits_1(self):
        err = StringIO()
        with patch.object(sys, "argv", ["podbean.py", "-f", "ep.mp3"]), \
                patch.object(podbean, "require_tools"), \
                patch.object(podbean, "process_audio",
                             side_effect=podbean.PipelineStop("Buffer says no", checkpoint="out/x.json")), \
                redirect_stderr(err), self.assertRaises(SystemExit) as exit_:
            podbean.main()
        self.assertEqual(exit_.exception.code, 1)
        self.assertIn("Error: Buffer says no", err.getvalue())
        self.assertIn("Checkpoint: out/x.json", err.getvalue())


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
