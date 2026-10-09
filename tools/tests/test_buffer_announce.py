"""Buffer announcement: quote evidence, voice, tags, scheduling, ledger and eligibility.

Codex and the Buffer API are mocked; nothing is posted.
Run from repo: cd tools && uv run python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, patch

_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

import buffer_announce as ba  # noqa: E402
from episode_pipeline import normalize_guest_context  # noqa: E402

UTC = dt.timezone.utc
LINKEDIN_ID = "68ca90a4139f4ffdd6e8d02a"
X_ID = "56d21b912b19ce1e74c4ced1"
RELEASE = dt.datetime(2026, 9, 28, 11, 0, tzinfo=UTC)  # Monday Podbean slot
NOW = dt.datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
NAMED_FILE = "raw/riverside_edit_02 - paulina, matte, andrey +1_devsecops.mp3"
UNNAMED_FILE = "raw/riverside_magic_episode 01_devsecops.mp3"
PAGE = "content/episodes/111-renaming-a-repo-can-lock-you-out-of-aws-with-jane-doe.md"
COMPANY_PAGE = "https://www.linkedin.com/company/devsecops-talks"
PAGE_URL = "https://devsecops.fm/episodes/111-renaming-a-repo-can-lock-you-out-of-aws-with-jane-doe/"

TURNS = [
    {"speaker": "A", "start": 0.0, "end": 28.0,
     "text": "Welcome to devsekovs talks. I'm Andre, with me Matthias and Pauline, and our guest Jane Doe."},
    {"speaker": "B", "start": 28.0, "end": 95.0,
     "text": "Thanks. So renaming a repository changes the OIDC sub claim, and your AWS trust policy silently stops matching."},
    {"speaker": "C", "start": 95.0, "end": 160.0,
     "text": "That is why Matthias pins trust to the repository ID now, not the name."},
    {"speaker": "D", "start": 160.0, "end": 230.0,
     "text": "Right, and the ID survives a rename, a transfer, everything."},
]
GUEST = {
    "full_name": "Jane Doe",
    "participant_name": "Jane Doe",
    "role": "Staff Engineer",
    "company": "Example Corp",
    "linkedin_url": "https://www.linkedin.com/in/janedoe/",
    "linkedin_name": "Jane Doe",
    "x_handle": "janedoe",
}
QUOTE_PRESENT = {
    "format": "quote",
    "quote": "renaming a repository changes the OIDC sub claim, and your AWS trust policy silently stops matching",
    "source_speaker": "B",
    "source_timestamp": "00:28",
    "source_person": "Jane Doe",
    "context": "I had not connected a repo rename with an AWS lockout until Jane walked us through it.",
    "theme_hashtag": "#GitHubActions",
    "speaker_map": [{"label": "A", "person": "Andrey Devyatkin"}, {"label": "B", "person": "Jane Doe"}],
}
QUOTE_ABSENT = dict(
    QUOTE_PRESENT,
    context="Paulina and Mattias with Jane on why a repo rename can lock you out of AWS.",
    speaker_map=[{"label": "B", "person": "Jane Doe"}],
)
NO_QUOTE = {
    "format": "quote",  # the model ignored the no-turns rule; Python corrects it
    "quote": "renaming a repository breaks trust",
    "source_speaker": "B",
    "source_timestamp": "00:28",
    "source_person": "Jane Doe",
    "context": "A repository rename changes the OIDC sub claim, and AWS trust policies keyed on the name stop matching.",
    "theme_hashtag": "#AWS",
    "speaker_map": [],
}


def _channel(cid, service, name, tz, day, time):
    return {
        "id": cid, "name": name, "service": service, "displayName": name,
        "isDisconnected": False, "isLocked": False, "isQueuePaused": False, "timezone": tz,
        "postingSchedule": [{"day": day, "times": [time]}],
    }


CHANNELS = [
    _channel(LINKEDIN_ID, "linkedin", "andreydevyatkin", "Atlantic/Canary", "wed", "09:00"),
    _channel(X_ID, "twitter", "Andrey9kin", "Europe/Stockholm", "wed", "10:30"),
]


class FakeBuffer:
    """Stands in for requests.post against the Buffer GraphQL API."""

    def __init__(self, channels=CHANNELS, fail_channels=()):
        self.channels = channels
        self.fail_channels = set(fail_channels)
        self.created: list[dict] = []
        self.calls = 0

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls += 1
        query = json["query"]
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        if "organizations" in query:
            body = {"data": {"account": {"organizations": [{"id": "org1"}]}}}
        elif "channels(" in query:
            body = {"data": {"channels": self.channels}}
        else:
            post = json["variables"]["input"]
            if post["channelId"] in self.fail_channels:
                raise ConnectionError("network down")
            self.created.append(post)
            body = {"data": {"createPost": {"__typename": "PostActionSuccess",
                                            "post": {"id": f"post-{post['channelId'][:4]}"}}}}
        resp.json.return_value = body
        return resp


class AnnouncementRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out_base = os.path.join(self.tmp.name, "episode111")
        self.handles = ba.load_social_handles()

    def tearDown(self):
        self.tmp.cleanup()

    def guest_context(self, hosts, guests=(GUEST,)):
        return normalize_guest_context({"status": "verified", "guests": list(guests), "hosts_present": hosts})

    def run_announcement(self, answers, codex_outputs, turns=TURNS, audio=NAMED_FILE, buffer=None,
                         hosts=("Andrey Devyatkin", "Paulina Dubas", "Mattias Hemmingsson"), page=PAGE,
                         eligible=True, guests=(GUEST,)):
        if eligible:
            ba.record_announcement_eligibility(self.out_base, RELEASE)
        buffer = buffer or FakeBuffer()
        codex = MagicMock(side_effect=[json.dumps(o) for o in codex_outputs])
        answers = iter(answers)
        out = StringIO()
        with (
            patch("buffer_announce.requests.post", side_effect=buffer),
            patch("buffer_announce.run_codex", codex),
            redirect_stdout(out),
        ):
            ba.schedule_episode_announcement(
                self.out_base, 111, page, "Renaming a Repo Can Lock You Out of AWS with Jane Doe",
                "## Article\n\nBody.", "transcript text", turns, self.guest_context(list(hosts), guests), audio,
                input_func=lambda: next(answers), api_key="test-key", handles=self.handles, now=NOW,
            )
        return out.getvalue(), buffer, codex

    def ledger(self):
        return ba.load_ledger(f"{self.out_base}{ba.LEDGER_SUFFIX}")

    def saved(self):
        with open(f"{self.out_base}{ba.SAVED_SUFFIX}", encoding="utf-8") as f:
            return json.load(f)

    # --- Andrey present / absent -------------------------------------------

    def test_andrey_present_first_person_quote_led_posts_with_tags(self):
        out, buffer, codex = self.run_announcement(["", "a"], [QUOTE_PRESENT])

        self.assertIn(
            "On this episode: Andrey Devyatkin, Paulina Dubas, Mattias Hemmingsson, Jane Doe (guest) (Andrey present)", out
        )
        self.assertIn("Voice: first person (Andrey present)", out)
        self.assertIn("Quote evidence: [B] 00:28 -> Jane Doe (verified)", out)
        self.assertIn(f"Linked on LinkedIn: {COMPANY_PAGE}", out)
        self.assertIn("first person, in his own voice", codex.call_args.args[0])

        linkedin = next(p for p in buffer.created if p["channelId"] == LINKEDIN_ID)
        text = linkedin["text"]
        self.assertTrue(text.startswith('"Renaming a repository changes the OIDC sub claim'))
        self.assertIn("\n\nI had not connected a repo rename", text)
        self.assertIn(
            f"Episode 111 of {COMPANY_PAGE}, with @Jane Doe, @Paulina Dubas and @Mattias Hemmingsson.", text
        )
        self.assertIn(f"\n\n{PAGE_URL}\n\n", text)
        self.assertTrue(text.endswith("#DevSecOps #GitHubActions"))
        self.assertNotIn("@Andrey", text)
        self.assertEqual(linkedin["dueAt"], "2026-09-30T08:00:00.000Z")  # Wed 09:00 Atlantic/Canary

        x = next(p for p in buffer.created if p["channelId"] == X_ID)
        reply = x["metadata"]["twitter"]["thread"][0]["text"]
        self.assertNotIn("http", x["text"])
        self.assertIn("with @janedoe, @pauladubas and Mattias Hemmingsson.", reply)
        self.assertIn(PAGE_URL, reply)
        self.assertEqual(x["dueAt"], "2026-09-30T08:30:00.000Z")  # Wed 10:30 Europe/Stockholm

        self.assertEqual(set(self.ledger()), {LINKEDIN_ID, X_ID})
        self.assertEqual(self.saved()["quote_verified"], "transcript")
        with open(f"{self.out_base}{ba.RECORD_SUFFIX}", encoding="utf-8") as f:
            self.assertIn("quote_verified: transcript", f.read())
        with open(f"{self.out_base}-guests.json", encoding="utf-8") as f:
            guests = json.load(f)
        self.assertTrue(guests["andrey_present"])

    def test_andrey_absent_third_person_and_he_is_never_tagged(self):
        first_person = dict(QUOTE_ABSENT, context="We learned that a rename can lock you out of AWS.")
        out, buffer, codex = self.run_announcement(
            ["paulina, matte", "a"], [first_person, QUOTE_ABSENT],
        )

        self.assertIn("On this episode: Paulina Dubas, Mattias Hemmingsson, Jane Doe (guest) (Andrey absent)", out)
        self.assertIn("Voice: third person (Andrey absent)", out)
        self.assertIn("NOT on this episode", codex.call_args_list[0].args[0])
        self.assertIn("conversation with Paulina, Mattias and Jane Doe", codex.call_args_list[0].args[0])
        # The first-person draft was rejected and fed back once.
        self.assertIn("Andrey was not on this episode: no first person (We)", codex.call_args_list[1].args[0])

        text = next(p for p in buffer.created if p["channelId"] == LINKEDIN_ID)["text"]
        opener = text.split("\n\n")[1]
        self.assertTrue(opener.startswith("Paulina and Mattias with Jane"))
        self.assertEqual(ba.first_person_words(opener), [])
        self.assertEqual(
            ba.tag_set(ba.tagging_context(self.guest_context(["Paulina Dubas", "Mattias Hemmingsson"]), self.handles),
                       "linkedin"),
            ["@Jane Doe", "@Paulina Dubas", "@Mattias Hemmingsson"],
        )
        with open(f"{self.out_base}-guests.json", encoding="utf-8") as f:
            guests = json.load(f)
        self.assertEqual(guests["hosts_present"], ["Paulina Dubas", "Mattias Hemmingsson"])
        self.assertFalse(guests["andrey_present"])

    def test_no_turns_falls_back_to_a_quote_free_post(self):
        out, buffer, codex = self.run_announcement(["", "a"], [NO_QUOTE], turns=None)

        self.assertIn("no timestamped turns", codex.call_args.kwargs["stdin_text"])
        self.assertIn("Quote evidence: no verified quote", out)
        text = next(p for p in buffer.created if p["channelId"] == LINKEDIN_ID)["text"]
        self.assertTrue(text.startswith("A repository rename changes the OIDC sub claim"))
        self.assertNotIn('"', text)
        self.assertNotIn("Jane Doe -", text)
        saved = self.saved()
        self.assertEqual(saved["announcement"]["format"], "no_quote")
        self.assertEqual(saved["announcement"]["quote"], "")
        self.assertEqual(saved["quote_verified"], "none")

    # --- robustness ---------------------------------------------------------

    def test_ledger_keeps_successes_and_a_rerun_posts_only_the_missing_channel(self):
        out, _, _ = self.run_announcement(["", "a"], [QUOTE_PRESENT], buffer=FakeBuffer(fail_channels={X_ID}))
        self.assertEqual(set(self.ledger()), {LINKEDIN_ID})
        self.assertIn("re-run with --episode-number 111", out)

        retry = FakeBuffer()
        out, retry, codex = self.run_announcement(["", "", "a"], [])
        codex.assert_not_called()  # saved announcement reused: same inputs
        self.assertEqual([p["channelId"] for p in retry.created], [X_ID])
        self.assertIn("linkedin: already scheduled (post-68ca", out)
        self.assertEqual(set(self.ledger()), {LINKEDIN_ID, X_ID})
        with open(f"{self.out_base}{ba.LEDGER_SUFFIX}", encoding="utf-8") as f:
            self.assertEqual(len(f.read().splitlines()), 2)

        out, done, _ = self.run_announcement([], [])
        self.assertIn("already scheduled on every channel", out)
        self.assertEqual(done.calls, 0)

    def test_changed_inputs_invalidate_the_saved_copy(self):
        self.run_announcement(["", "a"], [QUOTE_PRESENT], buffer=FakeBuffer(fail_channels={X_ID}))
        other_page = PAGE.replace("111-", "111-renamed-")
        out, _, codex = self.run_announcement(["", "a"], [QUOTE_PRESENT], page=other_page)
        self.assertIn("built from other inputs", out)
        codex.assert_called_once()

    def test_historical_page_without_eligibility_skips_buffer(self):
        out, buffer, codex = self.run_announcement([], [], eligible=False)
        self.assertIn("skipping the Buffer announcement", out)
        self.assertEqual(buffer.calls, 0)
        codex.assert_not_called()

    def test_eligibility_keeps_the_original_release(self):
        ba.record_announcement_eligibility(self.out_base, RELEASE)
        ba.record_announcement_eligibility(self.out_base, RELEASE + dt.timedelta(days=30))
        self.assertEqual(ba.load_announcement_eligibility(self.out_base), RELEASE)

    def test_missing_or_disconnected_channel_fails_before_posting(self):
        broken = [dict(CHANNELS[0], isDisconnected=True)]
        out, buffer, codex = self.run_announcement([], [], buffer=FakeBuffer(channels=broken))
        self.assertIn("disconnected or locked", out)
        self.assertIn("is not in this Buffer account", out)
        self.assertEqual(buffer.created, [])
        codex.assert_not_called()

    def test_unverified_quote_needs_operator_override(self):
        misquoted = dict(QUOTE_PRESENT, quote="renaming a repository changes the OIDC claim and your AWS trust policy stops matching")
        out, buffer, _ = self.run_announcement(["", "o"], [misquoted, misquoted])
        self.assertIn("NOT VERIFIED", out)
        self.assertIn("{+sub+}", out)
        self.assertEqual(self.saved()["quote_verified"], "operator")
        self.assertEqual(len(buffer.created), 2)

    def test_overlong_x_reply_blocks_approval(self):
        crowd = [GUEST] + [{"full_name": f"Guest Number {n} With A Very Long Double-Barrelled Surname"}
                           for n in range(4)]
        out, buffer, _ = self.run_announcement(["", "a", "o", "s"], [QUOTE_PRESENT], guests=crowd)
        self.assertIn("error(s) block approval", out)
        self.assertIn("Approval blocked: the X reply is", out)
        self.assertIn("Approval is blocked by the errors above", out)
        self.assertNotIn("'a' to approve", out)
        self.assertEqual(buffer.created, [])
        self.assertFalse(os.path.exists(f"{self.out_base}{ba.SAVED_SUFFIX}"))

    def test_saved_announcement_with_rule_errors_is_not_scheduled(self):
        hosts = ["Andrey Devyatkin", "Paulina Dubas", "Mattias Hemmingsson"]
        context = self.guest_context(hosts)
        tags = ba.tagging_context(context, self.handles)
        inputs = ba.build_announcement_inputs(TURNS, context)
        bad = ba.clean_announcement(dict(QUOTE_PRESENT, context="A rename — then a lockout."), inputs)
        fingerprint = ba.announcement_fingerprint("transcript text", TURNS, PAGE_URL,
                                                  ba.announcement_target_date(RELEASE), tags)
        with open(f"{self.out_base}{ba.SAVED_SUFFIX}", "w", encoding="utf-8") as f:
            json.dump({"fingerprint": fingerprint, "announcement": bad, "quote_verified": "transcript"}, f)

        out, buffer, codex = self.run_announcement(["", "", "a"], [])
        codex.assert_not_called()
        self.assertIn("Found saved announcement", out)
        self.assertIn("Approval blocked: em dash in the copy", out)
        self.assertIn("Skipped the Buffer announcement.", out)
        self.assertEqual(buffer.created, [])

    def test_quote_person_must_match_the_speaker_map(self):
        mislabelled = dict(QUOTE_PRESENT, speaker_map=[{"label": "B", "person": "Paulina Dubas"}])
        out, buffer, _ = self.run_announcement(["", "a", "o"], [mislabelled])
        self.assertIn("Quote evidence: [B] 00:28 -> Jane Doe (NOT VERIFIED: speaker map has [B] as Paulina Dubas)", out)
        self.assertIn("'o' to post the quote anyway", out)
        self.assertEqual(self.saved()["quote_verified"], "operator")
        self.assertEqual(len(buffer.created), 2)

    def test_skip_schedules_nothing(self):
        _, buffer, _ = self.run_announcement(["", "s"], [QUOTE_PRESENT])
        self.assertEqual(buffer.created, [])
        self.assertFalse(os.path.exists(f"{self.out_base}{ba.SAVED_SUFFIX}"))

    def test_no_api_key_skips(self):
        out = StringIO()
        with patch.dict(os.environ, {}, clear=True), patch("buffer_announce.requests.post") as post, redirect_stdout(out):
            ba.schedule_episode_announcement(self.out_base, 111, PAGE, "t", "a", "t", TURNS, {}, NAMED_FILE)
        post.assert_not_called()
        self.assertIn("BUFFER_API_KEY not set", out.getvalue())


class QuoteEvidence(unittest.TestCase):
    def setUp(self):
        self.fixes = ba.load_spelling_fixes()

    def test_spelling_fixes_come_from_podcast_context(self):
        self.assertIn(("Matthias", "Mattias"), self.fixes)
        self.assertIn(("Andre", "Andrey"), self.fixes)

    def test_verbatim_ignoring_case_punctuation_and_name_spellings(self):
        result = ba.verify_quote_against_turns("That is why Mattias pins trust to the repository ID now", TURNS, "C", "01:40")
        self.assertTrue(result["verified"], result)

    def test_wrong_speaker_is_reported_with_the_real_turn(self):
        result = ba.verify_quote_against_turns("the ID survives a rename, a transfer, everything", TURNS, "C", "01:40")
        self.assertFalse(result["verified"])
        self.assertIn("quote is in [D] 02:40", result["reason"])

    def test_span_stitched_across_turns_fails(self):
        quote = "not the name. Right, and the ID survives a rename"
        self.assertFalse(ba.verify_quote_against_turns(quote, TURNS, "C", "01:40")["verified"])

    def test_timestamp_outside_the_turn_fails(self):
        result = ba.verify_quote_against_turns("the ID survives a rename, a transfer, everything", TURNS, "D", "10:00")
        self.assertFalse(result["verified"])
        self.assertIn("quote is in [D] 02:40, not [D] 10:00", result["reason"])

    def test_speaker_map_mismatch_and_missing_label_fail_the_check(self):
        inputs = ba.build_announcement_inputs(TURNS, {"guests": [GUEST]})
        ok = ba.check_quote(QUOTE_PRESENT, inputs)
        self.assertTrue(ok["verified"], ok)
        cased = dict(QUOTE_PRESENT, speaker_map=[{"label": "B", "person": "jane doe"}])
        self.assertTrue(ba.check_quote(cased, inputs)["verified"])
        missing = ba.check_quote(dict(QUOTE_PRESENT, speaker_map=[{"label": "A", "person": "Jane Doe"}]), inputs)
        self.assertFalse(missing["verified"])
        self.assertEqual(missing["reason"], "[B] is not in the speaker map")

    def test_posted_quote_uses_corrected_spellings(self):
        ann = dict(QUOTE_PRESENT, quote="That is why Matthias pins trust to the repository ID now", source_person="Paulina Dubas")
        self.assertTrue(ba.post_body(ann, self.fixes).startswith('"That is why Mattias pins'))

    def test_inputs_carry_timestamped_turns_and_people(self):
        inputs = ba.build_announcement_inputs(TURNS, {"hosts_present": ["Paulina Dubas"], "guests": [GUEST]})
        self.assertTrue(inputs["has_turns"])
        self.assertIn("[00:28] [B]: Thanks. So renaming", inputs["turns_text"])
        self.assertEqual(inputs["speakers"], ["A", "B", "C", "D"])
        self.assertEqual(inputs["people"], ["Paulina Dubas", "Jane Doe"])
        self.assertFalse(inputs["andrey_present"])
        self.assertFalse(ba.build_announcement_inputs(None, {})["has_turns"])


class HostsAndGuests(unittest.TestCase):
    def setUp(self):
        self.handles = ba.load_social_handles()

    def confirm(self, context, audio, answers, guests_file=None):
        answers = iter(answers)
        with redirect_stdout(StringIO()) as out:
            result = ba.confirm_hosts_present(context, audio, self.handles, guests_file=guests_file,
                                              input_func=lambda: next(answers))
        return result, out.getvalue()

    def test_filename_names_win_over_detection(self):
        context = {"guests": [], "hosts_present": ["Paulina Dubas"]}
        result, out = self.confirm(context, NAMED_FILE, [""])
        self.assertEqual(result["hosts_present"], ["Andrey Devyatkin", "Paulina Dubas", "Mattias Hemmingsson"])
        self.assertIn("disagree", out)

    def test_filename_without_names_uses_detection_and_can_be_corrected(self):
        context = {"guests": [GUEST], "hosts_present": ["Andrey Devyatkin", "Paulina Dubas"]}
        result, out = self.confirm(context, UNNAMED_FILE, ["pauline", "paulina, matte"])
        self.assertIn("On this episode: Andrey Devyatkin, Paulina Dubas, Jane Doe (guest) (Andrey present)", out)
        self.assertIn("Unknown host name(s): pauline", out)
        self.assertEqual(result["hosts_present"], ["Paulina Dubas", "Mattias Hemmingsson"])
        self.assertFalse(result["andrey_present"])

    def test_normalize_guest_context_keeps_hosts_and_guest_handles(self):
        data = normalize_guest_context({
            "status": "verified",
            "hosts_present": ["Mattias", "Julien Bisconti", "Andrey Devyatkin"],
            "guests": [{"full_name": "Jane Doe", "x_handle": "@janedoe"}],
        })
        self.assertEqual(data["hosts_present"], ["Andrey Devyatkin", "Mattias Hemmingsson"])
        self.assertTrue(data["andrey_present"])
        guest = data["guests"][0]
        self.assertEqual((guest["x_handle"], guest["linkedin_name"], guest["linkedin_url"]), ("janedoe", "", ""))

    def test_unconfirmed_linkedin_profile_credits_the_guest_in_plain_text(self):
        context = normalize_guest_context({"guests": [{"full_name": "Jane Doe"}],
                                           "hosts_present": ["Andrey Devyatkin", "Paulina Dubas"]})
        tags = ba.tagging_context(context, self.handles)
        self.assertIn("with Jane Doe and @Paulina Dubas.", ba.credits_line(tags, 111, "linkedin"))
        self.assertEqual(ba.tag_set(tags, "linkedin"), ["@Paulina Dubas"])
        warnings = ba.announcement_warnings(QUOTE_PRESENT, tags, 111, PAGE_URL)
        self.assertIn("not tagged on LinkedIn: Jane Doe (profile not confirmed)", warnings)
        self.assertFalse(any("plain text (no linkedin_name)" in w for w in warnings))


class CompanyCredit(unittest.TestCase):
    """Buffer does not resolve a LinkedIn Page @-mention, so the company is credited with its Page URL."""

    def setUp(self):
        self.handles = ba.load_social_handles()
        self.context = normalize_guest_context({"guests": [GUEST], "hosts_present": ["Paulina Dubas"]})

    def without_link(self):
        handles = json.loads(json.dumps(self.handles))
        del handles["company"]["linkedin_credit"]
        return handles

    def test_linkedin_credits_line_links_the_company_page(self):
        tags = ba.tagging_context(self.context, self.handles)
        self.assertEqual(ba.credits_line(tags, 111, "linkedin"),
                         f"Episode 111 of {COMPANY_PAGE}, with @Jane Doe and @Paulina Dubas.")
        self.assertNotIn("@DevSecOps Talks", ba.render_linkedin_post(QUOTE_PRESENT, tags, 111, PAGE_URL))

    def test_company_link_is_never_an_at_tag(self):
        tags = ba.tagging_context(self.context, self.handles)
        self.assertEqual(ba.tag_set(tags, "linkedin"), ["@Jane Doe", "@Paulina Dubas"])

    def test_x_still_names_the_company(self):
        tags = ba.tagging_context(self.context, self.handles)
        line = ba.credits_line(tags, 111, "x")
        self.assertIn("Episode 111 of DevSecOps Talks,", line)
        self.assertNotIn(COMPANY_PAGE, line)

    def test_linked_company_without_linkedin_name_is_not_warned_about(self):
        handles = json.loads(json.dumps(self.handles))
        handles["company"]["linkedin_name"] = None
        warnings = ba.announcement_warnings(QUOTE_PRESENT, ba.tagging_context(self.context, handles), 111, PAGE_URL)
        self.assertFalse(any("DevSecOps Talks" in w and "LinkedIn" in w for w in warnings))

    def test_without_linkedin_credit_the_company_falls_back_to_its_mention(self):
        tags = ba.tagging_context(self.context, self.without_link())
        self.assertTrue(ba.credits_line(tags, 111, "linkedin").startswith("Episode 111 of @DevSecOps Talks,"))


class Timing(unittest.TestCase):
    def test_target_is_two_days_after_release(self):
        self.assertEqual(ba.announcement_target_date(RELEASE), dt.date(2026, 9, 30))

    def test_due_at_skips_past_slots(self):
        late = dt.datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
        due = ba.announcement_due_at(CHANNELS[0], dt.date(2026, 9, 30), now=late)
        self.assertEqual(due, dt.datetime(2026, 10, 7, 8, 0, tzinfo=UTC))

    def test_page_url_is_the_hugo_path_of_the_page(self):
        self.assertEqual(ba.episode_page_url(PAGE), PAGE_URL)


if __name__ == "__main__":
    unittest.main()
