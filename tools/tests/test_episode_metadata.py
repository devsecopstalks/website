"""Chapters, metadata packaging, article style and page writing, with Codex mocked.

Run from repo: cd tools && uv run python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

import episode_metadata  # noqa: E402
import episode_pipeline  # noqa: E402
import podbean  # noqa: E402

TURNS = [
    {"speaker": "A", "start": 0.0, "end": 95.0, "text": "Welcome back to devsekovs talks. " + "word " * 200},
    {"speaker": "B", "start": 95.0, "end": 400.0, "text": "Matthias here, GitHub changed the OIDC sub claim."},
    {"speaker": "C", "start": 400.0, "end": 900.0, "text": "Renaming a repo breaks the trust policy."},
    {"speaker": "A", "start": 900.0, "end": 1210.0, "text": "And AWS may think you were hacked."},
]
CHAPTERS = "00:00 - Why OIDC beats static keys\n01:35 - GitHub's new sub claim\n06:40 - Renames break trust\n15:00 - AWS abuse tickets"
METADATA = {
    "subtitle": "A security fix that can lock you out of AWS.",
    "youtube_title": "Can a Repo Rename Get Your AWS Account Blocked?",
    "youtube_hook": "Renamed a repository and your deploys broke? GitHub changed the OIDC token.",
    "youtube_intro": "Andrey Devyatkin, Paulina Dubas and Mattias Hemmingsson get into the change.",
    "youtube_learn": ["Why the sub claim now carries IDs", "How renames break trust", "What to do on an abuse ticket"],
    "youtube_substance": "GitHub now puts immutable owner and repository IDs into the sub claim.",
    "youtube_comment_prompt": "Do you pin trust policies to repository IDs yet?",
    "youtube_hashtags": ["#DevSecOps", "#DevOps", "#CloudSecurity", "#GitHubActions", "#DevSecOpsTalks"],
    "podcast_hook": "A GitHub security change can break AWS deploys.",
    "podcast_who_what": "Andrey Devyatkin, Paulina Dubas and Mattias Hemmingsson cover OIDC & renames.",
    "podcast_learn": ["Why the sub claim changed", "How renames break trust", "How to answer AWS abuse tickets"],
}


class TestChapters(unittest.TestCase):
    def test_validator_accepts_youtube_rules(self):
        self.assertEqual(episode_metadata.validate_youtube_chapters(CHAPTERS, duration_s=1210), [])

    def test_validator_rejects_each_rule(self):
        cases = {
            "00:00 - A\n01:00 - B": "at least 3",
            "00:05 - A\n01:00 - B\n02:00 - C": "not 00:00",
            "00:00 - A\n02:00 - B\n01:00 - C": "is not after",
            "00:00 - A\n00:05 - B\n02:00 - C": "under 10s",
        }
        for text, needle in cases.items():
            with self.subTest(text=text):
                self.assertIn(needle, " ".join(episode_metadata.validate_youtube_chapters(text)))
        self.assertIn("past the end", " ".join(
            episode_metadata.validate_youtube_chapters(CHAPTERS, duration_s=600)))

    def test_parse_ignores_commentary_and_renders_hours(self):
        parsed = episode_metadata.parse_chapters("Here you go:\n- 00:00 - Intro topic\n1:02:03 - Late")
        self.assertEqual(parsed, [(0, "Intro topic"), (3723, "Late")])
        self.assertEqual(episode_metadata.format_timestamp(3723), "1:02:03")

    def test_turns_for_prompt_caps_long_turns(self):
        text = episode_metadata.turns_for_prompt(TURNS)
        first = text.splitlines()[0]
        self.assertTrue(first.startswith("[00:00] [A]: Welcome back"))
        self.assertLess(len(first), episode_metadata.CHAPTER_TURN_TEXT_CAP + 30)
        self.assertIn("[01:35] [B]:", text)

    def test_manual_chapters_win_and_invalid_manual_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "episode001")
            Path(f"{base}-chapters.txt").write_text(CHAPTERS, encoding="utf-8")
            with patch.object(episode_metadata, "run_codex") as codex, redirect_stdout(StringIO()):
                self.assertEqual(episode_metadata.load_or_generate_chapters(base, "a", TURNS), CHAPTERS)
            codex.assert_not_called()
            Path(f"{base}-chapters.txt").write_text("00:00 - only one", encoding="utf-8")
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit):
                episode_metadata.load_or_generate_chapters(base, "a", TURNS)

    def test_no_turns_omits_chapters_with_notice(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(episode_metadata, "run_codex") as codex:
            out = StringIO()
            with redirect_stdout(out):
                result = episode_metadata.load_or_generate_chapters(os.path.join(tmp, "e"), "a", None)
        self.assertEqual(result, "")
        self.assertIn("no chapters", out.getvalue())
        codex.assert_not_called()

    def test_invalid_proposal_cannot_be_accepted_and_skip_is_remembered(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "episode001")
            answers = iter(["", "s"])
            with patch.object(episode_metadata, "run_codex", return_value="00:10 - A\n01:00 - B"), \
                    redirect_stdout(StringIO()):
                result = episode_metadata.load_or_generate_chapters(
                    base, "a", TURNS, input_func=lambda: next(answers))
                self.assertEqual(result, "")
                # A later run keeps the operator's skip instead of asking again.
                self.assertEqual(episode_metadata.load_or_generate_chapters(base, "a", TURNS), "")


class TestMetadata(unittest.TestCase):
    def test_validate_requires_guest_names_and_counts(self):
        guests = ["Jane Doe"]
        errors = episode_metadata.validate_metadata(dict(METADATA, youtube_learn=["one"]), guests)
        self.assertTrue(any("youtube_learn" in e for e in errors))
        self.assertTrue(any("Jane Doe" in e for e in errors))
        self.assertEqual(episode_metadata.validate_metadata(METADATA), [])

    def test_extract_passes_schema_and_retries_once_on_bad_output(self):
        outputs = iter(["not json", json.dumps(METADATA)])
        with patch.object(episode_metadata, "run_codex", side_effect=lambda *a, **k: next(outputs)) as codex, \
                redirect_stdout(StringIO()):
            meta = episode_metadata.extract_metadata("Title", "Teaser", "article", "transcript")
        self.assertEqual(meta, METADATA)
        self.assertEqual(codex.call_args.kwargs["output_schema"], episode_metadata.METADATA_SCHEMA)
        self.assertIn("previous answer was rejected", codex.call_args.args[0])
        self.assertIn("--- TRANSCRIPT ---\ntranscript", codex.call_args.kwargs["stdin_text"])

    def test_checkpoint_reused_until_title_or_teaser_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "episode001")
            with patch.object(episode_metadata, "run_codex", return_value=json.dumps(METADATA)) as codex, \
                    redirect_stdout(StringIO()):
                for title in ("Title", "Title", "New title"):
                    episode_metadata.load_or_generate_metadata(base, title, "Teaser", "article", "t")
            self.assertEqual(codex.call_count, 2)
            self.assertTrue(Path(f"{base}-metadata.json").exists())

    def test_readtime(self):
        self.assertEqual(episode_metadata.readtime_for("word " * 2640), "12 min read")
        self.assertEqual(episode_metadata.readtime_for("short"), "1 min read")


class TestBuilders(unittest.TestCase):
    def test_hashtags_forced_to_house_slots(self):
        tags = episode_metadata.normalize_hashtags(["#AWS", "Git Hub", "#devsecops", "#AWS"])
        self.assertEqual(tags, ["#DevSecOps", "#AWS", "#GitHub", "#DevOps", "#DevSecOpsTalks"])

    def test_youtube_title_keeps_hook_and_number_within_limit(self):
        title = episode_metadata.build_youtube_title({"youtube_title": "word " * 40}, 110, "x")
        self.assertLessEqual(len(title), episode_metadata.YOUTUBE_TITLE_MAX_CHARS)
        self.assertTrue(title.endswith(" - DevSecOps Talks #110"))
        self.assertEqual(episode_metadata.build_youtube_title({}, 7, "Fallback"), "Fallback - DevSecOps Talks #7")

    def test_youtube_description_order_and_links(self):
        text = episode_metadata.build_youtube_description(METADATA, 110, CHAPTERS, {
            "guests": [{"full_name": "Jane Doe", "links": [
                {"type": "github", "url": "https://github.com/jane"},
                {"type": "linkedin", "url": "https://www.linkedin.com/in/jane/"}]}]})
        order = ["Renamed a repository", "What you will learn", "Andrey Devyatkin", "immutable owner",
                 "pin trust policies", "Timestamps:\n00:00 - Why OIDC", "https://devsecops.fm/episodes/110/",
                 "Jane Doe\nhttps://www.linkedin.com/in/jane/", "#DevSecOps #DevOps"]
        positions = [text.index(needle) for needle in order]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("\n\n\n", text)
        without = episode_metadata.build_youtube_description(METADATA, 110, "")
        self.assertNotIn("Timestamps:", without)
        self.assertIn("no chapters", episode_metadata.youtube_description_warnings(without, METADATA, ""))

    def test_podbean_show_notes_are_escaped_html(self):
        notes = episode_metadata.build_podbean_show_notes(METADATA, 110)
        self.assertTrue(notes.startswith("<p>A GitHub security change"))
        self.assertIn("OIDC &amp; renames", notes)
        self.assertIn("<ul><li>Why the sub claim changed</li>", notes)
        self.assertIn("https://devsecops.fm/episodes/110/", notes)


class TestArticleHelpers(unittest.TestCase):
    ARTICLE = "\n".join([
        "## The problem {#problem}", "Text.",
        "## Common questions, answered {#faq}",
        "### How do I fix it? {#faq-fix}", "Answer.",
        "### Why? {#faq-why}", "Answer.",
        "### When? {#faq-when}", "Answer.",
        "## Resources {#resources}", "- link",
    ])

    def test_extract_article_drops_preamble(self):
        with redirect_stdout(StringIO()):
            self.assertEqual(
                episode_pipeline.extract_article("Sure, here it is:\n\n" + self.ARTICLE),
                self.ARTICLE + "\n",
            )

    def test_style_warnings(self):
        self.assertEqual(episode_pipeline.article_style_warnings(self.ARTICLE), [])
        bad = (self.ARTICLE.replace("### When? {#faq-when}\nAnswer.\n", "").replace(" {#faq-why}", "")
               + "\n## Summary {#problem}\nA — B")
        warnings = " | ".join(episode_pipeline.article_style_warnings(bad))
        for needle in ("em dash", "heading without", "duplicate heading ids: problem",
                       "Summary", "2 common questions"):
            self.assertIn(needle, warnings)

    def test_prompts_inject_tone_of_voice(self):
        for prompt in (episode_pipeline.DRAFT_PROMPT, episode_pipeline.REVIEW_PROMPT, episode_pipeline.REVISE_PROMPT):
            self.assertNotIn("{{TONE}}", prompt)
            self.assertIn("Common questions, answered {#faq}", prompt)
            self.assertIn("Matthias", prompt)

    def test_legacy_article_is_set_aside_before_redrafting(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "episode001")
            for suffix in ("-article.md", "-draft.md", "-draft-v2.md", "-review-1.md"):
                Path(f"{base}{suffix}").write_text("## Summary {#summary}\nold", encoding="utf-8")
            with patch.object(episode_pipeline, "generate_draft", return_value=self.ARTICLE), \
                    patch.object(episode_pipeline, "review_with_codex", return_value=("GOOD_TO_GO", True)) as review, \
                    redirect_stdout(StringIO()):
                article = episode_pipeline.generate_article("transcript", base, "guest ctx", input_func=lambda: "")
            self.assertEqual(article, self.ARTICLE)
            self.assertTrue(Path(f"{base}-draft-v2.md.legacy").exists())
            self.assertEqual(review.call_args.kwargs["transcript"], "transcript")
            self.assertEqual(review.call_args.kwargs["editorial_guidance"], "guest ctx")

    def test_review_sends_transcript_and_guest_context(self):
        with patch.object(episode_pipeline, "run_codex", return_value="GOOD_TO_GO") as codex, \
                redirect_stdout(StringIO()):
            episode_pipeline.review_with_codex("draft", transcript="[A]: hi", editorial_guidance="## Guest Context")
        stdin = codex.call_args.kwargs["stdin_text"]
        self.assertIn("--- TRANSCRIPT ---\n[A]: hi", stdin)
        self.assertIn("## Guest Context", stdin)

    def test_run_codex_adds_output_schema(self):
        def succeed(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_text("{}", encoding="utf-8")
            return types.SimpleNamespace(returncode=0, stderr="")

        with patch("episode_pipeline.shutil.which", return_value="/bin/codex"), \
                patch("episode_pipeline.subprocess.run", side_effect=succeed) as run:
            episode_pipeline.run_codex("prompt", "stdin", output_schema="/schema.json")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--output-schema") + 1], "/schema.json")


class TestEpisodePage(unittest.TestCase):
    def setUp(self):
        self.dir = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(podbean, "EPISODES_DIR", self.dir))

    def write(self, title="New Title"):
        return podbean.write_episode_markdown(
            110, title, 'Teaser with "quotes".', "## The problem {#problem}\nBody.",
            "pb-id", "yt12345678a", subtitle="Sub", readtime="12 min read",
            image="/images/covers/110.png", audio_url="",
            publish_datetime=datetime.datetime(2026, 9, 14, 12, tzinfo=datetime.timezone.utc),
        )

    def test_new_page_front_matter_and_body_order(self):
        text = Path(self.write()).read_text(encoding="utf-8")
        self.assertIn('title: "#110 - New Title"', text)
        self.assertIn('description: "Teaser with \\"quotes\\"."', text)
        self.assertIn('image: "/images/covers/110.png"', text)
        self.assertIn('youtube_id: "yt12345678a"', text)
        self.assertNotIn("audio_url", text)
        body = text.split("\n---\n", 1)[1]
        order = ["Teaser with", "Discuss the episode", "<!--more-->", "{{< whats-in-this-post >}}",
                 "podbean pb-id", "{{< youtube yt12345678a >}}", "## The problem"]
        positions = [body.index(needle) for needle in order]
        self.assertEqual(positions, sorted(positions))

    def test_published_page_is_updated_in_place(self):
        old = Path(self.dir) / "110-can-broken-github-actions-get-your-aws-account-blocked-.md"
        old.write_text("\n".join([
            "---", 'title: "#110 - Old Title"', "date: 2026-09-14T12:00:00+01:00",
            "lastmod: 2026-09-14T12:00:00+01:00", "episode: 110", 'author: "DevSecOps Talks"',
            'participants: ["Paulina", "Mattias", "Andrey"]', "aliases:", '  - "/episodes/110/"',
            '  - "/old-alias/"', "---", "", "Old teaser", "", "## Summary {#summary}", "old",
        ]), encoding="utf-8")
        path = self.write(title="A Different Title")
        self.assertEqual(path, str(old))
        self.assertEqual(sorted(os.listdir(self.dir)), [old.name])
        text = old.read_text(encoding="utf-8")
        self.assertIn('title: "#110 - A Different Title"', text)
        self.assertIn("date: 2026-09-14T12:00:00+01:00", text)
        self.assertNotIn("lastmod: 2026-09-14T12:00:00+01:00", text)
        self.assertIn('  - "/old-alias/"', text)
        self.assertIn('subtitle: "Sub"', text)
        self.assertNotIn("## Summary", text)
        self.assertEqual(text.count("\ntitle:"), 1)


class TestPackagingIntegration(unittest.TestCase):
    """Turns -> chapter validator -> metadata -> YouTube description handed to upload."""

    def test_youtube_upload_receives_chapters_and_metadata(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        audio = root / "recording.mp3"
        audio.write_bytes(b"audio")
        video = root / "recording.mp4"
        video.write_bytes(b"video")
        self.enterContext(patch.object(podbean, "OUT_DIR", str(root)))
        self.enterContext(patch.dict(os.environ, {
            "PODBEAN_CLIENT_ID": "id", "PODBEAN_CLIENT_SECRET": "secret",
            "UPLOAD_POST_API_KEY": "key", "UPLOAD_POST_USER": "user",
        }))
        self.enterContext(redirect_stdout(StringIO()))
        self.enterContext(redirect_stderr(StringIO()))
        with patch.object(sys, "argv", ["podbean.py", "--episode-number", "1", "--youtube-no-r2-staging"]):
            args = podbean.parse_args()
        args.guidance, args.title, args.description = "", "Title", "Teaser"
        args.video = str(video)

        def fake_codex(prompt, stdin_text="", verbose=False, output_schema=None):
            if output_schema:
                return json.dumps(METADATA)
            self.assertIn("[01:35] [B]: Matthias here", stdin_text)
            return "Proposed chapters:\n" + CHAPTERS

        mocks = {}
        for name, result in {
            "get_podbean_auth_token": "token",
            "get_podbean_episodes": {"episodes": []},
            "validate_or_bind_checkpoint_source": None,
            "load_or_create_transcript": "transcript",
            "load_transcript_turns": TURNS,
            "_load_or_detect_guest_context": {"status": "no_guests", "guests": []},
            "generate_article": "## The problem {#problem}\nBody.",
            "generate_cover": "/images/covers/001.png",
            "prompt_publish_action": None,
            "get_podbean_upload_link": {"presigned_url": "https://example.test/a", "file_key": "k"},
            "upload_file_to_podbean": None,
            "create_podbean_episode": {"episode": {"id": "episode-id", "status": "publish"}},
            "upload_to_youtube": {"results": []},
            "status_to_youtube_embed_url": "https://www.youtube.com/embed/abcdefghijk",
            "write_episode_markdown": "episode.md",
        }.items():
            mocks[name] = self.enterContext(patch.object(podbean, name, return_value=result))
        self.enterContext(patch.object(episode_metadata, "run_codex", side_effect=fake_codex))
        self.enterContext(patch("builtins.input", return_value=""))

        podbean.process_audio(str(audio), args, None)

        upload_args = mocks["upload_to_youtube"].call_args.args
        self.assertEqual(upload_args[1], "Can a Repo Rename Get Your AWS Account Blocked? - DevSecOps Talks #1")
        description = upload_args[2]
        self.assertTrue(description.startswith(METADATA["youtube_hook"]))
        self.assertIn("Timestamps:\n" + CHAPTERS + "\n", description)
        self.assertTrue(description.rstrip().endswith("#DevSecOpsTalks"))
        self.assertEqual((root / "episode001-youtube-description.txt").read_text(encoding="utf-8"), description)
        self.assertEqual((root / "episode001-chapters-generated.txt").read_text(encoding="utf-8").strip(), CHAPTERS)
        self.assertIn("<li>How renames break trust</li>", mocks["create_podbean_episode"].call_args.args[2])


if __name__ == "__main__":
    unittest.main()
