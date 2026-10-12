import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import podbean  # noqa: E402
import transcribe_local as tl  # noqa: E402


def words(*specs):
    """Build wordTimings from (word, start, end) triples."""
    return [{"word": w, "startTime": s, "endTime": e} for w, s, e in specs]


def segments(*specs):
    """Build VBx-shaped segments from (speakerId, start, end) triples."""
    return [
        {"speakerId": spk, "startTimeSeconds": s, "endTimeSeconds": e}
        for spk, s, e in specs
    ]


class BuildTurnsTests(unittest.TestCase):
    def test_straddling_word_goes_to_the_speaker_it_overlaps_most(self):
        # 'shared' spans both segments: 0.3s of S1, 0.7s of S2. S2 must win, so
        # this fails if the assignment takes the first overlap rather than the max.
        asr = {"wordTimings": words(("hi", 0.0, 0.2), ("shared", 0.2, 1.2), ("bye", 1.2, 1.4))}
        dia = {"segments": segments(("S1", 0.0, 0.5), ("S2", 0.5, 1.4))}

        turns = tl.build_turns(asr, dia)

        self.assertEqual([t["speaker"] for t in turns], ["A", "B"])
        self.assertEqual(turns[0]["text"], "hi")
        self.assertEqual(turns[1]["text"], "shared bye")

    def test_speaker_index_zero_is_not_treated_as_missing(self):
        """sortformer uses int indices; 0 is falsy but a real speaker.

        Speaker 0 is sandwiched between two speaker-1 spans, and the words sit in
        the gaps as well as inside the spans, so the carry-forward branch runs. A
        falsy check there drops speaker 0 entirely and yields a single turn.
        """
        asr = {"wordTimings": words(
            ("one", 0.0, 0.5), ("zero", 2.0, 2.5), ("one_again", 4.0, 4.5),
        )}
        dia = {
            "segments": [
                {"speakerIndex": 1, "startTimeSeconds": 0.0, "endTimeSeconds": 0.5},
                {"speakerIndex": 0, "startTimeSeconds": 2.0, "endTimeSeconds": 2.5},
                {"speakerIndex": 1, "startTimeSeconds": 4.0, "endTimeSeconds": 4.5},
            ]
        }

        turns = tl.build_turns(asr, dia)

        self.assertEqual([t["speaker"] for t in turns], ["A", "B", "A"])
        self.assertEqual(turns[1]["text"], "zero")

    def test_nested_segment_is_found_however_far_back_it_starts(self):
        """A long enclosing turn must win even behind many short interjections.

        With a fixed-size lookback the enclosing segment falls out of the window
        and its words get misattributed to the interrupting speaker.
        """
        interjections = [("S2", 1.0 + i, 1.0 + i + 0.05) for i in range(40)]
        dia = {"segments": segments(("S1", 0.0, 100.0), *interjections)}
        # A word late in the monologue, in none of the interjections.
        asr = {"wordTimings": words(("late", 90.0, 90.5))}

        turns = tl.build_turns(asr, dia)

        self.assertEqual(turns[0]["speaker"], "A")

    def test_more_than_26_speakers_keep_valid_labels(self):
        segs = [(f"S{i}", i * 2.0, i * 2.0 + 1.0) for i in range(30)]
        asr = {"wordTimings": words(*[(f"w{i}", i * 2.0, i * 2.0 + 1.0) for i in range(30)])}

        turns = tl.build_turns(asr, {"segments": segments(*segs)})

        labels = [t["speaker"] for t in turns]
        self.assertEqual(labels[25], "Z")
        self.assertEqual(labels[26], "AA")
        self.assertEqual(labels[27], "AB")
        for label in labels:
            self.assertTrue(label.isalpha(), f"{label!r} is not a usable speaker label")

    def test_missing_segments_raises(self):
        asr = {"wordTimings": words(("a", 0.0, 0.5))}
        with self.assertRaises(RuntimeError) as ctx:
            tl.build_turns(asr, {"segments": []})
        self.assertIn("segments", str(ctx.exception))

    def test_totally_disjoint_timebases_raise_instead_of_inventing_one_speaker(self):
        """Filling every word would yield a plausible single-speaker transcript."""
        asr = {"wordTimings": words(("a", 0.0, 0.5), ("b", 1.0, 1.5))}
        dia = {"segments": segments(("S1", 9000.0, 9001.0))}

        with self.assertRaises(RuntimeError) as ctx:
            tl.build_turns(asr, dia)
        self.assertIn("do not line up", str(ctx.exception))

    def test_words_outside_any_segment_inherit_the_previous_speaker(self):
        asr = {"wordTimings": words(("In", 0.0, 0.5), ("gap", 5.0, 5.5), ("back", 10.0, 10.5))}
        dia = {"segments": segments(("S1", 0.0, 0.5), ("S1", 10.0, 10.5))}

        turns = tl.build_turns(asr, dia)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["text"], "In gap back")

    def test_leading_words_before_any_segment_get_the_first_speaker(self):
        asr = {"wordTimings": words(("Early", 0.0, 0.5), ("later", 10.0, 10.5))}
        dia = {"segments": segments(("S3", 10.0, 10.5))}

        turns = tl.build_turns(asr, dia)

        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["speaker"], "A")

    def test_turns_carry_timestamps_for_downstream_highlights(self):
        asr = {"wordTimings": words(("One", 1.25, 1.75), ("two", 1.75, 2.5))}
        dia = {"segments": segments(("S1", 1.0, 3.0))}

        turns = tl.build_turns(asr, dia)

        self.assertEqual(turns[0]["start"], 1.25)
        self.assertEqual(turns[0]["end"], 2.5)

    def test_missing_word_timings_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            tl.build_turns({"wordTimings": []}, {"segments": segments(("S1", 0.0, 1.0))})
        self.assertIn("wordTimings", str(ctx.exception))

    def test_speaker_labels_follow_first_appearance(self):
        asr = {"wordTimings": words(("a", 0.0, 0.5), ("b", 2.0, 2.5), ("c", 4.0, 4.5))}
        dia = {"segments": segments(("S9", 0.0, 0.5), ("S4", 2.0, 2.5), ("S9", 4.0, 4.5))}

        turns = tl.build_turns(asr, dia)

        self.assertEqual([t["speaker"] for t in turns], ["A", "B", "A"])


class SnapBoundariesTests(unittest.TestCase):
    def test_boundary_moves_to_the_sentence_end(self):
        # Diarization puts the change one word late: "code." belongs to the first
        # speaker, but lands on the second.
        w = words(
            ("write", 0.0, 0.4),
            ("code.", 0.4, 0.9),
            ("I", 1.6, 1.8),
            ("actually", 1.8, 2.4),
        )
        labels = ["S1", "S2", "S2", "S2"]

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(snapped, ["S1", "S1", "S2", "S2"])

    def test_boundary_does_not_cross_a_neighbouring_boundary(self):
        w = words(("a", 0.0, 0.1), ("b", 0.1, 0.2), ("c", 5.0, 5.1), ("d", 5.1, 5.2))
        labels = ["S1", "S2", "S3", "S3"]

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(snapped, ["S1", "S2", "S3", "S3"])
        self.assertEqual(len(snapped), len(w))

    def test_ties_do_not_drag_the_boundary_left(self):
        """Parakeet quantises timings, so most adjacent gaps are exactly 0.

        Every candidate scores the same here, so the boundary must stay where the
        diarizer put it. Picking the leftmost maximum instead moves it by the full
        clamp and misattributes four words.
        """
        w = words(*[(f"w{i}", i * 0.5, (i + 1) * 0.5) for i in range(20)])
        labels = ["S1"] * 10 + ["S2"] * 10

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(snapped, labels)

    def test_equal_pauses_are_broken_towards_the_original_boundary(self):
        w = words(*[(f"w{i}", i * 0.5, (i + 1) * 0.5) for i in range(20)])
        # Identical pauses before w6 and w10; the diarizer said w10.
        for idx in (6, 10):
            for k in range(idx, 20):
                w[k]["startTime"] += 0.4
                w[k]["endTime"] += 0.4
        labels = ["S1"] * 10 + ["S2"] * 10

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(snapped, labels)

    def test_a_marginally_better_split_does_not_override_the_diarizer(self):
        # Boundary at index 2. A neighbouring gap beats it by 0.01s -- noise, not
        # evidence -- so the diarizer's own boundary must stand.
        w = words(("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.2, 1.7), ("d", 1.88, 2.4))
        labels = ["S1", "S1", "S2", "S2"]

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(snapped, labels)

    def test_a_bigger_pause_wins_over_a_sentence_end(self):
        # Sentence end before w2 (gap 0.0 + bonus), much larger pause before w3.
        w = words(("a", 0.0, 0.5), ("b.", 0.5, 1.0), ("c", 1.0, 1.5), ("d", 4.0, 4.5))
        labels = ["S1", "S1", "S2", "S2"]

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(snapped, ["S1", "S1", "S1", "S2"])

    def test_sentence_end_breaks_a_tie_between_equal_pauses(self):
        # Equal 0.5s pauses before w1 and w2; only w1 follows a sentence end.
        w = words(("a.", 0.0, 0.5), ("b", 1.0, 1.5), ("c", 2.0, 2.5), ("d", 2.5, 3.0))
        labels = ["S1", "S1", "S2", "S2"]

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(snapped, ["S1", "S2", "S2", "S2"])

    def test_single_speaker_is_untouched(self):
        w = words(("a", 0.0, 0.1), ("b", 0.1, 0.2))
        self.assertEqual(tl._snap_boundaries(w, ["S1", "S1"]), ["S1", "S1"])

    def test_snapping_preserves_word_count(self):
        w = words(*[(f"w{i}.", i * 0.5, i * 0.5 + 0.4) for i in range(20)])
        labels = ["S1"] * 7 + ["S2"] * 6 + ["S3"] * 7

        snapped = tl._snap_boundaries(w, labels)

        self.assertEqual(len(snapped), len(w))


class FormatTurnsTests(unittest.TestCase):
    def test_matches_the_bracketed_speaker_convention(self):
        turns = [
            {"speaker": "A", "start": 0.0, "end": 1.0, "text": "Hello."},
            {"speaker": "B", "start": 1.0, "end": 2.0, "text": "Hi."},
        ]
        self.assertEqual(tl.format_turns(turns), "[A]: Hello.\n[B]: Hi.")


class ResolveCliTests(unittest.TestCase):
    def test_missing_binary_explains_how_to_build_it(self):
        with mock.patch.dict("os.environ", {"FLUIDAUDIO_CLI": ""}, clear=False):
            with mock.patch.object(tl, "FLUIDAUDIO_DIR", "/nonexistent/fluidaudio"):
                with self.assertRaises(RuntimeError) as ctx:
                    tl.resolve_cli()
        self.assertIn("do.sh", str(ctx.exception))

    def test_override_is_used_when_it_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "fluidaudiocli"
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.dict("os.environ", {"FLUIDAUDIO_CLI": str(binary)}, clear=False):
                self.assertEqual(tl.resolve_cli(), str(binary))

    def test_override_pointing_nowhere_is_rejected(self):
        with mock.patch.dict("os.environ", {"FLUIDAUDIO_CLI": "/nope/fluidaudiocli"}, clear=False):
            with self.assertRaises(RuntimeError) as ctx:
                tl.resolve_cli()
        self.assertIn("/nope/fluidaudiocli", str(ctx.exception))


class CliInvocationTests(unittest.TestCase):
    """The argv sent to fluidaudiocli is the whole contract with the models."""

    def _capture(self, fn, payload):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            out_flag = "--output-json" if "--output-json" in cmd else "--output"
            Path(cmd[cmd.index(out_flag) + 1]).write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(tl.subprocess, "run", side_effect=fake_run):
            fn()
        return calls[0]

    def test_asr_requests_word_timestamps_and_the_pinned_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "asr.json")
            cmd = self._capture(
                lambda: tl.run_asr("/bin/cli", "a.wav", out),
                {"wordTimings": [], "processingTimeSeconds": 1.0, "rtfx": 1.0},
            )

        self.assertIn("transcribe", cmd)
        self.assertIn("--word-timestamps", cmd)
        self.assertEqual(cmd[cmd.index("--model-version") + 1], tl.PARAKEET_MODEL_VERSION)
        self.assertEqual(tl.PARAKEET_MODEL_VERSION, "v2")

    def test_diarization_pins_the_speaker_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "dia.json")
            cmd = self._capture(
                lambda: tl.run_diarization("/bin/cli", "a.wav", out, num_speakers=4),
                {"segments": [{"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 1.0}]},
            )

        self.assertIn("process", cmd)
        self.assertEqual(cmd[cmd.index("--mode") + 1], "offline")
        self.assertEqual(cmd[cmd.index("--num-speakers") + 1], "4")

    def test_diarization_is_stamped_with_the_built_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp) / ".build"
            (build / "release").mkdir(parents=True)
            (build / ".built-commit").write_text("abc123\n", encoding="utf-8")
            cli = str(build / "release" / "fluidaudiocli")
            out = str(Path(tmp) / "dia.json")
            self._capture(
                lambda: tl.run_diarization(cli, "a.wav", out),
                {"segments": [{"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 1.0}]},
            )
            self.assertEqual(json.loads(Path(out).read_text(encoding="utf-8"))["fluidaudioCommit"], "abc123")
            self.assertIsNone(tl.built_commit("/bin/cli"))

    def test_diarization_omits_the_pin_when_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "dia.json")
            cmd = self._capture(
                lambda: tl.run_diarization("/bin/cli", "a.wav", out, num_speakers=None),
                {"segments": [{"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 1.0}]},
            )

        self.assertNotIn("--num-speakers", cmd)

    def test_unhonoured_pin_is_reported(self):
        payload = {
            "segments": [{"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 1.0}],
            "speakerCount": 2,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "dia.json")
            with mock.patch("builtins.print") as printed:
                self._capture(
                    lambda: tl.run_diarization("/bin/cli", "a.wav", out, num_speakers=4),
                    payload,
                )

        said = " ".join(str(c.args[0]) for c in printed.call_args_list if c.args)
        self.assertIn("Asked for 4 speakers", said)

    def test_honoured_pin_is_not_reported(self):
        payload = {
            "segments": [{"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 1.0}],
            "speakerCount": 4,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "dia.json")
            with mock.patch("builtins.print") as printed:
                self._capture(
                    lambda: tl.run_diarization("/bin/cli", "a.wav", out, num_speakers=4),
                    payload,
                )

        said = " ".join(str(c.args[0]) for c in printed.call_args_list if c.args)
        self.assertNotIn("Asked for", said)

    def test_diarization_rejects_an_empty_segment_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "dia.json")
            with self.assertRaises(RuntimeError):
                self._capture(
                    lambda: tl.run_diarization("/bin/cli", "a.wav", out),
                    {"segments": []},
                )

    def test_cli_failure_surfaces_the_output(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 2, "stdout detail", "stderr detail")

        with mock.patch.object(tl.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(RuntimeError) as ctx:
                tl._run_cli("/bin/cli", ["transcribe"], "transcribe")

        self.assertIn("stderr detail", str(ctx.exception))


class TranscribeLocalTests(unittest.TestCase):
    def test_writes_turns_json_and_removes_the_temp_wav(self):
        asr = {
            "wordTimings": words(("Hello.", 0.0, 0.5), ("Hi.", 2.0, 2.5)),
            "processingTimeSeconds": 1.0,
            "rtfx": 100.0,
        }
        dia = {"segments": segments(("S1", 0.0, 0.5), ("S2", 2.0, 2.5)), "speakerCount": 2}
        seen_wav = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffmpeg":
                Path(cmd[cmd.index("-c:a") + 2]).write_bytes(b"wav")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            seen_wav.append(cmd[2])
            out_flag = "--output-json" if "--output-json" in cmd else "--output"
            payload = asr if "transcribe" in cmd else dia
            Path(cmd[cmd.index(out_flag) + 1]).write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with tempfile.TemporaryDirectory() as tmp:
            out_base = str(Path(tmp) / "episode001")
            with mock.patch.dict("os.environ", {"FLUIDAUDIO_CLI": "/bin/sh"}, clear=False):
                with mock.patch.object(tl.shutil, "which", return_value="/usr/bin/ffmpeg"):
                    with mock.patch.object(tl.subprocess, "run", side_effect=fake_run):
                        transcript = tl.transcribe_local("ep.mp3", out_base, num_speakers=2)

            self.assertEqual(transcript, "[A]: Hello.\n[B]: Hi.")
            turns = json.loads(Path(f"{out_base}-turns.json").read_text(encoding="utf-8"))
            self.assertEqual([t["speaker"] for t in turns], ["A", "B"])
            self.assertEqual(turns[0]["start"], 0.0)
            self.assertTrue(Path(f"{out_base}-asr.json").exists())
            self.assertTrue(Path(f"{out_base}-diarization.json").exists())

        # The scratch WAV is cleaned up rather than left in the temp dir.
        self.assertTrue(seen_wav)
        self.assertFalse(os.path.exists(seen_wav[0]))

    def test_missing_ffmpeg_is_reported(self):
        with mock.patch.dict("os.environ", {"FLUIDAUDIO_CLI": "/bin/sh"}, clear=False):
            with mock.patch.object(tl.shutil, "which", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    tl.transcribe_local("ep.mp3", "base")
        self.assertIn("ffmpeg", str(ctx.exception))


class RediarizeTests(unittest.TestCase):
    ASR = {
        "wordTimings": words(("Hello.", 0.0, 0.5), ("Hi.", 2.0, 2.5), ("Bye.", 4.0, 4.5)),
        "processingTimeSeconds": 1.0,
        "rtfx": 100.0,
    }

    def _run(self, out_base, dia):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[0] == "ffmpeg":
                Path(cmd[cmd.index("-c:a") + 2]).write_bytes(b"wav")
                return subprocess.CompletedProcess(cmd, 0, "", "")
            Path(cmd[cmd.index("--output") + 1]).write_text(json.dumps(dia), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.dict("os.environ", {"FLUIDAUDIO_CLI": "/bin/sh"}, clear=False):
            with mock.patch.object(tl.shutil, "which", return_value="/usr/bin/ffmpeg"):
                with mock.patch.object(tl.subprocess, "run", side_effect=fake_run):
                    transcript = tl.rediarize("ep.mp3", out_base, 3)
        return transcript, calls

    def test_reuses_saved_asr_and_rewrites_the_diarized_outputs(self):
        dia = {
            "segments": segments(("S1", 0.0, 0.5), ("S2", 2.0, 2.5), ("S3", 4.0, 4.5)),
            "speakerCount": 3,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out_base = str(Path(tmp) / "episode001")
            Path(f"{out_base}-asr.json").write_text(json.dumps(self.ASR), encoding="utf-8")
            Path(f"{out_base}-local.txt").write_text("[A]: stale", encoding="utf-8")

            transcript, calls = self._run(out_base, dia)

            self.assertEqual(transcript, "[A]: Hello.\n[B]: Hi.\n[C]: Bye.")
            self.assertEqual(Path(f"{out_base}-local.txt").read_text(encoding="utf-8"), transcript)
            turns = json.loads(Path(f"{out_base}-turns.json").read_text(encoding="utf-8"))
            self.assertEqual([t["speaker"] for t in turns], ["A", "B", "C"])
            saved = json.loads(Path(f"{out_base}-diarization.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["speakerCount"], 3)

        cli_calls = [c for c in calls if c[0] != "ffmpeg"]
        self.assertEqual(len(cli_calls), 1)
        self.assertNotIn("transcribe", cli_calls[0])
        self.assertEqual(cli_calls[0][cli_calls[0].index("--num-speakers") + 1], "3")

    def test_missing_asr_is_reported_before_any_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(tl.subprocess, "run") as run:
                with self.assertRaises(RuntimeError) as ctx:
                    tl.rediarize("ep.mp3", str(Path(tmp) / "episode001"), 3)
        self.assertIn("-asr.json", str(ctx.exception))
        run.assert_not_called()

    def test_count_must_be_positive(self):
        with self.assertRaises(ValueError):
            tl.rediarize("ep.mp3", "base", 0)


class SpeakerLabelsTests(unittest.TestCase):
    def test_maps_diarizer_ids_to_turn_labels_by_first_appearance(self):
        asr = {"wordTimings": words(("a", 0.0, 0.5), ("b", 2.0, 2.5))}
        dia = {"segments": segments(("S2", 0.0, 0.5), ("S1", 2.0, 2.5), ("S3", 9.0, 9.5))}
        # S3 wins no word, so no turn carries it.
        self.assertEqual(tl.speaker_labels(asr, dia), {"S2": "A", "S1": "B"})


class SpeakerCountPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = podbean

    def _prompt(self, answers, env=None):
        answers = list(answers)
        with mock.patch.dict("os.environ", env or {"EPISODE_SPEAKERS": ""}, clear=False):
            return self.mod.prompt_speaker_count(input_func=lambda: answers.pop(0))

    def test_enter_means_auto_detect_not_a_guessed_count(self):
        """No numeric default: a wrong pin merges real people irrecoverably."""
        self.assertIsNone(self._prompt([""]))

    def test_eof_falls_back_to_auto_detect(self):
        def eof():
            raise EOFError

        with mock.patch.dict("os.environ", {"EPISODE_SPEAKERS": ""}, clear=False):
            self.assertIsNone(self.mod.prompt_speaker_count(input_func=eof))

    def test_number_is_accepted(self):
        self.assertEqual(self._prompt(["4"]), 4)

    def test_auto_disables_pinning(self):
        self.assertIsNone(self._prompt(["auto"]))

    def test_invalid_input_reprompts(self):
        self.assertEqual(self._prompt(["zero", "0", "3"]), 3)

    def test_env_override_skips_the_prompt(self):
        def explode():
            raise AssertionError("should not prompt")

        with mock.patch.dict("os.environ", {"EPISODE_SPEAKERS": "5"}, clear=False):
            self.assertEqual(self.mod.prompt_speaker_count(input_func=explode), 5)

    def test_env_auto_skips_the_prompt(self):
        with mock.patch.dict("os.environ", {"EPISODE_SPEAKERS": "auto"}, clear=False):
            self.assertIsNone(self.mod.prompt_speaker_count(input_func=lambda: "3"))


class LoadOrTranscribeTests(unittest.TestCase):
    """-turns.json is the transcription checkpoint, keyed in the step input record."""

    TURNS = [
        {"speaker": "A", "start": 0.0, "end": 1.0, "text": "Hello."},
        {"speaker": "B", "start": 1.0, "end": 2.0, "text": "Hi."},
    ]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audio = self.root / "riverside_ep.mp3"
        self.audio.write_bytes(b"audio")
        self.out_base = str(self.root / "episode110")
        for patcher in (
            mock.patch("builtins.print"),
            mock.patch.dict("os.environ", {"EPISODE_SPEAKERS": "2"}),
            mock.patch.object(podbean.voice_match, "fluidaudio_pin", return_value="pin1"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _fake_local(self, audio_path, out_base, num_speakers=None, verbose=False):
        Path(f"{out_base}-turns.json").write_text(json.dumps(self.TURNS), encoding="utf-8")
        return tl.format_turns(self.TURNS)

    def test_first_run_transcribes_with_the_pin_and_writes_the_raw_text(self):
        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local) as local:
            turns = podbean.load_or_transcribe(str(self.audio), self.out_base)
        self.assertEqual(turns, self.TURNS)
        self.assertEqual(local.call_args.kwargs["num_speakers"], 2)
        self.assertEqual(Path(f"{self.out_base}-local.txt").read_text(), tl.format_turns(self.TURNS))

    def test_rerun_with_the_same_recording_reuses_the_turns(self):
        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local) as local:
            podbean.load_or_transcribe(str(self.audio), self.out_base)
            podbean.load_or_transcribe(str(self.audio), self.out_base)
        self.assertEqual(local.call_count, 1)

    def test_turns_without_a_record_are_transcribed_again(self):
        Path(f"{self.out_base}-turns.json").write_text(json.dumps(self.TURNS), encoding="utf-8")
        Path(f"{self.out_base}-article.md").write_text("old", encoding="utf-8")
        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local) as local:
            podbean.load_or_transcribe(str(self.audio), self.out_base)
        local.assert_called_once()
        self.assertFalse(Path(f"{self.out_base}-article.md").exists())

    def test_skip_transcription_uses_saved_turns_or_stops(self):
        with self.assertRaises(podbean.PipelineStop):
            podbean.load_or_transcribe(str(self.audio), self.out_base, skip_transcription=True)
        Path(f"{self.out_base}-turns.json").write_text(json.dumps(self.TURNS), encoding="utf-8")
        with mock.patch.object(podbean, "transcribe_local") as local:
            self.assertEqual(
                podbean.load_or_transcribe(str(self.audio), self.out_base, skip_transcription=True), self.TURNS
            )
        local.assert_not_called()

    def test_transcription_failure_stops(self):
        with mock.patch.object(podbean, "transcribe_local", side_effect=RuntimeError("ffmpeg not found")):
            with self.assertRaisesRegex(podbean.PipelineStop, "ffmpeg not found"):
                podbean.load_or_transcribe(str(self.audio), self.out_base)


class ReferenceTextTests(unittest.TestCase):
    def test_sidecar_vtt_is_read_as_plain_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "ep.mp3"
            audio.write_bytes(b"x")
            (Path(tmp) / "ep.vtt").write_text("WEBVTT\n\n1\n00:00.000 --> 00:01.000\nHello there\n", encoding="utf-8")
            with mock.patch("builtins.print"):
                self.assertEqual(podbean.load_reference_text(None, str(audio)), "Hello there")

    def test_no_sidecar_and_no_flag_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "ep.mp3"
            audio.write_bytes(b"x")
            self.assertEqual(podbean.load_reference_text(None, str(audio)), "")


class SidecarStagingTests(unittest.TestCase):
    def test_downloads_move_only_transcripts_named_after_an_mp3(self):
        with tempfile.TemporaryDirectory() as downloads, tempfile.TemporaryDirectory() as raw:
            for name in ("ep.mp3", "ep.mp4", "ep.vtt", "ep-transcript.txt", "notes.txt"):
                (Path(downloads) / name).write_bytes(b"x")
            with mock.patch.object(podbean, "DOWNLOADS_DIR", downloads), \
                    mock.patch.object(podbean, "RAW_DIR", raw), \
                    mock.patch("builtins.print"):
                podbean.stage_downloads_to_raw()

            self.assertEqual(
                sorted(p.name for p in Path(raw).iterdir()),
                ["ep-transcript.txt", "ep.mp3", "ep.mp4", "ep.vtt"],
            )
            self.assertEqual([p.name for p in Path(downloads).iterdir()], ["notes.txt"])


if __name__ == "__main__":
    unittest.main()
