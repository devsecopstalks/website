"""Buffer announcement: quote check, drafters, approval before uploads, scheduling and ledger.

Drafters and the Buffer API are faked; nothing is posted.
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
THREADS_ID = "threads0000000000000001"
RELEASE = dt.datetime(2026, 9, 28, 11, 0, tzinfo=UTC)  # Monday Podbean slot
NOW = dt.datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
PAGE = "content/episodes/111-renaming-a-repo-can-lock-you-out-of-aws-with-jane-doe.md"
COMPANY_PAGE = "https://www.linkedin.com/company/devsecops-talks"
PAGE_URL = "https://devsecops.fm/episodes/111-renaming-a-repo-can-lock-you-out-of-aws-with-jane-doe/"
COVER_PATH = "/tmp/episode111-cover.png"
COVER_URL = "https://media.example.com/covers/111-0123456789ab.png"
TITLE = "Renaming a Repo Can Lock You Out of AWS with Jane Doe"
ALL_HOSTS = ("Andrey Devyatkin", "Paulina Dubas", "Mattias Hemmingsson")

TURNS = [
    {"speaker": "Andrey Devyatkin", "label": "S1", "start": 0.0, "end": 28.0,
     "text": "Welcome to DevSecOps Talks. I'm Andrey, with me Mattias and Paulina, and our guest Jane Doe."},
    {"speaker": "Jane Doe", "label": "S2", "start": 28.0, "end": 95.0,
     "text": "Thanks. So renaming a repository changes the OIDC sub claim, and your AWS trust policy silently stops matching."},
    {"speaker": "Jane Doe", "label": "S2", "start": 95.0, "end": 120.0,
     "text": "That is why we pin trust to the repository ID now, not the name."},
    {"speaker": "Mattias Hemmingsson", "label": "S3", "start": 120.0, "end": 160.0,
     "text": "Right, and the ID survives a rename, a transfer, everything you throw at it."},
    {"speaker": "Paulina Dubas", "label": "S4", "start": 160.0, "end": 200.0, "flagged": True,
     "text": "Dependabot will happily bump a pinned SHA to a malicious release if you let it."},
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
    "context": "I had not connected a repo rename with an AWS lockout until Jane walked us through it.",
    "theme_hashtag": "#GitHubActions",
}
QUOTE_ABSENT = dict(QUOTE_PRESENT, context="Paulina and Mattias with Jane on why a repo rename can lock you out of AWS.")
DISAGREEMENT = {
    "format": "disagreement",
    "quote": "",
    "context": "Mattias pins trust to the repository ID. Paulina thinks pinning just moves the risk to Dependabot.",
    "theme_hashtag": "#AWS",
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
    _channel(THREADS_ID, "threads", "andrey9kin", "Europe/Stockholm", "wed", "12:00"),
]


def test_handles():
    with open(ba.SOCIAL_HANDLES_FILE, encoding="utf-8") as f:
        handles = json.load(f)
    for channel in handles["buffer_channels"]:
        if channel["service"] == "threads":
            channel["id"] = THREADS_ID
    return handles


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

    def post_for(self, cid):
        return next(p for p in self.created if p["channelId"] == cid)


class FakeDrafter:
    """One drafter: answers in order, or raises what it is given."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.sources: list[str] = []

    def __call__(self, prompt, source, verbose=False):
        self.prompts.append(prompt)
        self.sources.append(source)
        item = self.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return dict(item)


def drafters(codex=(), claude=(), grok=()):
    return (("Codex", FakeDrafter(*codex)), ("Claude", FakeDrafter(*claude)), ("Grok", FakeDrafter(*grok)))


class AnnouncementCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out_base = os.path.join(self.tmp.name, "episode111")
        self.handles = test_handles()
        self.opener = MagicMock(return_value=MagicMock(returncode=0))

    def tearDown(self):
        self.tmp.cleanup()

    def guest_context(self, hosts=ALL_HOSTS, guests=(GUEST,)):
        return normalize_guest_context({"status": "verified", "guests": list(guests), "hosts_present": list(hosts)})

    def approve(self, answers, drafter_set=None, hosts=ALL_HOSTS, guests=(GUEST,), buffer=None,
                release=RELEASE, page_url=PAGE_URL, cover_url=COVER_URL):
        buffer = buffer or FakeBuffer()
        drafter_set = drafter_set or drafters()
        answers = iter(answers)

        def ask():
            try:
                return next(answers)
            except StopIteration:
                raise EOFError from None

        out = StringIO()
        with patch("buffer_announce.requests.post", side_effect=buffer), redirect_stdout(out):
            record = ba.approve_episode_announcement(
                self.out_base, 111, page_url, TITLE, "## Article\n\nBody.", TURNS,
                self.guest_context(hosts, guests), release, COVER_PATH, cover_url,
                input_func=ask, api_key="test-key", handles=self.handles, now=NOW,
                opener=self.opener, drafters=drafter_set,
            )
        return record, out.getvalue(), drafter_set

    def schedule(self, buffer=None, page=PAGE, hosts=ALL_HOSTS, cover_url=COVER_URL):
        buffer = buffer or FakeBuffer()
        out = StringIO()
        with patch("buffer_announce.requests.post", side_effect=buffer), redirect_stdout(out):
            ba.schedule_episode_announcement(self.out_base, 111, page, self.guest_context(hosts), cover_url,
                                             api_key="test-key", handles=self.handles, now=NOW)
        return out.getvalue(), buffer

    def ledger(self):
        return ba.load_ledger(f"{self.out_base}{ba.LEDGER_SUFFIX}")

    def saved(self):
        with open(f"{self.out_base}{ba.SAVED_SUFFIX}", encoding="utf-8") as f:
            return json.load(f)


class Approval(AnnouncementCase):
    def test_three_drafters_pick_with_the_cover_open_then_schedule_posts_exactly_that(self):
        record, out, (codex, claude, grok) = self.approve(
            ["2"], drafters([DISAGREEMENT], [QUOTE_PRESENT], [QUOTE_PRESENT]))

        self.assertIn("[1] Codex", out)
        self.assertIn("[2] Claude", out)
        self.assertIn("[3] Grok", out)
        self.assertIn("Quote by Jane Doe", out)
        self.assertIn("Tagged on Threads:", out)
        self.opener.assert_called_with(["open", COVER_PATH], check=False)
        self.assertIn("first person, in his own voice", codex[1].prompts[0])
        self.assertIn("Quote a guest (Jane Doe), never a host.", codex[1].prompts[0])
        self.assertIn("[00:28] [Jane Doe]: Thanks.", claude[1].sources[0])
        self.assertIn("(flagged: do not quote)", grok[1].sources[0])
        self.assertEqual(record["drafter"], "Claude")
        self.assertEqual(record["cover_url"], COVER_URL)
        self.assertEqual(record["target_date"], "2026-09-30")
        self.assertEqual(set(record["posts"]), {"linkedin", "twitter", "threads"})

        ba.record_announcement_eligibility(self.out_base, RELEASE)
        out, buffer = self.schedule()
        self.assertEqual(len(buffer.created), 3)
        linkedin = buffer.post_for(LINKEDIN_ID)
        self.assertEqual(linkedin["text"], record["posts"]["linkedin"]["text"])
        self.assertTrue(linkedin["text"].startswith('"Renaming a repository changes the OIDC sub claim'))
        self.assertIn('" - Jane Doe\n\nI had not connected', linkedin["text"])
        self.assertIn(f"Episode 111 of {COMPANY_PAGE}, with @Jane Doe, @Paulina Dubas and @Mattias Hemmingsson.",
                      linkedin["text"])
        self.assertTrue(linkedin["text"].endswith("#DevSecOps #GitHubActions"))
        self.assertNotIn("@Andrey", linkedin["text"])
        self.assertEqual(linkedin["dueAt"], "2026-09-30T08:00:00.000Z")  # Wed 09:00 Atlantic/Canary
        for post in buffer.created:
            self.assertEqual(post["assets"][0]["image"]["url"], COVER_URL)
            self.assertIn("episode 111", post["assets"][0]["image"]["metadata"]["altText"])

        x = buffer.post_for(X_ID)
        root, reply_entry = x["metadata"]["twitter"]["thread"]
        self.assertEqual(root["text"], x["text"])  # Buffer publishes the thread array, root included
        self.assertEqual(root["assets"][0]["image"]["url"], COVER_URL)
        self.assertEqual(reply_entry["assets"], [])
        reply = reply_entry["text"]
        self.assertNotIn("http", x["text"])
        self.assertIn("with @janedoe, @pauladubas and Mattias Hemmingsson.", reply)

        threads = buffer.post_for(THREADS_ID)
        self.assertIn("with Jane Doe, Paulina Dubas and Mattias Hemmingsson.", threads["text"])
        self.assertIn(PAGE_URL, threads["text"])
        self.assertEqual(threads["metadata"], {"threads": {"type": "post", "topic": "GitHubActions"}})

        ledger = self.ledger()
        self.assertEqual(set(ledger), {LINKEDIN_ID, X_ID, THREADS_ID})
        self.assertTrue(all(e["fingerprint"] == record["fingerprint"] for e in ledger.values()))
        with open(f"{self.out_base}{ba.RECORD_SUFFIX}", encoding="utf-8") as f:
            self.assertIn("## Threads", f.read())

    def test_andrey_absent_first_person_is_sent_back_once(self):
        first_person = dict(QUOTE_ABSENT, context="We learned that a rename can lock you out of AWS.")
        record, out, (codex, _, _) = self.approve(
            ["1"], drafters([first_person, QUOTE_ABSENT], [DISAGREEMENT], [DISAGREEMENT]),
            hosts=("Paulina Dubas", "Mattias Hemmingsson"))

        self.assertIn("Andrey absent", out)
        self.assertIn("NOT on this episode", codex[1].prompts[0])
        self.assertIn("conversation with Paulina, Mattias and Jane Doe", codex[1].prompts[0])
        self.assertIn("Andrey was not on this episode: no first person (We)", codex[1].prompts[1])
        self.assertTrue(record["posts"]["linkedin"]["text"].split("\n\n")[1].startswith("Paulina and Mattias"))

    def test_a_candidate_still_broken_after_the_retry_is_dropped(self):
        misquote = dict(QUOTE_PRESENT, quote="renaming a repo changes the OIDC claim and your AWS policy stops matching")
        record, out, _ = self.approve(["1"], drafters([misquote, misquote], [DISAGREEMENT], [DISAGREEMENT]))
        self.assertIn("Codex: still breaks rules after one retry", out)
        self.assertIn("is not word for word in the transcript", out)
        self.assertNotIn("[3]", out)
        self.assertEqual(record["drafter"], "Claude")

    def test_a_crashed_drafter_is_left_out_and_all_crashing_stops(self):
        record, out, _ = self.approve(
            ["1"], drafters([RuntimeError("timed out after 900s")], [QUOTE_PRESENT], [DISAGREEMENT]))
        self.assertIn("Codex: drafting failed (RuntimeError: timed out after 900s)", out)
        self.assertEqual(record["drafter"], "Claude")

        os.remove(f"{self.out_base}{ba.SAVED_SUFFIX}")
        broken = drafters([RuntimeError("a")], [RuntimeError("b")], [RuntimeError("c")])
        with self.assertRaises(ba.AnnouncementStop) as stop:
            self.approve([], broken)
        self.assertIn("every announcement drafter failed", str(stop.exception))

    def test_regenerate_feeds_rejected_drafts_and_guidance_to_every_drafter(self):
        record, _, (codex, _, grok) = self.approve(
            ["r", "use the line about the ID", "3"],
            drafters([DISAGREEMENT, DISAGREEMENT], [DISAGREEMENT, DISAGREEMENT], [DISAGREEMENT, QUOTE_PRESENT]))
        self.assertNotIn("Drafts the operator already rejected", codex[1].prompts[0])
        self.assertIn("Mattias pins trust to the repository ID", grok[1].prompts[1])
        self.assertIn("Operator guidance after round 1: use the line about the ID", grok[1].prompts[1])
        self.assertEqual(record["drafter"], "Grok")
        rows = ba.load_rejected(f"{self.out_base}{ba.REJECTED_SUFFIX}", record["fingerprint"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["posts"]), 3)

    def test_saved_approval_is_reused_and_changed_inputs_draft_again(self):
        first, _, _ = self.approve(["1"], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]))
        record, out, (codex, _, _) = self.approve([""])
        self.assertIn("Found the approved announcement (Codex)", out)
        self.assertEqual(codex[1].prompts, [])
        self.assertEqual(record["fingerprint"], first["fingerprint"])

        record, out, _ = self.approve(["2"], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]),
                                      cover_url=COVER_URL.replace("0123", "9999"))
        self.assertIn("built from other inputs", out)
        self.assertNotEqual(record["fingerprint"], first["fingerprint"])

    def test_old_format_saved_announcement_is_drafted_again(self):
        with open(f"{self.out_base}{ba.SAVED_SUFFIX}", "w", encoding="utf-8") as f:
            json.dump({"fingerprint": "x", "announcement": dict(QUOTE_PRESENT, speaker_map=[]),
                       "quote_verified": "transcript"}, f)
        record, out, _ = self.approve(["1"], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]))
        self.assertIn("older format", out)
        self.assertEqual(record["schema"], ba.SAVED_SCHEMA)

    def test_skip_is_remembered_for_the_same_inputs(self):
        record, _, _ = self.approve(["s"], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]))
        self.assertIsNone(record)
        self.assertTrue(self.saved()["skipped"])
        record, out, _ = self.approve([])
        self.assertIsNone(record)
        self.assertIn("skipped at an earlier pick", out)

        ba.record_announcement_eligibility(self.out_base, RELEASE)
        out, buffer = self.schedule()
        self.assertIn("Skipped the Buffer announcement", out)
        self.assertEqual(buffer.calls, 0)

    def test_no_answer_at_the_pick_stops(self):
        with self.assertRaises(ba.AnnouncementStop) as stop:
            self.approve([], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]))
        self.assertIn("no answer at the announcement pick", str(stop.exception))

    def test_not_released_by_this_pipeline_gets_no_announcement(self):
        buffer = FakeBuffer()
        record, out, _ = self.approve([], release=None, buffer=buffer)
        self.assertIsNone(record)
        self.assertIn("gets no Buffer announcement", out)
        self.assertEqual(buffer.calls, 0)

    def test_eligibility_release_wins_over_the_passed_one(self):
        ba.record_announcement_eligibility(self.out_base, RELEASE + dt.timedelta(days=7))
        record, _, _ = self.approve(["1"], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]))
        self.assertEqual(record["target_date"], "2026-10-07")

    def test_eligibility_keeps_the_original_release(self):
        ba.record_announcement_eligibility(self.out_base, RELEASE)
        ba.record_announcement_eligibility(self.out_base, RELEASE + dt.timedelta(days=30))
        self.assertEqual(ba.load_announcement_eligibility(self.out_base), RELEASE)


class Preflight(AnnouncementCase):
    def test_missing_threads_id_stops_and_names_the_buffer_channel(self):
        handles = test_handles()
        handles["buffer_channels"][2]["id"] = None
        with patch("buffer_announce.requests.post", side_effect=FakeBuffer()):
            with self.assertRaises(ba.AnnouncementStop) as stop:
                ba.preflight_buffer("key", handles)
        self.assertIn("no Threads channel id in social-handles.json", str(stop.exception))
        self.assertIn(f"Buffer has: andrey9kin ({THREADS_ID})", str(stop.exception))

    def test_missing_service_or_disconnected_channel_stops(self):
        broken = [dict(CHANNELS[0], isDisconnected=True), CHANNELS[1]]
        with patch("buffer_announce.requests.post", side_effect=FakeBuffer(channels=broken)):
            with self.assertRaises(ba.AnnouncementStop) as stop:
                ba.preflight_buffer("key", self.handles)
        self.assertIn("disconnected or locked", str(stop.exception))
        self.assertIn(f"Threads ({THREADS_ID}) is not in this Buffer account", str(stop.exception))

    def test_no_api_key_stops(self):
        with patch.dict(os.environ, {}, clear=True), patch("buffer_announce.requests.post") as post:
            with self.assertRaises(ba.AnnouncementStop) as stop:
                ba.preflight_buffer(None, self.handles)
        post.assert_not_called()
        self.assertIn("BUFFER_API_KEY is not set", str(stop.exception))

    def test_channel_without_a_slot_stops_when_a_target_is_given(self):
        empty = [CHANNELS[0], CHANNELS[1], dict(CHANNELS[2], postingSchedule=[])]
        with patch("buffer_announce.requests.post", side_effect=FakeBuffer(channels=empty)):
            with self.assertRaises(ba.AnnouncementStop) as stop:
                ba.preflight_buffer("key", self.handles, target=dt.date(2026, 9, 30), now=NOW)
        self.assertIn("Threads: no usable slot", str(stop.exception))

    def test_approval_checks_buffer_before_drafting(self):
        handles = test_handles()
        handles["buffer_channels"][2]["id"] = None
        self.handles = handles
        drafter_set = drafters([QUOTE_PRESENT])
        with self.assertRaises(ba.AnnouncementStop):
            self.approve([], drafter_set)
        self.assertEqual(drafter_set[0][1].prompts, [])


class Scheduling(AnnouncementCase):
    def approved(self):
        record, _, _ = self.approve(["1"], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]))
        ba.record_announcement_eligibility(self.out_base, RELEASE)
        return record

    def test_failed_channel_raises_and_a_rerun_posts_only_it(self):
        self.approved()
        with self.assertRaises(ba.AnnouncementStop) as stop:
            self.schedule(FakeBuffer(fail_channels={X_ID}))
        self.assertIn("Buffer failed on twitter", str(stop.exception))
        self.assertEqual(set(self.ledger()), {LINKEDIN_ID, THREADS_ID})

        out, retry = self.schedule()
        self.assertEqual([p["channelId"] for p in retry.created], [X_ID])
        self.assertEqual(set(self.ledger()), {LINKEDIN_ID, X_ID, THREADS_ID})

        out, done = self.schedule()
        self.assertIn("already scheduled on every channel", out)
        self.assertEqual(done.created, [])

    def test_ledger_line_from_other_inputs_warns_and_is_never_reposted(self):
        self.approved()
        ba.append_ledger(f"{self.out_base}{ba.LEDGER_SUFFIX}",
                         {"channel_id": LINKEDIN_ID, "service": "linkedin", "post_id": "old-post"})
        out, buffer = self.schedule()
        self.assertIn("LinkedIn already carries a post from other inputs (old-post); not reposting", out)
        self.assertEqual(sorted(p["channelId"] for p in buffer.created), sorted([X_ID, THREADS_ID]))

    def test_page_that_moved_since_approval_stops_and_the_next_run_asks_again(self):
        self.approved()
        with self.assertRaises(ba.AnnouncementStop) as stop:
            self.schedule(page=PAGE.replace("111-", "111-renamed-"))
        self.assertIn("no longer matches what would be posted", str(stop.exception))
        self.assertIn("page URL is", str(stop.exception))
        self.assertFalse(os.path.exists(f"{self.out_base}{ba.SAVED_SUFFIX}"))
        self.assertTrue(os.path.exists(f"{self.out_base}{ba.STALE_SUFFIX}"))
        self.assertEqual(self.ledger(), {})

    def test_changed_cover_url_stops(self):
        self.approved()
        with self.assertRaises(ba.AnnouncementStop) as stop:
            self.schedule(cover_url=COVER_URL.replace("0123", "9999"))
        self.assertIn("cover URL is", str(stop.exception))

    def test_historical_page_without_eligibility_posts_nothing(self):
        self.approve(["1"], drafters([QUOTE_PRESENT], [DISAGREEMENT], [DISAGREEMENT]))
        out, buffer = self.schedule()
        self.assertIn("not released by this pipeline", out)
        self.assertEqual(buffer.calls, 0)


class QuoteCheck(unittest.TestCase):
    def setUp(self):
        self.with_guest = {"guests": [GUEST], "hosts_present": list(ALL_HOSTS)}
        self.no_guest = {"guests": [], "hosts_present": list(ALL_HOSTS)}

    def test_word_for_word_ignoring_case_and_punctuation(self):
        speaker, problems = ba.quote_check("Renaming a repository changes the OIDC sub claim; and your AWS trust",
                                           TURNS, self.with_guest)
        self.assertEqual((speaker, problems), ("Jane Doe", []))

    def test_a_span_may_run_across_one_speakers_consecutive_turns(self):
        quote = "your AWS trust policy silently stops matching. That is why we pin trust to the repository ID"
        self.assertEqual(ba.quote_check(quote, TURNS, self.with_guest), ("Jane Doe", []))

    def test_a_span_across_two_speakers_fails(self):
        quote = "not the name. Right, and the ID survives a rename"
        _, problems = ba.quote_check(quote, TURNS, self.with_guest)
        self.assertIn("is not within one speaker's consecutive turns", problems[0])

    def test_changed_words_fail(self):
        _, problems = ba.quote_check("renaming a repo changes the OIDC claim", TURNS, self.with_guest)
        self.assertIn("is not word for word in the transcript", problems[0])

    def test_host_quote_needs_an_episode_without_a_guest(self):
        quote = "the ID survives a rename, a transfer, everything you throw at it"
        _, problems = ba.quote_check(quote, TURNS, self.with_guest)
        self.assertIn("quote is from host Mattias Hemmingsson", problems[0])
        self.assertEqual(ba.quote_check(quote, TURNS, self.no_guest), ("Mattias Hemmingsson", []))

    def test_flagged_turn_cannot_be_quoted(self):
        _, problems = ba.quote_check("Dependabot will happily bump a pinned SHA to a malicious release",
                                     TURNS, self.no_guest)
        self.assertIn("left flagged", problems[0])

    def test_ellipsis_and_numbers_keep_their_meaning(self):
        self.assertIn("ellipsis", ba.quote_check("renaming a repository ... stops matching", TURNS, self.with_guest)[1][0])
        self.assertNotEqual(ba.quote_words("-5%"), ba.quote_words("5"))

    def test_first_name_speaker_resolves_to_the_full_name(self):
        turns = [dict(TURNS[3], speaker="Mattias")]
        quote = "the ID survives a rename, a transfer, everything you throw at it"
        self.assertEqual(ba.quote_check(quote, turns, self.no_guest), ("Mattias Hemmingsson", []))

    def test_model_cannot_choose_who_is_credited(self):
        inputs = ba.build_announcement_inputs(TURNS, self.with_guest)
        tags = ba.tagging_context(self.with_guest, test_handles())
        ann, errors = ba.check_announcement(dict(QUOTE_PRESENT, source_person="Paulina Dubas"), inputs, tags,
                                            111, PAGE_URL)
        self.assertEqual(errors, [])
        self.assertEqual(ann["source_person"], "Jane Doe")

    def test_overlong_x_reply_is_a_rule_violation(self):
        crowd = [GUEST] + [{"full_name": f"Guest Number {n} With A Very Long Double-Barrelled Surname"}
                           for n in range(4)]
        context = normalize_guest_context({"guests": crowd, "hosts_present": list(ALL_HOSTS)})
        inputs = ba.build_announcement_inputs(TURNS, context)
        _, errors = ba.check_announcement(QUOTE_PRESENT, inputs, ba.tagging_context(context, test_handles()),
                                          111, PAGE_URL)
        self.assertTrue(any(e.startswith("the X reply is") for e in errors), errors)


class CompanyCredit(unittest.TestCase):
    """Buffer does not resolve a LinkedIn Page @-mention, so the company is credited with its Page URL."""

    def setUp(self):
        self.handles = test_handles()
        self.context = normalize_guest_context({"guests": [GUEST], "hosts_present": ["Paulina Dubas"]})

    def test_linkedin_credits_line_links_the_company_page(self):
        tags = ba.tagging_context(self.context, self.handles)
        self.assertEqual(ba.credits_line(tags, 111, "linkedin"),
                         f"Episode 111 of {COMPANY_PAGE}, with @Jane Doe and @Paulina Dubas.")
        self.assertEqual(ba.tag_set(tags, "linkedin"), ["@Jane Doe", "@Paulina Dubas"])

    def test_x_and_threads_name_the_company(self):
        tags = ba.tagging_context(self.context, self.handles)
        self.assertTrue(ba.credits_line(tags, 111, "x").startswith("Episode 111 of DevSecOps Talks,"))
        self.assertTrue(ba.credits_line(tags, 111, "threads").startswith("Episode 111 of DevSecOps Talks,"))

    def test_threads_tags_by_threads_handle_when_known(self):
        context = normalize_guest_context({"guests": [GUEST], "hosts_present": ["Paulina Dubas"]})
        context["guests"][0]["threads_handle"] = "jane.doe"
        tags = ba.tagging_context(context, self.handles)
        self.assertEqual(ba.credits_line(tags, 111, "threads"),
                         "Episode 111 of DevSecOps Talks, with @jane.doe and Paulina Dubas.")
        self.assertIn("credited on Threads in plain text (no threads_handle): DevSecOps Talks, Paulina Dubas",
                      ba.announcement_warnings(tags))

    def test_unconfirmed_linkedin_profile_credits_the_guest_in_plain_text(self):
        context = normalize_guest_context({"guests": [{"full_name": "Jane Doe"}], "hosts_present": ["Paulina Dubas"]})
        tags = ba.tagging_context(context, self.handles)
        self.assertIn("with Jane Doe and @Paulina Dubas.", ba.credits_line(tags, 111, "linkedin"))
        self.assertIn("not tagged on LinkedIn: Jane Doe (profile not confirmed)", ba.announcement_warnings(tags))


class Timing(unittest.TestCase):
    def test_target_is_two_days_after_release(self):
        self.assertEqual(ba.announcement_target_date(RELEASE), dt.date(2026, 9, 30))

    def test_due_at_skips_past_slots(self):
        late = dt.datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
        due = ba.announcement_due_at(CHANNELS[0], dt.date(2026, 9, 30), now=late)
        self.assertEqual(due, dt.datetime(2026, 10, 7, 8, 0, tzinfo=UTC))

    def test_page_url_is_the_hugo_path_of_the_page(self):
        self.assertEqual(ba.episode_page_url(PAGE), PAGE_URL)


class Drafters(unittest.TestCase):
    def test_grok_runs_with_its_prompt_replaced_and_returns_structured_output(self):
        result = MagicMock(returncode=0, stdout=json.dumps({"structuredOutput": QUOTE_PRESENT}))
        with patch("buffer_announce.subprocess.run", return_value=result) as run:
            self.assertEqual(ba.draft_with_grok("prompt", "source"), QUOTE_PRESENT)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "grok")
        for flag in ("--prompt-file", "--json-schema", "--system-prompt-override", "--no-subagents"):
            self.assertIn(flag, cmd)

    def test_claude_returns_structured_output_and_timeouts_raise(self):
        result = MagicMock(returncode=0, stdout=json.dumps({"structured_output": QUOTE_PRESENT}))
        with patch("buffer_announce.subprocess.run", return_value=result) as run:
            self.assertEqual(ba.draft_with_claude("prompt", "source"), QUOTE_PRESENT)
        self.assertIn("--json-schema", run.call_args.args[0])
        import subprocess
        with patch("buffer_announce.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 1)):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                ba.draft_with_claude("prompt", "source")


if __name__ == "__main__":
    unittest.main()
