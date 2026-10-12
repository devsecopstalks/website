import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import voice_match as vm  # noqa: E402

PIN = "abc123"


def host(name, *vec):
    return vm.HostVoice(name=name, embedding=vm._unit(vec), sources=())


# Orthogonal hosts make every score below an exact cosine of the label vector.
HOSTS = {
    "Andrey Devyatkin": host("Andrey Devyatkin", 1, 0, 0, 0),
    "Mattias Hemmingsson": host("Mattias Hemmingsson", 0, 1, 0, 0),
    "Paulina Dubas": host("Paulina Dubas", 0, 0, 1, 0),
}


def voice(label, *vec, seconds=600.0):
    return vm.LabelVoice(label=label, embedding=vm._unit(vec), seconds=seconds)


def along(score, axis=0):
    """A unit vector scoring ``score`` against the host on ``axis``, 0 on the others."""
    vec = [0.0, 0.0, 0.0, 0.0]
    vec[axis] = score
    vec[3] = (1 - score * score) ** 0.5
    return vec


def by_label(matches):
    return {m.label: m for m in matches}


class LabelEmbeddingsTests(unittest.TestCase):
    DIA = {
        "segments": [
            {"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 30.0, "embedding": [1, 0]},
            {"speakerId": "S1", "startTimeSeconds": 30.0, "endTimeSeconds": 40.0, "embedding": [0, 2]},
            {"speakerId": "S2", "startTimeSeconds": 40.0, "endTimeSeconds": 100.0, "embedding": [0, 1]},
        ]
    }

    def test_duration_weighted_mean_of_normalized_segments(self):
        voices = vm.label_embeddings(self.DIA)
        s1 = voices["S1"]
        self.assertAlmostEqual(s1.seconds, 40.0)
        # 30 s of [1,0] and 10 s of [0,1] after normalizing the [0,2] segment.
        self.assertAlmostEqual(s1.embedding[0] / s1.embedding[1], 3.0)
        self.assertAlmostEqual(sum(x * x for x in s1.embedding), 1.0)
        self.assertAlmostEqual(voices["S2"].minutes, 1.0)

    def test_with_asr_keys_are_the_turn_labels(self):
        asr = {"wordTimings": [
            {"word": "hi", "startTime": 50.0, "endTime": 51.0},
            {"word": "yo", "startTime": 5.0, "endTime": 6.0},
        ]}
        # Words are in time order in real ASR output; sort to keep the fixture honest.
        asr["wordTimings"].sort(key=lambda w: w["startTime"])
        voices = vm.label_embeddings(self.DIA, asr)
        self.assertEqual(set(voices), {"A", "B"})
        self.assertAlmostEqual(voices["A"].seconds, 40.0)  # S1 speaks first
        self.assertAlmostEqual(voices["B"].seconds, 60.0)


class MatchSpeakersTests(unittest.TestCase):
    def test_clear_matches_and_a_clear_guest_have_no_flags(self):
        matches = by_label(vm.match_speakers({
            "A": voice("A", *along(0.95, axis=0)),
            "B": voice("B", *along(0.9, axis=2)),
            "C": voice("C", *along(0.3, axis=1)),
        }, HOSTS))

        self.assertEqual(matches["A"].host, "Andrey Devyatkin")
        self.assertEqual(matches["B"].host, "Paulina Dubas")
        self.assertIsNone(matches["C"].host)
        self.assertEqual(matches["C"].name, "guest")
        self.assertEqual(matches["C"].closest_host, "Mattias Hemmingsson")
        self.assertAlmostEqual(matches["C"].score, 0.3)
        self.assertFalse(vm.unresolved(matches.values()))

    def test_doubtful_band_is_a_flagged_guest(self):
        score = (vm.GUEST_CEILING + vm.MATCH_THRESHOLD) / 2
        [m] = vm.match_speakers({"A": voice("A", *along(score))}, HOSTS)
        self.assertIsNone(m.host)
        self.assertIn("below", m.flags[0])
        self.assertIn("Andrey Devyatkin", m.flags[0])

    # Two prints 0.93 rad apart (cosine 0.6), so a label can clear the threshold
    # for both, which orthogonal prints cannot reproduce.
    NEAR_HOSTS = {"Andrey Devyatkin": host("Andrey Devyatkin", 1, 0), "Mattias Hemmingsson": host("Mattias Hemmingsson", 0.6, 0.8)}

    def test_close_runner_up_is_flagged(self):
        [m] = vm.match_speakers({"A": voice("A", 0.90, 0.435)}, self.NEAR_HOSTS)
        self.assertEqual(m.host, "Andrey Devyatkin")
        self.assertLess(m.score - m.second_score, vm.SECOND_BEST_MARGIN)
        self.assertIn("within", m.flags[0])
        self.assertIn("Mattias Hemmingsson", m.flags[0])

    def test_two_hosts_above_threshold_is_flagged_as_a_merge(self):
        [m] = vm.match_speakers({"A": voice("A", 0.95, 0.31)}, self.NEAR_HOSTS)
        self.assertEqual(m.host, "Andrey Devyatkin")
        self.assertGreaterEqual(m.second_score, vm.MATCH_THRESHOLD)
        self.assertGreaterEqual(m.score - m.second_score, vm.SECOND_BEST_MARGIN)
        self.assertIn("two people", m.flags[0])

    def test_two_labels_on_one_host_are_both_flagged(self):
        matches = by_label(vm.match_speakers({
            "A": voice("A", *along(0.95)),
            "B": voice("B", *along(0.9)),
        }, HOSTS))
        self.assertIn("same host as B", matches["A"].flags)
        self.assertIn("same host as A", matches["B"].flags)

    def test_dims_mismatch_raises(self):
        with self.assertRaises(ValueError):
            vm.match_speakers({"A": voice("A", 1, 0)}, HOSTS)


class OverrideTests(unittest.TestCase):
    def setUp(self):
        self.matches = vm.match_speakers({
            "A": voice("A", *along(0.95)),
            "B": voice("B", *along(0.9)),
            "C": voice("C", *along(0.7, axis=1)),
        }, HOSTS)

    def test_guest_override_clears_both_same_host_flags(self):
        matches = by_label(vm.apply_overrides(self.matches, {"B": None}))
        self.assertIsNone(matches["B"].host)
        self.assertTrue(matches["B"].overridden)
        self.assertEqual(matches["A"].flags, ())

    def test_explicit_same_host_clears_the_flag_and_keeps_both_named(self):
        matches = by_label(vm.apply_overrides(self.matches, {"B": "Andrey Devyatkin", "C": None}))
        self.assertEqual(matches["A"].host, "Andrey Devyatkin")
        self.assertEqual(matches["B"].host, "Andrey Devyatkin")
        self.assertFalse(vm.unresolved(matches.values()))

    def test_override_onto_a_host_another_label_holds_settles_both(self):
        matches = by_label(vm.apply_overrides(self.matches, {"C": "Andrey Devyatkin"}))
        self.assertEqual(matches["C"].host, "Andrey Devyatkin")
        # The operator named Andrey knowing A and B already were, so the group is settled.
        self.assertFalse(vm.unresolved(matches.values()))

    def test_overrides_compose_across_rounds(self):
        once = vm.apply_overrides(self.matches, {"C": None})
        self.assertEqual(len(vm.unresolved(once)), 2)
        twice = vm.apply_overrides(once, {"A": "Mattias Hemmingsson"})
        self.assertFalse(vm.unresolved(twice))
        self.assertIsNone(by_label(twice)["C"].host)

    def test_unknown_label_raises(self):
        with self.assertRaises(ValueError):
            vm.apply_overrides(self.matches, {"Z": None})


class ParseConfirmationTests(unittest.TestCase):
    LABELS = ["A", "B", "C"]

    def test_enter_accepts(self):
        self.assertEqual(vm.parse_confirmation("  ", self.LABELS).kind, "accept")
        self.assertEqual(vm.parse_confirmation("", self.LABELS).kind, "accept")

    def test_bare_number_requests_a_rediarize(self):
        answer = vm.parse_confirmation(" 4 ", self.LABELS)
        self.assertEqual((answer.kind, answer.num_speakers), ("rediarize", 4))

    def test_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            vm.parse_confirmation("0", self.LABELS)

    def test_overrides_are_case_insensitive(self):
        answer = vm.parse_confirmation("c=GUEST, a=mattias b=Paulina", self.LABELS)
        self.assertEqual(answer.kind, "overrides")
        self.assertEqual(answer.overrides, {"C": None, "A": "Mattias Hemmingsson", "B": "Paulina Dubas"})

    def test_bad_input_is_explained(self):
        for text, needle in [
            ("A", "LABEL=NAME"),
            ("Z=guest", "unknown label"),
            ("A=Nikita", "not a host"),
            ("3 A=guest", "LABEL=NAME"),
        ]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as ctx:
                    vm.parse_confirmation(text, self.LABELS)
                self.assertIn(needle, str(ctx.exception))


class FormatMatchesTests(unittest.TestCase):
    def test_table_shows_name_score_minutes_and_reason(self):
        matches = vm.match_speakers({
            "A": voice("A", *along(0.95), seconds=1200),
            "B": voice("B", *along(0.7, axis=1), seconds=90),
        }, HOSTS)
        text = vm.format_matches(matches)
        lines = text.splitlines()
        self.assertIn("Andrey Devyatkin 0.95", lines[1])
        self.assertIn("20.0", lines[1])
        self.assertNotIn("⚠", lines[1])
        self.assertIn("guest", lines[2])
        self.assertIn("1.5", lines[2])
        self.assertIn("⚠ below", lines[2])

    def test_override_is_marked(self):
        matches = vm.apply_overrides(
            vm.match_speakers({"A": voice("A", *along(0.3))}, HOSTS), {"A": "Paulina Dubas"}
        )
        self.assertIn("Paulina Dubas (set)", vm.format_matches(matches))


class HostVoicesFileTests(unittest.TestCase):
    def _write(self, tmp, pin=PIN, dims=2):
        path = Path(tmp) / "host-voices.json"
        path.write_text(json.dumps({
            "fluidaudio_commit": pin,
            "dims": dims,
            "hosts": {"Andrey Devyatkin": {"embedding": [3, 4], "sources": [{"episode": "episode111", "label": "S1"}]}},
        }), encoding="utf-8")
        return str(path)

    def test_loads_and_normalizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            hosts = vm.load_host_voices(self._write(tmp), current_pin=PIN)
        self.assertEqual(hosts["Andrey Devyatkin"].embedding, (0.6, 0.8))
        self.assertEqual(hosts["Andrey Devyatkin"].sources[0]["label"], "S1")

    def test_pin_mismatch_refuses_and_names_the_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(vm.VoicePrintError) as ctx:
                vm.load_host_voices(self._write(tmp, pin="old999"), current_pin=PIN)
        message = str(ctx.exception)
        self.assertIn("old999", message)
        self.assertIn(PIN, message)
        self.assertIn("build-host-voices.py", message)

    def test_missing_file_names_the_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(vm.VoicePrintError) as ctx:
                vm.load_host_voices(str(Path(tmp) / "none.json"), current_pin=PIN)
        self.assertIn("build-host-voices.py", str(ctx.exception))

    def test_dims_disagreeing_with_the_file_header_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(vm.VoicePrintError):
                vm.load_host_voices(self._write(tmp, dims=256), current_pin=PIN)

    def test_pin_is_read_from_do_sh(self):
        with tempfile.TemporaryDirectory() as tmp:
            do_sh = Path(tmp) / "do.sh"
            do_sh.write_text('FLUIDAUDIO_REPO="x"\nFLUIDAUDIO_COMMIT="deadbeef"\n', encoding="utf-8")
            self.assertEqual(vm.fluidaudio_pin(str(do_sh)), "deadbeef")
        # The real do.sh must keep a parseable pin, or matching can never run.
        self.assertRegex(vm.fluidaudio_pin(), r"^[0-9a-f]{40}$")


class BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "build_host_voices", TOOLS_DIR / "build-host-voices.py"
        )
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _episode(self, out_dir, num, segs):
        Path(out_dir, f"episode{num:03d}-diarization.json").write_text(json.dumps({"segments": [
            {"speakerId": spk, "startTimeSeconds": s, "endTimeSeconds": e, "embedding": emb}
            for spk, s, e, emb in segs
        ]}), encoding="utf-8")

    def test_source_spec_forms(self):
        self.assertEqual(self.mod.parse_source("22:S2=paulina"), ("episode022", "S2", "Paulina Dubas"))
        self.assertEqual(self.mod.parse_source("episode020:S1"), ("episode020", "S1", None))

    def test_prints_without_writing_then_writes_with_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._episode(tmp, 1, [("S1", 0, 60, [1, 0, 0]), ("S2", 60, 120, [0, 1, 0]),
                                   ("S3", 120, 180, [0, 0, 1])])
            self._episode(tmp, 2, [("S1", 0, 180, [1, 0.1, 0])])
            output = Path(tmp) / "host-voices.json"
            args = ["1:S1=Andrey", "2:S1=andrey dEVYATKIN", "1:S2=Mattias", "1:S3=Paulina",
                    "--out-dir", tmp, "--output", str(output)]

            self.assertEqual(self.mod.main(args), 0)
            self.assertFalse(output.exists())

            self.assertEqual(self.mod.main(args + ["--write"]), 0)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["fluidaudio_commit"], vm.fluidaudio_pin())
        self.assertEqual(data["dims"], 3)
        andrey = data["hosts"]["Andrey Devyatkin"]
        self.assertEqual([s["episode"] for s in andrey["sources"]], ["episode001", "episode002"])
        # Episode 2 spoke three times as long, so it pulls the mean towards its vector.
        self.assertAlmostEqual(andrey["embedding"][1] / andrey["embedding"][0], 0.3 / 4, places=2)

    def test_write_refuses_without_every_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._episode(tmp, 1, [("S1", 0, 60, [1, 0])])
            output = Path(tmp) / "host-voices.json"
            code = self.mod.main(["1:S1=Andrey", "--out-dir", tmp, "--output", str(output), "--write"])
            self.assertEqual(code, 1)
            self.assertFalse(output.exists())


class CanonicalHostTests(unittest.TestCase):
    def test_first_or_full_name_in_any_case(self):
        self.assertEqual(vm.canonical_host("mattias"), "Mattias Hemmingsson")
        self.assertEqual(vm.canonical_host(" PAULINA DUBAS "), "Paulina Dubas")
        self.assertIsNone(vm.canonical_host("Nikita"))
        self.assertIsNone(vm.canonical_host(""))

    def test_hosts_present_keeps_host_order(self):
        names = {"B": "Paulina Dubas", "A": "Mattias Hemmingsson", "C": "Mattias Hemmingsson"}
        self.assertEqual(vm.hosts_present(names), ["Mattias Hemmingsson", "Paulina Dubas"])


class ConfirmSpeakersTests(unittest.TestCase):
    # S1 speaks first (label A) and sounds like Andrey; S2 (label B) is a clear guest.
    ASR = {"wordTimings": [
        {"word": "hello", "startTime": 1.0, "endTime": 2.0},
        {"word": "there", "startTime": 70.0, "endTime": 71.0},
    ]}

    def _episode(self, tmp, s2_vec=(0.3, 0, 0, 0.954)):
        base = str(Path(tmp) / "episode001")
        Path(f"{base}-asr.json").write_text(json.dumps(self.ASR), encoding="utf-8")
        self._diarize(base, s2_vec)
        return base

    @staticmethod
    def _diarize(base, s2_vec):
        Path(f"{base}-diarization.json").write_text(json.dumps({"segments": [
            {"speakerId": "S1", "startTimeSeconds": 0.0, "endTimeSeconds": 60.0,
             "embedding": along(0.95)},
            {"speakerId": "S2", "startTimeSeconds": 60.0, "endTimeSeconds": 120.0,
             "embedding": list(s2_vec)},
        ]}), encoding="utf-8")

    def _run(self, base, answers, **kwargs):
        feed = iter(answers)

        def ask():
            try:
                return next(feed)
            except StopIteration:
                raise EOFError from None

        with mock.patch("builtins.print"):
            return vm.confirm_speakers("ep.mp3", base, input_func=ask, host_voices=HOSTS, **kwargs)

    def test_enter_accepts_and_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._episode(tmp)
            names, transcript = self._run(base, [""])
            saved = json.loads(Path(f"{base}-speakers.json").read_text(encoding="utf-8"))
        self.assertEqual(names, {"A": "Andrey Devyatkin"})
        self.assertIsNone(transcript)
        self.assertEqual(saved["speakers"], {"A": "Andrey Devyatkin", "B": "guest"})

    def test_enter_is_refused_while_flagged_then_rename_settles_it(self):
        flagged = along((vm.GUEST_CEILING + vm.MATCH_THRESHOLD) / 2, axis=1)
        with tempfile.TemporaryDirectory() as tmp:
            base = self._episode(tmp, s2_vec=flagged)
            names, _ = self._run(base, ["", "b=mattias", ""])
            # A rerun against the same diarization re-applies the rename without asking twice.
            again, _ = self._run(base, [""])
        self.assertEqual(names, {"A": "Andrey Devyatkin", "B": "Mattias Hemmingsson"})
        self.assertEqual(again, names)

    def test_no_input_while_flagged_stops(self):
        flagged = along((vm.GUEST_CEILING + vm.MATCH_THRESHOLD) / 2, axis=1)
        with tempfile.TemporaryDirectory() as tmp:
            base = self._episode(tmp, s2_vec=flagged)
            with self.assertRaises(vm.SpeakerConfirmationError) as ctx:
                self._run(base, [])
        self.assertTrue(ctx.exception.checkpoint.endswith("-speakers.json"))

    def test_number_rediarizes_and_returns_the_new_transcript(self):
        calls = []

        def fake_rediarize(audio, base, count):
            calls.append(count)
            self._diarize(base, along(0.9, axis=2))
            return "[A]: hello\n[B]: there"

        with tempfile.TemporaryDirectory() as tmp:
            base = self._episode(tmp)
            names, transcript = self._run(base, ["2", ""], rediarize_func=fake_rediarize)
        self.assertEqual(calls, [2])
        self.assertEqual(names, {"A": "Andrey Devyatkin", "B": "Paulina Dubas"})
        self.assertEqual(transcript, "[A]: hello\n[B]: there")

    def test_missing_asr_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(vm.SpeakerConfirmationError):
                self._run(str(Path(tmp) / "episode001"), [""])


class ShippedPrintsTests(unittest.TestCase):
    def test_host_voices_json_matches_the_pin_and_holds_every_host(self):
        hosts = vm.load_host_voices()
        self.assertEqual(set(hosts), set(vm.HOSTS))


if __name__ == "__main__":
    unittest.main()
