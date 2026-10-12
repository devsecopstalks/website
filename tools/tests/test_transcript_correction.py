"""Transcript correction loop, title/teaser picks and the article frame, with Codex and Claude mocked.

Run from repo: cd tools && uv run python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

import episode_pipeline as ep  # noqa: E402

TURNS = [
    {"speaker": "A", "start": 2.32, "end": 5.12, "text": "Welcome to a new episode of Del Sego"},
    {"speaker": "B", "start": 5.36, "end": 10.48, "text": "Talks with Andrew"},
    {"speaker": "A", "start": 11.04, "end": 81.28, "text": "Uh so we are talking about knowledge."},
]
NAMES = {"A": "Mattias Hemmingsson", "B": "Andrey Devyatkin"}
GOOD_REWRITE = {"turns": [
    {"index": 1, "speaker": "Mattias Hemmingsson", "text": "Welcome to a new episode of DevSecOps"},
    {"index": 2, "speaker": "Andrey Devyatkin", "text": "Talks with Andrey"},
    {"index": 3, "speaker": "Mattias Hemmingsson", "text": "So we are talking about knowledge."},
]}


class FakeCodex:
    """Answers run_codex_json by schema, popping scripted answers; records each call."""

    def __init__(self, rewrites, reviews):
        self.rewrites, self.reviews, self.calls = list(rewrites), list(reviews), []

    def __call__(self, prompt, stdin_text, schema_file, checkpoint="", verbose=False):
        self.calls.append({"prompt": prompt, "stdin": stdin_text, "schema": schema_file})
        queue = self.reviews if schema_file == ep.TRANSCRIPT_REVIEW_SCHEMA else self.rewrites
        return queue.pop(0)


def run_correction(tmp, fake, answers=(), **kwargs):
    base = os.path.join(tmp, "episode112")
    replies = iter(answers)

    def reply():
        try:
            return next(replies)
        except StopIteration:
            raise EOFError from None

    with patch.object(ep, "run_codex_json", fake), redirect_stdout(StringIO()):
        turns = ep.correct_transcript(base, TURNS, {}, input_func=reply, **kwargs)
    return base, turns


class TestParsers(unittest.TestCase):
    def test_rewrite_must_return_exactly_the_expected_turns(self):
        self.assertEqual(ep.parse_rewritten_turns(GOOD_REWRITE, [1, 2, 3])[2]["text"], "Talks with Andrey")
        bad = {
            "count": {"turns": GOOD_REWRITE["turns"][:2]},
            "duplicate": {"turns": [GOOD_REWRITE["turns"][0]] * 3},
            "foreign index": {"turns": GOOD_REWRITE["turns"][:2] + [dict(GOOD_REWRITE["turns"][2], index=9)]},
            "no speaker": {"turns": GOOD_REWRITE["turns"][:2] + [dict(GOOD_REWRITE["turns"][2], speaker=" ")]},
            "no list": {"turns": "nope"},
        }
        for name, answer in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                ep.parse_rewritten_turns(answer, [1, 2, 3])

    def test_review_status_must_match_flags_and_scope(self):
        self.assertEqual(ep.parse_transcript_review({"status": "good", "turns": []}, [1]), {})
        self.assertEqual(
            ep.parse_transcript_review({"status": "issues", "turns": [{"index": 2, "problem": "x"}]}, [2]), {2: "x"}
        )
        for answer in (
            {"status": "good", "turns": [{"index": 1, "problem": "x"}]},
            {"status": "issues", "turns": []},
            {"status": "issues", "turns": [{"index": 3, "problem": "x"}]},
            {"status": "maybe", "turns": []},
        ):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                ep.parse_transcript_review(answer, [1, 2])


class TestCorrectTranscript(unittest.TestCase):
    def test_clean_pass_keeps_labels_and_times_and_writes_named_transcript(self):
        fake = FakeCodex([GOOD_REWRITE], [{"status": "good", "turns": []}])
        with tempfile.TemporaryDirectory() as tmp:
            base, turns = run_correction(tmp, fake, speaker_names=NAMES)
            self.assertEqual([t["label"] for t in turns], ["A", "B", "A"])
            self.assertEqual([(t["start"], t["end"]) for t in turns], [(t["start"], t["end"]) for t in TURNS])
            self.assertFalse(any(t["flagged"] for t in turns))
            self.assertEqual(
                Path(f"{base}.txt").read_text(encoding="utf-8").splitlines()[1],
                "Andrey Devyatkin: Talks with Andrey",
            )
            saved = json.loads(Path(f"{base}-turns-corrected.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, turns)

    def test_voice_names_override_the_rewriter(self):
        renamed = {"turns": [dict(t, speaker="Paulina Dubas") for t in GOOD_REWRITE["turns"]]}
        fake = FakeCodex([renamed], [{"status": "good", "turns": []}])
        with tempfile.TemporaryDirectory() as tmp:
            _, turns = run_correction(tmp, fake, speaker_names=NAMES)
        self.assertEqual([t["speaker"] for t in turns], ["Mattias Hemmingsson", "Andrey Devyatkin", "Mattias Hemmingsson"])

    def test_flagged_turn_is_revised_and_rereviewed_alone(self):
        flagged_first = dict(GOOD_REWRITE["turns"][1], text="Talks with Andrew")
        first = {"turns": [GOOD_REWRITE["turns"][0], flagged_first, GOOD_REWRITE["turns"][2]]}
        fake = FakeCodex(
            [first, {"turns": [GOOD_REWRITE["turns"][1]]}],
            [{"status": "issues", "turns": [{"index": 2, "problem": "Andrew -> Andrey"}]},
             {"status": "good", "turns": []}],
        )
        with tempfile.TemporaryDirectory() as tmp:
            _, turns = run_correction(tmp, fake, speaker_names=NAMES)
        self.assertEqual(turns[1]["text"], "Talks with Andrey")
        revision, second_review = fake.calls[2], fake.calls[3]
        self.assertIn("Reviewer: Andrew -> Andrey", revision["stdin"])
        self.assertIn("--- TURNS TO REVIEW ---\n2\n", second_review["stdin"])

    def test_cap_keep_marks_flagged_turns_unquotable(self):
        issue = {"status": "issues", "turns": [{"index": 3, "problem": "dropped a word"}]}
        fake = FakeCodex([GOOD_REWRITE] + [{"turns": [GOOD_REWRITE["turns"][2]]}] * 9, [issue] * 10)
        with tempfile.TemporaryDirectory() as tmp, patch.object(ep, "TRANSCRIPT_REVIEW_ROUNDS", 2), \
                patch.object(ep, "TRANSCRIPT_EXTENSION_ROUNDS", 1):
            base, turns = run_correction(tmp, fake, answers=["e", "s"])
            self.assertEqual(Path(f"{base}-transcript-review-limit.txt").read_text().strip(), "3")
        self.assertEqual([t["flagged"] for t in turns], [False, False, True])
        self.assertEqual(turns[2]["problem"], "dropped a word")
        self.assertEqual(sum(c["schema"] == ep.TRANSCRIPT_REVIEW_SCHEMA for c in fake.calls), 3)

    def test_cap_without_an_answer_stops(self):
        issue = {"status": "issues", "turns": [{"index": 3, "problem": "x"}]}
        fake = FakeCodex([GOOD_REWRITE], [issue])
        with tempfile.TemporaryDirectory() as tmp, patch.object(ep, "TRANSCRIPT_REVIEW_ROUNDS", 1):
            with self.assertRaises(ep.PipelineStop):
                run_correction(tmp, fake)
            self.assertFalse(Path(tmp, "episode112-turns-corrected.json").exists())

    def test_rerun_resumes_from_saved_rounds_and_final_file(self):
        fake = FakeCodex([GOOD_REWRITE], [{"status": "good", "turns": []}])
        with tempfile.TemporaryDirectory() as tmp:
            run_correction(tmp, fake)
            Path(tmp, "episode112-turns-corrected.json").unlink()
            idle = FakeCodex([], [])
            _, turns = run_correction(tmp, idle)
            self.assertEqual(idle.calls, [])
            self.assertEqual(turns[0]["text"], "Welcome to a new episode of DevSecOps")
            self.assertEqual(
                [os.path.basename(p) for p in ep.correction_checkpoints(os.path.join(tmp, "episode112"))],
                ["episode112-transcript-review-1.md", "episode112-transcript-rewrite-1.json",
                 "episode112-turns-corrected.json"],
            )

    def test_malformed_answer_is_retried_once_then_stops(self):
        short = {"turns": GOOD_REWRITE["turns"][:1]}
        fake = FakeCodex([short, GOOD_REWRITE], [{"status": "good", "turns": []}])
        with tempfile.TemporaryDirectory() as tmp:
            _, turns = run_correction(tmp, fake)
        self.assertIn("previous answer was rejected", fake.calls[1]["prompt"])
        self.assertEqual(len(turns), 3)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ep.PipelineStop):
            run_correction(tmp, FakeCodex([short, short], []))

    def test_context_carries_reference_text_and_known_speakers(self):
        fake = FakeCodex([GOOD_REWRITE], [{"status": "good", "turns": []}])
        with tempfile.TemporaryDirectory() as tmp:
            run_correction(tmp, fake, reference_text="Riverside: DevSecOps Talks with Andrey", speaker_names=NAMES)
        stdin = fake.calls[0]["stdin"]
        self.assertIn("PROVIDED TRANSCRIPT (spelling reference only", stdin)
        self.assertIn("Riverside: DevSecOps Talks with Andrey", stdin)
        self.assertIn("A = Mattias Hemmingsson", stdin)
        self.assertIn("[2] [00:05] [B]: Talks with Andrew", stdin)

    def test_no_turns_stops(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ep.PipelineStop):
            ep.correct_transcript(os.path.join(tmp, "e"), [], {})


class TestPicksAndFrame(unittest.TestCase):
    def test_title_options_read_chapters_and_transcript(self):
        answers = iter(["2"])
        with patch.object(ep, "run_codex", return_value="1. One\n2. Two with Jane Doe") as codex, \
                redirect_stdout(StringIO()):
            title = ep.pick_title("00:00 - Intro", "Jane Doe: hi", input_func=lambda: next(answers))
        self.assertEqual(title, "Two with Jane Doe")
        stdin_text = codex.call_args.kwargs["stdin_text"]
        self.assertIn("--- CHAPTERS ---\n00:00 - Intro", stdin_text)
        self.assertIn("--- TRANSCRIPT ---\nJane Doe: hi", stdin_text)

    def test_teaser_regenerates_with_guidance(self):
        answers = iter(["r", "shorter", "c", "My teaser"])
        with patch.object(ep, "run_codex", return_value="1. A") as codex, redirect_stdout(StringIO()):
            teaser = ep.pick_description("", "Jane: hi", input_func=lambda: next(answers))
        self.assertEqual(teaser, "My teaser")
        self.assertIn("Additional guidance: shorter", codex.call_args.args[0])
        self.assertNotIn("CHAPTERS", codex.call_args.kwargs["stdin_text"])

    def test_teaser_options_are_written_under_the_picked_title(self):
        options = "\n".join(f"{n}. [Style {n}] Teaser {n} with Jane Doe." for n in range(1, 13))
        answers = iter(["12"])
        out = StringIO()
        with patch.object(ep, "run_codex", return_value=options) as codex, redirect_stdout(out):
            teaser = ep.pick_description(
                "00:00 - Intro", "Jane Doe: hi", title="Picked title", input_func=lambda: next(answers))
        self.assertEqual(teaser, "Teaser 12 with Jane Doe.")
        self.assertIn("Enter a number (1-12)", out.getvalue())
        stdin_text = codex.call_args.kwargs["stdin_text"]
        self.assertTrue(stdin_text.startswith("--- TITLE ---\nPicked title\n"))
        self.assertLess(stdin_text.index("TITLE"), stdin_text.index("--- CHAPTERS ---"))

    def test_title_choices_follow_the_options_present(self):
        options = "\n".join(f"{n}. [Style {n}] Title {n} with Jane Doe" for n in range(1, 13))
        answers = iter(["13", "11"])
        out = StringIO()
        with patch.object(ep, "run_codex", return_value=options) as codex, redirect_stdout(out):
            title = ep.pick_title("", "Jane: hi", input_func=lambda: next(answers))
        self.assertEqual(title, "Title 11 with Jane Doe")
        self.assertIn("Enter a number (1-12)", out.getvalue())
        self.assertEqual(codex.call_count, 2)
        self.assertNotIn("TITLE", codex.call_args.kwargs["stdin_text"])

    def test_draft_and_revision_carry_title_teaser_and_chapters(self):
        article = "## Problem {#problem}\n" + "x " * 300
        with patch.object(ep, "run_claude", return_value=article) as claude, redirect_stdout(StringIO()):
            ep.generate_draft("T: hi", title="The title", teaser="The teaser", chapters="00:00 - A")
            ep.revise_draft("T: hi", "draft", "fix it", title="The title", teaser="The teaser", chapters="00:00 - A")
        for call in claude.call_args_list:
            prompt = call.args[0]
            self.assertIn("--- EPISODE TITLE ---\nThe title", prompt)
            self.assertIn("--- TEASER ---\nThe teaser", prompt)
            self.assertIn("--- CHAPTERS ---\n00:00 - A", prompt)

    def test_codex_command_is_unchanged(self):
        with patch.object(ep, "CODEX_MODEL", "m"):
            self.assertEqual(
                ep.codex_base_cmd("/tmp/o", "/s.json"),
                ["codex", "exec", "--sandbox", "read-only", "-C", ep.REPO_ROOT, "--model", "m",
                 "-o", "/tmp/o", "--output-schema", "/s.json"],
            )


if __name__ == "__main__":
    unittest.main()
