"""
Episode announcement on Andrey's personal LinkedIn, X and Threads, scheduled
through Buffer's GraphQL API. One moment from the episode: a quote copied word
for word from the corrected transcript, or a named disagreement.

Two halves, so every question comes before the uploads:

- approve_episode_announcement (before any upload): Codex, Claude and Grok
  draft in parallel, the operator picks one with the cover open, and the
  rendered posts are saved.
- schedule_episode_announcement (after the page is written): posts exactly the
  saved posts and asks nothing.

Missing pieces raise AnnouncementStop; the orchestrator turns it into a stop.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from episode_metadata import DEVSECOPS_HASHTAG, SITE_URL, format_turn_line
from episode_pipeline import (
    AUTHOR_HOST,
    CLAUDE_TIMEOUT_S,
    CODEX_MODEL,
    CODEX_TIMEOUT_S,
    PROMPTS_DIR,
    REPO_ROOT,
    SHOW_HOSTS,
    _extract_json_object,
    guest_full_names,
    load_prompt,
)

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
SOCIAL_HANDLES_FILE = os.path.join(TOOLS_DIR, "social-handles.json")
ANNOUNCEMENT_SCHEMA = os.path.join(PROMPTS_DIR, "announcement-schema.json")
GROK_TIMEOUT_S = int(os.environ.get("GROK_TIMEOUT_S", "900"))
CLAUDE_MODEL = "claude-opus-5"

BUFFER_API_URL = "https://api.buffer.com"
# Earliest announcement date after release: Wednesday for the Monday Podbean slot.
ANNOUNCEMENT_LEAD_DAYS = 2
# Every one must be configured and connected; the run stops before uploads otherwise.
REQUIRED_SERVICES = ("linkedin", "twitter", "threads")
SERVICE_NAMES = {"linkedin": "LinkedIn", "twitter": "X", "threads": "Threads"}

FORMATS = ("quote", "disagreement")
QUOTE_WORDS = (8, 30)
X_POST_LIMIT = 280
THREADS_POST_LIMIT = 500
# X counts every link as 23 characters whatever its length.
# https://docs.x.com/fundamentals/counting-characters
X_URL_WEIGHT = 23
_URL_RE = re.compile(r"https?://\S+")
_HASHTAG_RE = re.compile(r"^#[A-Za-z][A-Za-z0-9]*$")
_FIRST_PERSON = {
    "I", "I'm", "I've", "I'd", "I'll", "me", "Me", "my", "My",
    "we", "We", "we're", "We're", "we've", "We've", "our", "Our", "ours", "us",
}
_QUOTE_CHARS = "\"“”"

ELIGIBILITY_SUFFIX = "-announcement-eligible.json"
LEDGER_SUFFIX = "-announcement-scheduled.txt"
SAVED_SUFFIX = "-announcement.json"
STALE_SUFFIX = "-announcement.stale.json"
REJECTED_SUFFIX = "-announcement-rejected.jsonl"
RECORD_SUFFIX = "-announcement.md"
# Saved approvals from before this shape (speaker labels, LinkedIn and X only) are regenerated.
SAVED_SCHEMA = 2

CREATE_POST_MUTATION = """mutation ($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id dueAt status channelService } }
    ... on InvalidInputError { message }
    ... on UnauthorizedError { message }
    ... on NotFoundError { message }
    ... on LimitReachedError { message }
    ... on UnexpectedError { message }
    ... on RestProxyError { code message link }
  }
}"""

CHANNELS_QUERY = """query ($input: ChannelsInput!) {
  channels(input: $input) {
    id name service displayName isDisconnected isLocked isQueuePaused timezone
    postingSchedule { day times }
  }
}"""

_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_UTC = ZoneInfo("UTC")


class AnnouncementStop(RuntimeError):
    """The announcement cannot go ahead as configured; the run must stop, not skip it."""


# --- quote evidence ---------------------------------------------------------
# Quotes are checked against the corrected transcript: turns named by speaker
# ({"speaker": "Jane Doe", "start", "end", "text", "flagged"}), not raw labels.

# Quotes, dashes and non-breaking spaces fold to one form, so typography the
# model picked does not decide whether a quote matches.
_QUOTE_FOLD = str.maketrans({
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "–": "-", "—": "-", "‒": "-", "―": "-", "−": "-",
    " ": " ",
})
_ELLIPSIS_RE = re.compile(r"\.\.\.|…")
# A sign or currency before a number, a decimal, and %, # or + after a word stay
# on it, because they change what the word means: "-5%" is not "5".
_QUOTE_TOKEN_RE = re.compile(
    r"(?P<sign>(?<![\w'])[-+](?=[$€£]?\d))?"
    r"(?P<currency>[$€£](?=\d))?"
    r"(?P<core>[\w']+(?:(?<=\d)[.,]\d+)*)"
    r"(?P<suffix>(?:\+\+|\+|#|%)(?!\w))?"
)


def quote_words(text: str) -> str:
    """Space-padded lowercase words without punctuation: the form quotes and turns are compared in."""
    folded = str(text or "").translate(_QUOTE_FOLD).casefold()
    words = []
    for m in _QUOTE_TOKEN_RE.finditer(folded):
        core = m["core"].strip("'")
        if core:
            words.append((m["sign"] or "") + (m["currency"] or "") + core + (m["suffix"] or ""))
    return " " + " ".join(words) + " "


def speaker_role(speaker: str, guest_context: dict | None) -> tuple[str, str]:
    """("guest" | "host" | "", full name) for a speaker as the transcript names them.

    A lone first name that fits exactly one person counts too.
    """
    people = [("guest", name) for name in guest_full_names(guest_context)]
    people += [("host", name) for name in SHOW_HOSTS]
    wanted = " ".join(str(speaker or "").split()).casefold()
    for role, name in people:
        if name.casefold() == wanted:
            return role, name
    first = [(role, name) for role, name in people if name.split()[0].casefold() == wanted]
    return first[0] if len(first) == 1 else ("", str(speaker or ""))


def speaker_runs(turns, guest_context: dict | None) -> list[dict]:
    """Each stretch of consecutive turns by one speaker, in quote_words form.

    ``flagged`` holds the character spans of turns the transcript review left
    flagged, so a quote drawn from one is refused.
    """
    runs: list[dict] = []
    for turn in turns or ():
        words = quote_words(turn.get("text"))
        if not words.strip():
            continue
        speaker = str(turn.get("speaker") or turn.get("label") or "").strip()
        speaker = speaker_role(speaker, guest_context)[1] or speaker
        if not runs or runs[-1]["speaker"] != speaker:
            runs.append({"speaker": speaker, "text": " ", "flagged": []})
        run = runs[-1]
        start = len(run["text"]) - 1
        run["text"] += words[1:]
        if turn.get("flagged"):
            run["flagged"].append((start, len(run["text"])))
    return runs


def _touches_flagged(run: dict, span: tuple[int, int]) -> bool:
    # Interiors only: neighbouring turns share the space between them.
    s, e = span
    return any(s + 1 < f_end - 1 and f_start + 1 < e - 1 for f_start, f_end in run["flagged"])


def quote_check(quote: str, turns, guest_context: dict | None) -> tuple[str, list[str]]:
    """Who said ``quote`` ("" when it cannot run), and why it cannot.

    It must be word for word inside one speaker's consecutive turns: a guest's,
    or a host's when the episode has no guest, and not from a flagged turn.
    """
    wanted = quote_words(quote)
    if not wanted.strip():
        return "", ["quote is empty"]
    if _ELLIPSIS_RE.search(str(quote)):
        return "", ["quote contains an ellipsis; use one contiguous span"]
    runs = speaker_runs(turns, guest_context)
    hits = [(run, (i, i + len(wanted))) for run in runs if (i := run["text"].find(wanted)) >= 0]
    if not hits:
        whole = " " + "".join(run["text"][1:] for run in runs)
        where = ("is not within one speaker's consecutive turns" if wanted in whole
                 else "is not word for word in the transcript")
        return "", [f'quote "{quote}" {where}']
    said_by = sorted({run["speaker"] for run, _ in hits})
    if len(said_by) > 1:
        return "", [f'quote "{quote}" was said by {_name_list(said_by)}; quote words only one person said']
    if all(_touches_flagged(run, span) for run, span in hits):
        return "", [f'quote "{quote}" comes from a turn the transcript review left flagged']
    role, name = speaker_role(said_by[0], guest_context)
    if not role:
        return "", [f'quote "{quote}" is from {said_by[0]}, who is not a known guest or host']
    if role == "host" and guest_full_names(guest_context):
        return "", [f"quote is from host {name}; on an episode with a guest, quote the guest"]
    return name, []


def usable_turns(turns) -> list[dict]:
    return [t for t in turns or [] if isinstance(t, dict) and str(t.get("text") or "").strip()]


def transcript_text(turns) -> str:
    """``[MM:SS] [Name]: text`` per turn; flagged turns are marked as not quotable."""
    return "\n".join(
        format_turn_line(t) + ("  (flagged: do not quote)" if t.get("flagged") else "")
        for t in usable_turns(turns)
    )


def build_announcement_inputs(turns: list[dict] | None, guest_context: dict | None) -> dict:
    """What generation sees: the corrected turns and who was on the episode."""
    guest_context = guest_context or {}
    hosts = [h for h in guest_context.get("hosts_present") or [] if h]
    guests = guest_full_names(guest_context)
    usable = usable_turns(turns)
    return {
        "turns": usable,
        "turns_text": transcript_text(usable),
        "hosts_present": hosts,
        "andrey_present": AUTHOR_HOST in hosts,
        "guests": guests,
        "guest_context": guest_context,
    }


# --- people and tags --------------------------------------------------------


def load_social_handles(path: str | None = None) -> dict:
    """Hosts, company and Buffer channels; unreadable stops the run, since every channel is required."""
    path = path or SOCIAL_HANDLES_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise AnnouncementStop(f"could not read {path} ({e})") from e


def person_line(hosts_present, guests) -> str:
    names = list(hosts_present or []) + [f"{g} (guest)" for g in guests or []]
    presence = "present" if AUTHOR_HOST in (hosts_present or []) else "absent"
    return f"On this episode: {', '.join(names) or 'no hosts confirmed'} (Andrey {presence})"


def _entity(name, linkedin_name, url, x_handle, threads_handle, entity_type) -> dict:
    """One credited party; an empty handle credits it in plain text on that network."""
    return {
        "name": str(name).strip(),
        "linkedin_name": str(linkedin_name or "").strip(),
        "linkedin_url": str(url or "").strip(),
        "x_handle": str(x_handle or "").strip().lstrip("@"),
        "threads_handle": str(threads_handle or "").strip().lstrip("@"),
        "entity_type": entity_type,
    }


def tagging_context(guest_context: dict | None, handles: dict | None = None) -> dict:
    """Guest context, hosts present and handles as one value, so every render credits the same people."""
    guest_context = guest_context or {}
    return {
        "guest_context": guest_context,
        "hosts_present": tuple(guest_context.get("hosts_present") or ()),
        "handles": handles if handles is not None else load_social_handles(),
    }


def credited_people(tags: dict) -> list[dict]:
    """Guests, then hosts present; never the author, who owns the channels."""
    handles = tags.get("handles") or {}
    author = str(handles.get("author") or AUTHOR_HOST).strip()
    people: list[dict] = []
    for guest in tags["guest_context"].get("guests") or []:
        name = str((guest or {}).get("full_name") or "").strip() if isinstance(guest, dict) else ""
        if name:
            # No full-name fallback: an @-tag on an unconfirmed profile can tag a stranger.
            people.append(_entity(name, guest.get("linkedin_name"), guest.get("linkedin_url"),
                                  guest.get("x_handle"), guest.get("threads_handle"), "person"))
    by_name = {str(h.get("name") or ""): h for h in handles.get("hosts") or [] if isinstance(h, dict)}
    for name in tags["hosts_present"]:
        if name == author:
            continue
        host = by_name.get(name) or {}
        people.append(_entity(name, host.get("linkedin_name"), host.get("linkedin_url"), host.get("x_handle"),
                              host.get("threads_handle"), "person"))
    return people


def company_entity(handles: dict) -> dict | None:
    company = (handles or {}).get("company")
    if not isinstance(company, dict) or not company.get("name"):
        return None
    entity = _entity(company["name"], company.get("linkedin_name"), company.get("linkedin_url"),
                     company.get("x_handle"), company.get("threads_handle"), "organization")
    # Literal LinkedIn text used in place of the @mention: Buffer does not resolve Page mentions.
    entity["linkedin_credit"] = str(company.get("linkedin_credit") or "").strip()
    return entity


def _credit(entity: dict, channel: str) -> str:
    if channel == "linkedin" and entity.get("linkedin_credit"):
        return entity["linkedin_credit"]
    handle = {"x": entity["x_handle"], "threads": entity["threads_handle"]}.get(channel, entity["linkedin_name"])
    return f"@{handle}" if handle else entity["name"]


def _name_list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def credits_line(tags: dict, episode_number: int, channel: str) -> str:
    company = company_entity(tags.get("handles") or {})
    line = f"Episode {episode_number}" + (f" of {_credit(company, channel)}" if company else "")
    people = [_credit(p, channel) for p in credited_people(tags)]
    return line + (f", with {_name_list(people)}" if people else "") + "."


def tag_set(tags: dict, channel: str) -> list[str]:
    """Every @-mention the rendered posts carry on one channel."""
    company = company_entity(tags.get("handles") or {})
    entities = ([company] if company else []) + credited_people(tags)
    return [c for c in (_credit(e, channel) for e in entities) if c.startswith("@")]


# --- rendering and validation -----------------------------------------------


def clean_announcement(raw: dict) -> dict:
    """Coerce model output to the rendered shape: no quote outside ``quote`` format."""
    ann = {key: " ".join(str(raw.get(key) or "").split()) for key in ("format", "quote", "context", "theme_hashtag")}
    ann["quote"] = ann["quote"].strip(_QUOTE_CHARS + " ")
    ann["source_person"] = ""
    if ann["format"] != "quote":
        ann["quote"] = ""
    if ann["theme_hashtag"].casefold() == DEVSECOPS_HASHTAG.casefold():
        ann["theme_hashtag"] = ""
    return ann


def hashtags(ann: dict) -> list[str]:
    theme = ann.get("theme_hashtag") or ""
    return [DEVSECOPS_HASHTAG] + ([theme] if _HASHTAG_RE.match(theme) else [])


def post_body(ann: dict) -> str:
    """Quote-led when there is a quote; otherwise the context carries the post."""
    if ann.get("format") == "quote" and ann.get("quote"):
        quote = ann["quote"]
        return f"\"{quote[:1].upper()}{quote[1:]}\" - {ann.get('source_person')}\n\n{ann['context']}"
    return ann.get("context") or ""


def render_linkedin_post(ann: dict, tags: dict, episode_number: int, page_url: str) -> str:
    blocks = [post_body(ann), credits_line(tags, episode_number, "linkedin"), page_url, " ".join(hashtags(ann))]
    return "\n\n".join(b for b in blocks if b)


def render_x_posts(ann: dict, tags: dict, episode_number: int, page_url: str) -> list[str]:
    """One post, then one reply carrying the credits and the link."""
    reply = f"{credits_line(tags, episode_number, 'x')}\n\n{page_url}\n\n{' '.join(hashtags(ann))}"
    return [post_body(ann), reply]


def render_threads_post(ann: dict, tags: dict, episode_number: int, page_url: str) -> str:
    """The same body, credits and link inline; the topic travels as metadata."""
    blocks = [post_body(ann), credits_line(tags, episode_number, "threads"), page_url]
    return "\n\n".join(b for b in blocks if b)


def threads_topic(ann: dict) -> str:
    return (ann.get("theme_hashtag") or DEVSECOPS_HASHTAG).lstrip("#")


def render_posts(ann: dict, tags: dict, episode_number: int, page_url: str) -> dict[str, dict]:
    """{service: {"text", "thread"}}: exactly what Buffer gets, saved at approval."""
    x_main, x_reply = render_x_posts(ann, tags, episode_number, page_url)
    return {
        "linkedin": {"text": render_linkedin_post(ann, tags, episode_number, page_url), "thread": []},
        "twitter": {"text": x_main, "thread": [x_reply]},
        "threads": {"text": render_threads_post(ann, tags, episode_number, page_url), "thread": []},
    }


def x_post_length(text: str) -> int:
    return len(_URL_RE.sub("x" * X_URL_WEIGHT, text))


def first_person_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z']+", text.replace("’", "'")) if w in _FIRST_PERSON]


def check_announcement(raw, inputs: dict, tags: dict, episode_number: int, page_url: str) -> tuple[dict | None, list[str]]:
    """(cleaned announcement, rule violations); each violation goes back to one retry.

    The quoted person is taken from the transcript, never from the model.
    """
    if not isinstance(raw, dict):
        return None, ["answer is not a JSON object"]
    ann = clean_announcement(raw)
    fmt, context = ann["format"], ann["context"]
    if fmt not in FORMATS:
        return ann, [f"format must be one of {', '.join(FORMATS)}"]
    errors: list[str] = []
    if not context:
        errors.append("context is empty")
    if fmt == "quote":
        words = len(quote_words(ann["quote"]).split())
        if not QUOTE_WORDS[0] <= words <= QUOTE_WORDS[1]:
            errors.append(f"quote is {words} words (must be {QUOTE_WORDS[0]}-{QUOTE_WORDS[1]})")
        speaker, problems = quote_check(ann["quote"], inputs["turns"], inputs["guest_context"])
        ann["source_person"] = speaker
        errors += problems
    elif any(c in context for c in _QUOTE_CHARS):
        errors.append(f"{fmt} posts carry no quotation marks")
    if not inputs["andrey_present"] and first_person_words(context):
        errors.append(
            "Andrey was not on this episode: no first person ("
            + ", ".join(sorted(set(first_person_words(context)))) + ")"
        )
    if _URL_RE.search(context) or "@" in context or "#" in context:
        errors.append("context must carry no URL, @-mention or hashtag")
    if "—" in post_body(ann):
        errors.append("em dash in the copy; short dashes only")
    theme = ann.get("theme_hashtag") or ""
    if theme and not _HASHTAG_RE.match(theme):
        errors.append(f"theme_hashtag {theme!r} is not a single #Tag")
    posts = render_posts(ann, tags, episode_number, page_url)
    for label, text in (("X post", posts["twitter"]["text"]), ("X reply", posts["twitter"]["thread"][0])):
        if x_post_length(text) > X_POST_LIMIT:
            errors.append(f"the {label} is {x_post_length(text)} chars (limit {X_POST_LIMIT})")
    if len(posts["threads"]["text"]) > THREADS_POST_LIMIT:
        errors.append(f"the Threads post is {len(posts['threads']['text'])} chars (limit {THREADS_POST_LIMIT})")
    return ann, errors


def announcement_warnings(tags: dict) -> list[str]:
    warnings: list[str] = []
    guest_names = set(guest_full_names(tags["guest_context"]))
    company = company_entity(tags.get("handles") or {})
    entities = ([company] if company else []) + credited_people(tags)
    for e in entities:
        if e["name"] in guest_names and not e["linkedin_name"]:
            warnings.append(f"not tagged on LinkedIn: {e['name']} (profile not confirmed)")
    untagged_li = [e["name"] for e in entities
                   if not e["linkedin_name"] and not e.get("linkedin_credit") and e["name"] not in guest_names]
    if untagged_li:
        warnings.append(f"credited on LinkedIn in plain text (no linkedin_name): {', '.join(untagged_li)}")
    for key, network in (("x_handle", "X"), ("threads_handle", "Threads")):
        untagged = [e["name"] for e in entities if not e[key]]
        if untagged:
            warnings.append(f"credited on {network} in plain text (no {key}): {', '.join(untagged)}")
    return warnings


# --- generation -------------------------------------------------------------


def voice_directive(inputs: dict) -> str:
    if inputs["andrey_present"]:
        return "Andrey was on this episode: write in first person, in his own voice."
    others = [h.split()[0] for h in inputs["hosts_present"]] + inputs["guests"]
    return (
        "Andrey was NOT on this episode: third person only, no I, we, our or us. "
        f"He presents the conversation with {_name_list(others) if others else 'the people on it'}."
    )


def quote_directive(inputs: dict) -> str:
    if inputs["guests"]:
        return f"Quote a guest ({_name_list(inputs['guests'])}), never a host."
    return "There is no guest: quote a host."


def generation_source(title: str, article: str, inputs: dict) -> str:
    return (
        f"--- EPISODE TITLE ---\n{title}\n\n"
        f"--- ON THIS EPISODE ---\n{person_line(inputs['hosts_present'], inputs['guests'])}\n"
        f"{voice_directive(inputs)}\n{quote_directive(inputs)}\n\n"
        f"--- ARTICLE ---\n{article}\n\n--- TRANSCRIPT ---\n{inputs['turns_text']}\n"
    )


def rejected_rounds_prompt(rounds: list[dict]) -> str:
    """Earlier rounds and the guidance each drew, so a regeneration moves on instead of looping."""
    if not rounds:
        return ""
    lines = ["\n## Drafts the operator already rejected\n",
             "Do not reuse their angle, hook or quote. Every guidance line below still applies; "
             "when two conflict, the later one wins.\n"]
    for i, item in enumerate(rounds, 1):
        for post in item.get("posts") or []:
            lines.append(f"\n### Rejected in round {i}\n\n{post}\n")
        if item.get("guidance"):
            lines.append(f"\nOperator guidance after round {i}: {item['guidance']}\n")
    return "".join(lines)


def load_rejected(path: str, fingerprint: str) -> list[dict]:
    """Rejected rounds from earlier runs built from the same inputs; torn lines are skipped."""
    rows = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("fingerprint") == fingerprint]


def append_rejected(path: str, fingerprint: str, candidates: list[dict], guidance: str) -> dict:
    item = {"fingerprint": fingerprint, "posts": [post_body(c["announcement"]) for c in candidates],
            "guidance": guidance}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def _schema_text() -> str:
    with open(ANNOUNCEMENT_SCHEMA, "r", encoding="utf-8") as f:
        return f.read()


def draft_with_codex(prompt: str, source: str, verbose: bool = False) -> dict:
    """Codex, schema-enforced by --output-schema; raises on failure instead of exiting."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        out_path = tmp.name
    try:
        cmd = ["codex", "exec", "--sandbox", "read-only", "-C", REPO_ROOT, "--model", CODEX_MODEL,
               "-o", out_path, "--output-schema", ANNOUNCEMENT_SCHEMA, prompt]
        try:
            result = subprocess.run(cmd, input=source, stdout=subprocess.PIPE,
                                    stderr=None if verbose else subprocess.PIPE, text=True, timeout=CODEX_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"timed out after {CODEX_TIMEOUT_S}s (raise CODEX_TIMEOUT_S)") from None
        if result.returncode != 0:
            raise RuntimeError(f"exit {result.returncode}: {(result.stderr or '')[:1000]}")
        with open(out_path, "r", encoding="utf-8") as f:
            return _extract_json_object(f.read())
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def draft_with_claude(prompt: str, source: str, verbose: bool = False) -> dict:
    """Claude Code; the schema-checked answer is the envelope's ``structured_output``."""
    cmd = ["claude", "--print", "--model", CLAUDE_MODEL,
           "--disallowedTools", "Write", "Edit", "NotebookEdit", "Bash",
           "--json-schema", _schema_text(), "--output-format", "json",
           "-p", "Process the input provided on stdin."]
    try:
        result = subprocess.run(cmd, input=f"{prompt}\n\n{source}", stdout=subprocess.PIPE, stderr=None,
                                text=True, timeout=CLAUDE_TIMEOUT_S, cwd=REPO_ROOT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"timed out after {CLAUDE_TIMEOUT_S}s (raise CLAUDE_TIMEOUT_S)") from None
    if result.returncode != 0:
        raise RuntimeError(f"exit {result.returncode}: {(result.stdout or '')[:1000]}")
    envelope = _extract_json_object(result.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"Claude reported an error: {str(envelope.get('result'))[:500]}")
    if isinstance(envelope.get("structured_output"), dict):
        return envelope["structured_output"]
    return _extract_json_object(str(envelope.get("result") or ""))


def draft_with_grok(prompt: str, source: str, verbose: bool = False) -> dict:
    """Grok Build CLI with its agent prompt replaced and a scratch cwd.

    With its own system prompt and repo access it drifts into tool use and runs
    out of turns; everything it needs is in the prompt file.
    """
    with tempfile.TemporaryDirectory() as scratch:
        prompt_file = os.path.join(scratch, "prompt.md")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(f"{prompt}\n\n{source}")
        cmd = ["grok", "--prompt-file", prompt_file, "--json-schema", _schema_text(),
               "--disable-web-search", "--no-subagents", "--max-turns", "10",
               "--system-prompt-override", "You write social media copy. Output only the requested JSON.",
               "--cwd", scratch]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=None if verbose else subprocess.PIPE,
                                    text=True, timeout=GROK_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"timed out after {GROK_TIMEOUT_S}s (raise GROK_TIMEOUT_S)") from None
    if result.returncode != 0:
        raise RuntimeError(f"exit {result.returncode}: {(result.stdout or result.stderr or '')[:1000]}")
    envelope = _extract_json_object(result.stdout)
    if isinstance(envelope.get("structuredOutput"), dict):
        return envelope["structuredOutput"]
    return _extract_json_object(str(envelope.get("text") or ""))


# Order is the order the operator sees them, as [1], [2], [3].
DRAFTERS = (("Codex", draft_with_codex), ("Claude", draft_with_claude), ("Grok", draft_with_grok))


def drafting_prompt(inputs: dict, rejected: list[dict], guidance: str = "") -> str:
    prompt = load_prompt("announcement")
    prompt += f"\n\n## This episode\n\n{voice_directive(inputs)}\n{quote_directive(inputs)}\n"
    prompt += rejected_rounds_prompt(rejected)
    if guidance:
        prompt += f"\nGuidance from the operator: {guidance}\n"
    return prompt


def _draft_checked(name, fn, prompt, source, check, verbose=False) -> dict | None:
    """One drafter's candidate, sent back once with its violations; None if still broken."""
    attempt_prompt = prompt
    for attempt in (1, 2):
        raw = fn(attempt_prompt, source, verbose)
        ann, errors = check(raw)
        if not errors:
            return ann
        if attempt == 1:
            print(f"↻ {name}: breaks rules ({'; '.join(errors)}); asking once more")
            attempt_prompt = (f"{prompt}\n\nYour previous answer was:\n{json.dumps(raw, ensure_ascii=False)}\n"
                              f"It was rejected: {'; '.join(errors)}. Fix these.\n")
    print(f"⚠ {name}: still breaks rules after one retry ({'; '.join(errors)}); dropped")
    return None


def draft_candidates(prompt: str, source: str, check, drafters=DRAFTERS, verbose: bool = False) -> list[dict]:
    """Every drafter in parallel, each under its own timeout; [{"drafter", "announcement"}].

    A drafter that crashes or times out is reported and left out. All of them
    failing stops the run: that is a broken install or login, not bad copy.
    """
    print("Drafting the announcement with " + ", ".join(name for name, _ in drafters) + "...")
    with ThreadPoolExecutor(max_workers=len(drafters)) as pool:
        futures = [(name, pool.submit(_draft_checked, name, fn, prompt, source, check, verbose))
                   for name, fn in drafters]
    candidates, failures = [], []
    for name, future in futures:
        try:
            ann = future.result()
        except Exception as e:  # noqa: BLE001 - collected, raised below when nothing ran
            failures.append(f"{name}: {type(e).__name__}: {e}")
            print(f"⚠ {name}: drafting failed ({type(e).__name__}: {e})")
            continue
        if ann:
            candidates.append({"drafter": name, "announcement": ann})
    if len(failures) == len(drafters):
        raise AnnouncementStop("every announcement drafter failed:\n  " + "\n  ".join(failures))
    return candidates


# --- schedule, eligibility, ledger ------------------------------------------


def episode_page_url(page_path: str) -> str:
    """Canonical URL Hugo builds from the page's filename, which never changes after first publish."""
    return f"{SITE_URL}episodes/{Path(page_path).stem}/"


def record_announcement_eligibility(out_base: str, release_at: dt.datetime) -> None:
    """Mark the episode as announceable. Kept once written, so resumes keep the original release."""
    path = f"{out_base}{ELIGIBILITY_SUFFIX}"
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "release_at": release_at.astimezone(_UTC).isoformat(),
            "recorded_at": dt.datetime.now(_UTC).replace(microsecond=0).isoformat(),
        }, f, indent=2)
        f.write("\n")


def load_announcement_eligibility(out_base: str) -> dt.datetime | None:
    try:
        with open(f"{out_base}{ELIGIBILITY_SUFFIX}", "r", encoding="utf-8") as f:
            return dt.datetime.fromisoformat(json.load(f)["release_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def announcement_target_date(release_at: dt.datetime, lead_days: int = ANNOUNCEMENT_LEAD_DAYS) -> dt.date:
    return release_at.astimezone(_UTC).date() + dt.timedelta(days=lead_days)


def announcement_due_at(channel: dict, target: dt.date, now: dt.datetime | None = None) -> dt.datetime | None:
    """First slot of the channel's own Buffer posting schedule on or after ``target``, in UTC.

    Searches from today when the target is already past, so a late retry still
    finds a slot instead of only stale ones.
    """
    slots = {
        str(entry.get("day") or "").lower(): [str(t) for t in entry.get("times") or []]
        for entry in channel.get("postingSchedule") or []
    }
    if not any(slots.values()):
        return None
    try:
        tz = ZoneInfo(channel.get("timezone") or "UTC")
    except Exception:
        tz = _UTC
    now = now or dt.datetime.now(_UTC)
    start = max(target, now.astimezone(tz).date())
    for offset in range(14):
        day = start + dt.timedelta(days=offset)
        for raw in sorted(slots.get(_WEEKDAY_KEYS[day.weekday()], [])):
            try:
                hour, minute = (int(part) for part in raw.split(":")[:2])
            except ValueError:
                continue
            due = dt.datetime.combine(day, dt.time(hour, minute), tzinfo=tz).astimezone(_UTC)
            if due > now:
                return due
    return None


def load_ledger(path: str) -> dict[str, dict]:
    """Posts already created in Buffer, by channel id: one JSON object per line, never rewritten."""
    done: dict[str, dict] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict) and entry.get("channel_id") and entry.get("post_id"):
                    done[entry["channel_id"]] = entry
    except OSError:
        pass
    return done


def append_ledger(path: str, entry: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def configured_channels(handles: dict) -> list[dict]:
    return [c for c in (handles or {}).get("buffer_channels") or [] if isinstance(c, dict)]


def announcement_fingerprint(title: str, article: str, turns, page_url: str, target: dt.date,
                             cover_url: str, tags: dict) -> str:
    """What a saved approval or a rejected round was built from."""
    handles = {k: v for k, v in (tags.get("handles") or {}).items() if k != "_about"}
    payload = {
        "title": title,
        "article_sha256": hashlib.sha256(article.encode("utf-8")).hexdigest(),
        "turns_sha256": hashlib.sha256(json.dumps(turns, sort_keys=True).encode("utf-8")).hexdigest(),
        "page_url": page_url,
        "target_date": target.isoformat(),
        "cover_url": cover_url,
        "hosts_present": list(tags["hosts_present"]),
        "guests": tags["guest_context"].get("guests") or [],
        "handles": handles,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# --- Buffer API -------------------------------------------------------------
# GraphQL only: the legacy REST API rejects these tokens. Text goes in variables,
# never interpolated, because generated prose can break a query string.


def buffer_graphql(query: str, api_key: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    resp = requests.post(
        BUFFER_API_URL,
        json=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_buffer_channels(api_key: str) -> dict[str, dict]:
    """Every channel in every organization, by id (only top-level channels() is permitted)."""
    data = buffer_graphql("query { account { organizations { id } } }", api_key)
    orgs = ((data.get("data") or {}).get("account") or {}).get("organizations") or []
    channels: dict[str, dict] = {}
    for org in orgs:
        result = buffer_graphql(CHANNELS_QUERY, api_key, {"input": {"organizationId": org["id"]}})
        if result.get("errors"):
            raise RuntimeError(f"channel lookup failed: {json.dumps(result['errors'])[:300]}")
        for channel in (result.get("data") or {}).get("channels") or []:
            channels[channel["id"]] = channel
    return channels


def resolve_channels(configured: list[dict], fetched: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """One usable Buffer channel per required service, in REQUIRED_SERVICES order, or errors."""
    channels, errors = [], []
    for service in REQUIRED_SERVICES:
        name = SERVICE_NAMES[service]
        conf = next((c for c in configured if c.get("service") == service), None)
        cid = (conf or {}).get("id")
        if not cid:
            found = [f"{c.get('displayName') or c.get('name')} ({c['id']})"
                     for c in fetched.values() if c.get("service") == service]
            hint = f"; Buffer has: {', '.join(found)}" if found else f"; connect {name} in Buffer first"
            errors.append(f"no {name} channel id in social-handles.json buffer_channels{hint}")
            continue
        channel = fetched.get(cid)
        label = f"{name} {conf.get('name') or ''} ({cid})".replace("  ", " ")
        if not channel:
            errors.append(f"{label} is not in this Buffer account")
        elif channel.get("isDisconnected") or channel.get("isLocked"):
            errors.append(f"{label} is disconnected or locked; reconnect it in Buffer")
        elif channel.get("service") != service:
            errors.append(f"{label} is a {channel.get('service')} channel in Buffer, expected {service}")
        else:
            channels.append(channel)
    return channels, errors


def preflight_buffer(api_key: str | None = None, handles: dict | None = None, target: dt.date | None = None,
                     now: dt.datetime | None = None) -> list[dict]:
    """The LinkedIn, X and Threads channels, or AnnouncementStop naming what is missing.

    Run before any upload; with ``target`` it also requires a posting slot on each.
    """
    api_key = api_key or os.environ.get("BUFFER_API_KEY")
    if not api_key:
        raise AnnouncementStop("BUFFER_API_KEY is not set (do.sh reads it from 1Password)")
    handles = load_social_handles() if handles is None else handles
    try:
        fetched = fetch_buffer_channels(api_key)
    except Exception as e:  # noqa: BLE001 - network/HTTP, turned into a stop
        raise AnnouncementStop(f"Buffer channel lookup failed ({type(e).__name__}: {e})") from e
    channels, errors = resolve_channels(configured_channels(handles), fetched)
    if target is not None:
        errors += [f"{SERVICE_NAMES[c['service']]}: no usable slot in its Buffer posting schedule"
                   for c in channels if not announcement_due_at(c, target, now=now)]
    if errors:
        raise AnnouncementStop("Buffer cannot take the announcement:\n  " + "\n  ".join(errors))
    return channels


def image_assets(cover_url: str, alt_text: str) -> list[dict]:
    """Buffer keeps the URL and fetches it again at publish, so the object must stay live and unchanged."""
    if not cover_url:
        return []
    image = {"url": cover_url}
    if alt_text:
        image["metadata"] = {"altText": alt_text}
    return [{"image": image}]


def post_input(channel: dict, text: str, due_at: dt.datetime, thread: list[str] | None = None,
               assets: list[dict] | None = None, topic: str = "") -> dict:
    payload = {
        "channelId": channel["id"],
        "text": text,
        "assets": list(assets or []),
        "mode": "customScheduled",
        "schedulingType": "automatic",
        "dueAt": due_at.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if thread:
        payload["metadata"] = {"twitter": {"thread": [{"text": t, "assets": []} for t in thread]}}
    elif channel.get("service") == "threads":
        payload["metadata"] = {"threads": {"type": "post", **({"topic": topic} if topic else {})}}
    return payload


def create_buffer_post(api_key: str, payload: dict) -> tuple[str | None, str | None]:
    """(post_id, None) on success, (None, error) otherwise."""
    data = buffer_graphql(CREATE_POST_MUTATION, api_key, {"input": payload})
    if data.get("errors"):
        return None, json.dumps(data["errors"])[:400]
    result = (data.get("data") or {}).get("createPost") or {}
    if result.get("__typename") == "PostActionSuccess":
        return (result.get("post") or {}).get("id"), None
    return None, f"{result.get('__typename', 'UnknownError')}: {result.get('message') or json.dumps(data)[:400]}"


def _local(due: dt.datetime, channel: dict) -> str:
    tz = channel.get("timezone") or "UTC"
    try:
        local = due.astimezone(ZoneInfo(tz))
    except Exception:
        local = due
    return f"{local:%a %d %b %H:%M} {tz} ({due:%Y-%m-%d %H:%M} UTC)"


# --- preview and approval ---------------------------------------------------


def preview_posts(ann: dict, tags: dict, episode_number: int, page_url: str) -> None:
    posts = render_posts(ann, tags, episode_number, page_url)
    if ann["format"] == "quote":
        print(f"Quote by {ann['source_person']} (word for word in the corrected transcript)")
    body = posts["linkedin"]["text"]
    print(f"\n-- LinkedIn ({len(body)} chars) --\n{body}")
    for label, text in (("post", posts["twitter"]["text"]), ("reply", posts["twitter"]["thread"][0])):
        print(f"\n-- X {label} ({x_post_length(text)}/{X_POST_LIMIT}) --\n{text}")
    threads = posts["threads"]["text"]
    print(f"\n-- Threads ({len(threads)}/{THREADS_POST_LIMIT}, topic {threads_topic(ann)}) --\n{threads}")


def preview_context(tags, inputs, page_url, channels, done, release_at, target, cover_path, cover_url,
                    now=None) -> None:
    rule = "=" * 70
    print(f"\n{rule}\nANNOUNCEMENT  {page_url}\n{rule}")
    print(person_line(inputs["hosts_present"], inputs["guests"]))
    voice = "first person (Andrey present)" if inputs["andrey_present"] else "third person (Andrey absent)"
    print(f"Voice: {voice}")
    print(f"Cover: {cover_path} -> {cover_url} (attached to every post)")
    print(f"Tagged on LinkedIn: {', '.join(tag_set(tags, 'linkedin')) or 'nobody'}")
    company = company_entity(tags.get("handles") or {})
    if company and company["linkedin_credit"]:
        print(f"Linked on LinkedIn: {company['linkedin_credit']}")
    print(f"Tagged on X:        {', '.join(tag_set(tags, 'x')) or 'nobody'}")
    print(f"Tagged on Threads:  {', '.join(tag_set(tags, 'threads')) or 'nobody'}")

    print(f"\n-- Schedule (release {release_at.astimezone(_UTC):%a %d %b %H:%M} UTC + "
          f"{ANNOUNCEMENT_LEAD_DAYS} days: earliest {target:%a %d %b %Y}) --")
    earliest = None
    for channel in channels:
        if channel["id"] in done:
            entry = done[channel["id"]]
            print(f"  {channel['service']}: already scheduled ({entry.get('post_id')}, due {entry.get('due_at')})")
            continue
        due = announcement_due_at(channel, target, now=now)
        if due:
            earliest = min(earliest or due, due)
            print(f"  {channel['service']} {channel.get('displayName') or channel.get('name')}: {_local(due, channel)}")
    if earliest:
        print(f"⚠ The posts link {page_url}: push and deploy the page before {earliest:%a %d %b %H:%M} UTC.")
    warnings = announcement_warnings(tags)
    if warnings:
        print(f"\n⚠ {len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")


def open_image(path: str, opener=subprocess.run) -> None:
    """Open the cover in the default viewer; the prompt after it runs either way."""
    try:
        opened = opener(["open", path], check=False).returncode == 0
    except OSError:
        opened = False
    if not opened:
        print(f"Could not open the image; open it yourself: {path}")


def answer(input_func, where: str, lower: bool = True) -> str:
    """The operator's answer. EOF stops: an unattended run must not approve or skip by default."""
    try:
        text = input_func().strip()
        return text.lower() if lower else text
    except EOFError:
        raise AnnouncementStop(f"no answer at {where}; run ./do.sh from a terminal") from None


def pick_candidate(candidates: list[dict], input_func) -> tuple[str, dict | None]:
    """("pick", candidate) | ("skip", None) | ("regenerate", None); a typo asks again."""
    numbers = "/".join(str(i) for i in range(1, len(candidates) + 1))
    options = f"{numbers} to pick that candidate, 'r' to regenerate" if candidates else "'r' to regenerate"
    if not candidates:
        print("\n⚠ No candidate passed the checks.")
    while True:
        print(f"\n{options} with guidance, or 's' to skip Buffer for this episode: ", end="", flush=True)
        choice = answer(input_func, "the announcement pick")
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return "pick", candidates[int(choice) - 1]
        if choice == "s":
            return "skip", None
        if choice == "r":
            return "regenerate", None
        print("Invalid choice, try again.")


def read_saved(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except OSError:
        return None
    except ValueError as e:
        print(f"⚠ Could not read {path} ({e}); asking again")
        return None
    return saved if isinstance(saved, dict) else None


def write_saved(path: str, record: dict) -> dict:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return record


def approve_episode_announcement(
    out_base: str,
    episode_number: int,
    page_url: str,
    title: str,
    article: str,
    turns: list[dict] | None,
    guest_context: dict,
    release_at: dt.datetime | None,
    cover_path: str,
    cover_url: str,
    input_func=input,
    api_key: str | None = None,
    handles: dict | None = None,
    now: dt.datetime | None = None,
    verbose: bool = False,
    opener=subprocess.run,
    drafters=DRAFTERS,
) -> dict | None:
    """Draft, preview and pick the announcement before any upload; returns the saved approval.

    ``turns`` are the corrected, speaker-named turns; ``guest_context`` carries
    hosts_present from voice match. ``release_at`` is the release chosen for
    Podbean; an existing eligibility record wins over it. None for both means
    the episode is not released by this pipeline, so there is no announcement.
    ``cover_url`` is where the cover will be once uploaded; it is attached to
    every post and part of what the approval covers.
    """
    release_at = load_announcement_eligibility(out_base) or release_at
    if release_at is None:
        print(f"\nNo {os.path.basename(out_base)}{ELIGIBILITY_SUFFIX} and no new release; "
              "this episode gets no Buffer announcement.")
        return None
    handles = load_social_handles() if handles is None else handles
    target = announcement_target_date(release_at)
    channels = preflight_buffer(api_key, handles, target=target, now=now)
    done = load_ledger(f"{out_base}{LEDGER_SUFFIX}")
    saved_path = f"{out_base}{SAVED_SUFFIX}"
    if all(c["id"] in done for c in channels):
        print(f"\n✓ Announcement already scheduled on every channel ({os.path.basename(out_base)}{LEDGER_SUFFIX}).")
        return read_saved(saved_path)

    inputs = build_announcement_inputs(turns, guest_context)
    if not inputs["turns"]:
        raise AnnouncementStop("no corrected transcript turns to quote from")
    tags = tagging_context(guest_context, handles)
    fingerprint = announcement_fingerprint(title, article, inputs["turns"], page_url, target, cover_url, tags)
    alt_text = f"Cover of DevSecOps Talks episode {episode_number}: {title}"

    def check(raw):
        return check_announcement(raw, inputs, tags, episode_number, page_url)

    def approved(ann: dict, drafter: str) -> dict:
        return write_saved(saved_path, {
            "schema": SAVED_SCHEMA,
            "fingerprint": fingerprint,
            "drafter": drafter,
            "announcement": ann,
            "posts": render_posts(ann, tags, episode_number, page_url),
            "page_url": page_url,
            "target_date": target.isoformat(),
            "cover_url": cover_url,
            "cover_alt": alt_text,
            "approved_at": dt.datetime.now(_UTC).replace(microsecond=0).isoformat(),
        })

    saved = read_saved(saved_path)
    if saved and saved.get("fingerprint") == fingerprint and saved.get("skipped"):
        print(f"✓ Buffer announcement skipped at an earlier pick; delete {saved_path} to pick again.")
        return None
    if saved and saved.get("schema") == SAVED_SCHEMA and saved.get("fingerprint") == fingerprint:
        ann, errors = check(saved.get("announcement"))
        if not errors:
            print(f"\nFound the approved announcement ({saved.get('drafter')}):")
            preview_posts(ann, tags, episode_number, page_url)
            preview_context(tags, inputs, page_url, channels, done, release_at, target, cover_path, cover_url, now)
            open_image(cover_path, opener)
            while True:
                print("\nPress Enter to reuse it, 'new' to draft again, or 's' to skip Buffer: ", end="", flush=True)
                choice = answer(input_func, "the saved announcement")
                if choice in ("", "new", "s"):
                    break
                print("Invalid choice, try again.")
            if choice == "":
                return saved
            if choice == "s":
                write_saved(saved_path, {"schema": SAVED_SCHEMA, "fingerprint": fingerprint, "skipped": True})
                print("Skipped the Buffer announcement.")
                return None
        else:
            print(f"Saved announcement breaks rules ({'; '.join(errors)}); drafting again.")
    elif saved and not saved.get("skipped"):
        print("Saved announcement is in an older format or was built from other inputs; drafting again.")

    rejected_path = f"{out_base}{REJECTED_SUFFIX}"
    rejected = load_rejected(rejected_path, fingerprint)
    if rejected:
        print(f"✓ {len(rejected)} rejected round(s) from earlier runs go to the drafters")
    source = generation_source(title, article, inputs)
    while True:
        candidates = draft_candidates(drafting_prompt(inputs, rejected), source, check, drafters, verbose)
        for i, candidate in enumerate(candidates, 1):
            print(f"\n{'#' * 70}\n[{i}] {candidate['drafter']}\n{'#' * 70}")
            preview_posts(candidate["announcement"], tags, episode_number, page_url)
        preview_context(tags, inputs, page_url, channels, done, release_at, target, cover_path, cover_url, now)
        open_image(cover_path, opener)
        action, picked = pick_candidate(candidates, input_func)
        if action == "pick":
            record = approved(picked["announcement"], picked["drafter"])
            print(f"✓ Announcement approved and saved to {saved_path}")
            return record
        if action == "skip":
            write_saved(saved_path, {"schema": SAVED_SCHEMA, "fingerprint": fingerprint, "skipped": True})
            print("Skipped the Buffer announcement.")
            return None
        print("Guidance (e.g. 'use the guest's line about SHA pinning'): ", end="", flush=True)
        rejected.append(append_rejected(rejected_path, fingerprint, candidates,
                                        answer(input_func, "the guidance", lower=False)))


# --- scheduling -------------------------------------------------------------


def render_announcement_markdown(record: dict, episode_number: int, ledger: dict[str, dict],
                                 failures: list[dict]) -> str:
    ann = record["announcement"]
    posts = record["posts"]
    lines = [f"# Episode {episode_number} announcement", "", f"Page: {record['page_url']}",
             f"Cover: {record.get('cover_url')}", f"Drafted by: {record.get('drafter')}", ""]
    if ann["format"] == "quote":
        lines += [f"Quote by {ann['source_person']}, word for word in the corrected transcript", ""]
    else:
        lines += [f"Format: {ann['format']}", ""]
    lines += ["## LinkedIn", "", posts["linkedin"]["text"], "",
              "## X", "", posts["twitter"]["text"], "", "Reply:", "", posts["twitter"]["thread"][0], "",
              "## Threads", "", posts["threads"]["text"], "", "## Scheduled", ""]
    for entry in ledger.values():
        lines.append(f"- {entry.get('service')}: {entry.get('due_at')} ({entry.get('post_id')})")
    for entry in failures:
        lines.append(f"- {entry.get('service')}: FAILED {entry.get('error')}")
    return "\n".join(lines).rstrip() + "\n"


def approval_mismatch(record: dict, posts: dict, page_url: str, cover_url: str, target: dt.date) -> list[str]:
    """How what would be posted now differs from what the operator approved."""
    problems = []
    if record.get("page_url") != page_url:
        problems.append(f"page URL is {page_url}, approved {record.get('page_url')}")
    if record.get("cover_url") != cover_url:
        problems.append(f"cover URL is {cover_url}, approved {record.get('cover_url')}")
    if record.get("target_date") != target.isoformat():
        problems.append(f"target date is {target.isoformat()}, approved {record.get('target_date')}")
    for service, post in posts.items():
        if (record.get("posts") or {}).get(service) != post:
            problems.append(f"the {SERVICE_NAMES[service]} post text changed")
    return problems


def schedule_episode_announcement(
    out_base: str,
    episode_number: int,
    page_path: str,
    guest_context: dict,
    cover_url: str,
    api_key: str | None = None,
    handles: dict | None = None,
    now: dt.datetime | None = None,
) -> None:
    """Post the approved announcement to every channel not yet in the ledger. Asks nothing.

    A channel with a ledger line is never posted again; delete its line to
    repost it. A saved approval that no longer matches what would be posted is
    set aside and raises, so the next run asks for approval again.
    """
    release_at = load_announcement_eligibility(out_base)
    if release_at is None:
        print(f"\nNo {os.path.basename(out_base)}{ELIGIBILITY_SUFFIX} (episode not released by this "
              "pipeline); no Buffer announcement.")
        return
    saved_path = f"{out_base}{SAVED_SUFFIX}"
    record = read_saved(saved_path)
    if not record or record.get("skipped"):
        print("\nSkipped the Buffer announcement, as picked.")
        return
    if record.get("schema") != SAVED_SCHEMA:
        raise AnnouncementStop(f"{saved_path} is in an older format; rerun to approve the announcement again")

    handles = load_social_handles() if handles is None else handles
    ledger_path = f"{out_base}{LEDGER_SUFFIX}"
    done = load_ledger(ledger_path)
    for conf in configured_channels(handles):
        entry = done.get(conf.get("id"))
        if entry and entry.get("fingerprint") != record["fingerprint"]:
            print(f"⚠ {SERVICE_NAMES.get(conf.get('service'), conf.get('service'))} already carries a post from "
                  f"other inputs ({entry.get('post_id')}); not reposting. Delete its line in "
                  f"{os.path.basename(ledger_path)} to post this approval there.")
    channels = preflight_buffer(api_key, handles)
    api_key = api_key or os.environ.get("BUFFER_API_KEY")
    remaining = [c for c in channels if c["id"] not in done]
    if not remaining:
        print(f"\n✓ Announcement already scheduled on every channel ({os.path.basename(ledger_path)}).")
        return

    page_url = episode_page_url(page_path)
    target = announcement_target_date(release_at)
    tags = tagging_context(guest_context, handles)
    posts = render_posts(record["announcement"], tags, episode_number, page_url)
    mismatch = approval_mismatch(record, posts, page_url, cover_url, target)
    if mismatch:
        os.replace(saved_path, f"{out_base}{STALE_SUFFIX}")
        raise AnnouncementStop(
            "the approved announcement no longer matches what would be posted ("
            + "; ".join(mismatch) + f"). Set aside as {os.path.basename(out_base)}{STALE_SUFFIX}; "
            "the next run asks for approval again."
        )

    print("\nScheduling on Buffer...")
    assets = image_assets(cover_url, record.get("cover_alt") or "")
    topic = threads_topic(record["announcement"])
    failures = []
    for channel in remaining:
        service = channel["service"]
        due = announcement_due_at(channel, target, now=now)
        if not due:
            failures.append({"service": service, "error": "no usable slot in its Buffer posting schedule"})
            continue
        post = record["posts"][service]
        try:
            post_id, error = create_buffer_post(
                api_key, post_input(channel, post["text"], due, post["thread"], assets, topic))
        except Exception as e:  # noqa: BLE001 - collected so later channels still get their attempt
            post_id, error = None, f"{type(e).__name__}: {e}"
        if not post_id:
            print(f"  ✗ {service}: {error}")
            failures.append({"service": service, "error": error})
            continue
        append_ledger(ledger_path, {
            "channel_id": channel["id"],
            "service": service,
            "post_id": post_id,
            "due_at": due.isoformat(),
            "scheduled_at": dt.datetime.now(_UTC).replace(microsecond=0).isoformat(),
            "fingerprint": record["fingerprint"],
            "text": post["text"],
            "thread": post["thread"],
        })
        print(f"  ✓ {service}: {_local(due, channel)} ({post_id})")

    record_path = f"{out_base}{RECORD_SUFFIX}"
    with open(record_path, "w", encoding="utf-8") as f:
        f.write(render_announcement_markdown(record, episode_number, load_ledger(ledger_path), failures))
    print(f"✓ Announcement recorded in {record_path}")
    if failures:
        raise AnnouncementStop(
            "Buffer failed on " + "; ".join(f"{f['service']}: {f['error']}" for f in failures)
            + f". The rest are in {os.path.basename(ledger_path)}; a rerun posts only the failed ones."
        )
