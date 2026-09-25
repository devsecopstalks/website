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


class TranscribeBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = podbean

    def test_defaults_to_local(self):
        with mock.patch.dict("os.environ", {"TRANSCRIBE_BACKEND": ""}, clear=False):
            self.assertEqual(self.mod.transcribe_backend(), "local")

    def test_openai_is_accepted(self):
        with mock.patch.dict("os.environ", {"TRANSCRIBE_BACKEND": "OpenAI"}, clear=False):
            self.assertEqual(self.mod.transcribe_backend(), "openai")

    def test_unknown_backend_exits(self):
        with mock.patch.dict("os.environ", {"TRANSCRIBE_BACKEND": "whisper"}, clear=False):
            with self.assertRaises(SystemExit):
                self.mod.transcribe_backend()

    def test_local_backend_calls_the_local_transcriber_with_the_pin(self):
        with mock.patch.object(self.mod, "transcribe_local", return_value="local text") as local:
            with mock.patch.object(self.mod, "transcribe_openai") as openai:
                result = self.mod.transcribe(object(), "ep.mp3", "base", "local", num_speakers=4)

        self.assertEqual(result, "local text")
        openai.assert_not_called()
        self.assertEqual(local.call_args.kwargs["num_speakers"], 4)

    def test_openai_backend_calls_the_hosted_transcriber(self):
        with mock.patch.object(self.mod, "transcribe_local") as local:
            with mock.patch.object(self.mod, "transcribe_openai", return_value="hosted") as openai:
                result = self.mod.transcribe(object(), "ep.mp3", "base", "openai")

        self.assertEqual(result, "hosted")
        local.assert_not_called()
        openai.assert_called_once()

    def test_openai_backend_without_a_client_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
            podbean.transcribe(None, "ep.mp3", "base", "openai")


class OpenAIClientTests(unittest.TestCase):
    def _main(self, backend):
        env = {"TRANSCRIBE_BACKEND": backend, "OPENAI_API_KEY": ""}
        with mock.patch.dict("os.environ", env, clear=False), \
                mock.patch.object(sys, "argv", ["podbean.py", "-f", "ep.mp3"]), \
                mock.patch.object(podbean, "process_audio") as process, \
                mock.patch("builtins.print"):
            podbean.main()
        return process

    def test_local_backend_needs_no_openai_key(self):
        process = self._main("local")
        self.assertIsNone(process.call_args.args[2])

    def test_openai_backend_requires_the_key(self):
        with self.assertRaises(SystemExit):
            self._main("openai")


class OpenAIChunkingTests(unittest.TestCase):
    def test_long_audio_is_split_under_the_diarize_limit(self):
        client = mock.Mock(api_key="k")
        segments_seen = []

        def fake_extract(src, start, length, out, verbose=False):
            segments_seen.append((start, length))

        with mock.patch.object(podbean, "get_audio_duration_seconds", return_value=2700.0), \
                mock.patch.object(podbean, "extract_audio_segment", side_effect=fake_extract), \
                mock.patch.object(podbean, "transcribe_diarized", side_effect=["[A]: one", "[A]: two", "[A]: three"]), \
                mock.patch("builtins.print"):
            text = podbean.transcribe_openai(client, "ep.mp3")

        self.assertEqual(text, "[A]: one\n\n[A]: two\n\n[A]: three")
        self.assertEqual(len(segments_seen), 3)
        self.assertTrue(all(length <= podbean._DIARIZE_CHUNK_SECONDS for _, length in segments_seen))
        self.assertAlmostEqual(sum(length for _, length in segments_seen), 2700.0)


class LoadOrCreateTranscriptTests(unittest.TestCase):
    """out/episodeNNN.txt assembly: backend checkpoint, sidecar merge, invalidation, turns binding."""

    TURNS = [
        {"speaker": "A", "start": 0.0, "end": 1.0, "text": "Hello."},
        {"speaker": "B", "start": 1.0, "end": 2.0, "text": "Hi."},
    ]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()
        self.audio = self.raw / "riverside_ep.mp3"
        self.audio.write_bytes(b"audio")
        self.out_base = str(self.root / "episode110")
        patcher = mock.patch("builtins.print")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_local(self, audio_path, out_base, num_speakers=None, verbose=False):
        Path(f"{out_base}-turns.json").write_text(json.dumps(self.TURNS), encoding="utf-8")
        return tl.format_turns(self.TURNS)

    def _run(self, backend="local", answers=(), client=None, speakers="4"):
        answers = list(answers)
        env = {"TRANSCRIBE_BACKEND": backend, "EPISODE_SPEAKERS": speakers}
        with mock.patch.dict("os.environ", env, clear=False):
            return podbean.load_or_create_transcript(
                client, str(self.audio), self.out_base, input_func=lambda: answers.pop(0)
            )

    def test_local_run_writes_backend_and_final_checkpoints_with_bound_turns(self):
        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local) as local:
            transcript = self._run()

        self.assertEqual(local.call_args.kwargs["num_speakers"], 4)
        self.assertEqual(Path(f"{self.out_base}-local.txt").read_text(), transcript)
        self.assertEqual(Path(f"{self.out_base}.txt").read_text(), transcript)
        self.assertEqual(podbean.load_transcript_turns(self.out_base, transcript), self.TURNS)

    def test_new_transcript_removes_derived_checkpoints_only(self):
        derived = ["-guests.json", "-draft.md", "-draft-v2.md", "-review-1.md", "-article.md",
                   "-metadata.json", "-chapters-generated.txt", "-announcement.json"]
        kept = ["-title.txt", "-chapters.txt", "-announcement-scheduled.txt", "-source.json",
                "-youtube-scheduled.txt"]
        for suffix in derived + kept:
            Path(f"{self.out_base}{suffix}").write_text("old", encoding="utf-8")

        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local):
            self._run()

        for suffix in derived:
            self.assertFalse(Path(f"{self.out_base}{suffix}").exists(), suffix)
        for suffix in kept:
            self.assertTrue(Path(f"{self.out_base}{suffix}").exists(), suffix)

    def test_transcript_is_saved_before_derived_checkpoints_are_removed(self):
        Path(f"{self.out_base}-article.md").write_text("old", encoding="utf-8")
        seen = []

        def invalidate(out_base):
            seen.append((Path(f"{out_base}.txt").exists(), Path(f"{out_base}-transcript-source.json").exists()))
            return []

        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local), \
                mock.patch.object(podbean, "invalidate_transcript_checkpoints", side_effect=invalidate):
            self._run()
        self.assertEqual(seen, [(True, True)])

    def test_external_transcript_change_invalidates_and_binds_no_turns(self):
        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local):
            machine = self._run()
        Path(f"{self.out_base}-article.md").write_text("old", encoding="utf-8")
        self.assertFalse(podbean.adopt_external_transcript(self.out_base, machine, "same.txt"))
        self.assertTrue(Path(f"{self.out_base}-article.md").exists())
        self.assertEqual(podbean.load_transcript_turns(self.out_base, machine), self.TURNS)

        self.assertTrue(podbean.adopt_external_transcript(self.out_base, "[A]: edited", "/x/edited.txt"))
        self.assertFalse(Path(f"{self.out_base}-article.md").exists())
        self.assertEqual(Path(f"{self.out_base}.txt").read_text(), "[A]: edited")
        source = json.loads(Path(f"{self.out_base}-transcript-source.json").read_text())
        self.assertEqual((source["backend"], source["provided_transcript"]), ("external", "edited.txt"))
        self.assertIsNone(podbean.load_transcript_turns(self.out_base, "[A]: edited"))

    def test_openai_transcript_never_uses_turns_left_by_the_local_backend(self):
        Path(f"{self.out_base}-turns.json").write_text(json.dumps(self.TURNS), encoding="utf-8")
        with mock.patch.object(podbean, "transcribe_openai", return_value=tl.format_turns(self.TURNS)):
            transcript = self._run(backend="openai", client=object())

        self.assertTrue(Path(f"{self.out_base}-openai.txt").exists())
        self.assertIsNone(podbean.load_transcript_turns(self.out_base, transcript))

    def test_openai_backend_does_not_prompt_for_speakers(self):
        with mock.patch.object(podbean, "transcribe_openai", return_value="[A]: hosted"), \
                mock.patch.object(podbean, "prompt_speaker_count") as prompt:
            self._run(backend="openai", client=object())
        prompt.assert_not_called()

    def test_reused_local_transcript_with_mismatched_turns_is_not_bound(self):
        Path(f"{self.out_base}-local.txt").write_text("[A]: something else", encoding="utf-8")
        Path(f"{self.out_base}-turns.json").write_text(json.dumps(self.TURNS), encoding="utf-8")
        with mock.patch.object(podbean, "transcribe_local") as local:
            transcript = self._run(answers=[""])

        local.assert_not_called()
        self.assertEqual(transcript, "[A]: something else")
        self.assertIsNone(podbean.load_transcript_turns(self.out_base, transcript))

    def test_edited_turns_file_is_no_longer_bound(self):
        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local):
            transcript = self._run()
        Path(f"{self.out_base}-turns.json").write_text("[]", encoding="utf-8")
        self.assertIsNone(podbean.load_transcript_turns(self.out_base, transcript))

    def test_legacy_transcript_without_source_record_has_no_turns(self):
        self.assertIsNone(podbean.load_transcript_turns(self.out_base, "[A]: old"))

    def test_sidecar_is_merged_with_codex_and_turns_stay_bound_to_the_machine_pass(self):
        (self.raw / "riverside_ep.vtt").write_text(
            "WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\nHello there.\n", encoding="utf-8"
        )
        with mock.patch.object(podbean, "transcribe_local", side_effect=self._fake_local), \
                mock.patch.object(podbean, "run_codex", return_value="[A]: Hello there.\n[B]: Hi.") as codex:
            transcript = self._run()

        self.assertEqual(transcript, "[A]: Hello there.\n[B]: Hi.")
        stdin = codex.call_args.kwargs["stdin_text"]
        self.assertIn("Hello there.", stdin)
        self.assertNotIn("-->", stdin)
        self.assertEqual(Path(f"{self.out_base}.txt").read_text(), transcript)
        self.assertEqual(podbean.load_transcript_turns(self.out_base, transcript), self.TURNS)


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
