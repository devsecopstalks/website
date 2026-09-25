"""
Episode announcement on Andrey's personal LinkedIn and X, scheduled through
Buffer's GraphQL API. One moment from the episode: a quote verified against the
timestamped turns, a named disagreement, or (no turns) a paraphrased claim.
The operator approves the real posts before anything is scheduled; failures are
reported, never raised into the publishing run.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from episode_metadata import DEVSECOPS_HASHTAG, SITE_URL, format_timestamp, format_turn_line, parse_timestamp
from episode_pipeline import (
    AUTHOR_HOST,
    CONTEXT_FILE,
    PROMPTS_DIR,
    SHOW_HOSTS,
    guest_full_names,
    load_prompt,
    run_codex,
    save_guest_context,
)

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
SOCIAL_HANDLES_FILE = os.path.join(TOOLS_DIR, "social-handles.json")
ANNOUNCEMENT_SCHEMA = os.path.join(PROMPTS_DIR, "announcement-schema.json")

BUFFER_API_URL = "https://api.buffer.com"
# Earliest announcement date after release: Wednesday for the Monday Podbean slot.
ANNOUNCEMENT_LEAD_DAYS = 2

FORMATS = ("quote", "disagreement", "no_quote")
QUOTE_WORDS = (8, 30)
# A quote's MM:SS may name any moment inside its turn, give or take this much.
TS_TOLERANCE_S = 5
X_POST_LIMIT = 280
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
RECORD_SUFFIX = "-announcement.md"

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


# --- quote evidence ---------------------------------------------------------


def load_spelling_fixes(path: str = CONTEXT_FILE) -> list[tuple[str, str]]:
    """(wrong, right) pairs from the "Transcript spelling fixes" list, longest first."""
    fixes: list[tuple[str, str]] = []
    in_section = False
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    for line in lines:
        if line.startswith("## "):
            in_section = line.strip().lower() == "## transcript spelling fixes"
            continue
        match = re.match(r"^-\s+(.+?)\s+->\s+\*\*(.+?)\*\*\s*$", line) if in_section else None
        if match:
            fixes.extend((wrong.strip(), match.group(2).strip()) for wrong in match.group(1).split(","))
    return sorted(fixes, key=lambda pair: -len(pair[0]))


def apply_spelling_fixes(text: str, fixes: list[tuple[str, str]]) -> str:
    for wrong, right in fixes:
        text = re.sub(rf"(?<!\w){re.escape(wrong)}(?!\w)", right, text, flags=re.IGNORECASE)
    return text


def normalize_for_match(text: str, fixes: list[tuple[str, str]]) -> str:
    """Case, punctuation and whitespace folded, names corrected: what "verbatim" compares."""
    text = apply_spelling_fixes(str(text or ""), fixes).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def _word_diff(quote_words: list[str], turn_words: list[str]) -> str:
    """Git-style word diff of the quote against the closest window of the turn."""
    blocks = [b for b in difflib.SequenceMatcher(None, quote_words, turn_words, autojunk=False).get_matching_blocks() if b.size]
    if not blocks:
        return "(no words in common with the turn)"
    lo = max(blocks[0].b - blocks[0].a, 0)
    hi = min(blocks[-1].b + blocks[-1].size + len(quote_words) - blocks[-1].a - blocks[-1].size, len(turn_words))
    window = turn_words[lo:hi]
    out: list[str] = []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, quote_words, window, autojunk=False).get_opcodes():
        if op == "equal":
            out.extend(quote_words[a1:a2])
            continue
        if a2 > a1:
            out.append("[-" + " ".join(quote_words[a1:a2]) + "-]")
        if b2 > b1:
            out.append("{+" + " ".join(window[b1:b2]) + "+}")
    return " ".join(out)


def verify_quote_against_turns(quote: str, turns: list[dict], speaker: str, ts: str, fixes=None) -> dict:
    """Whether ``quote`` is a contiguous span of ``speaker``'s turn at ``ts``.

    Returns {"verified", "reason", "diff", "turn"}; the diff is against the
    closest turn so the operator can see what the model changed.
    """
    fixes = load_spelling_fixes() if fixes is None else fixes
    turns = [t for t in turns or [] if isinstance(t, dict)]
    wanted = normalize_for_match(quote, fixes)
    label = str(speaker or "").strip().strip("[]")
    seconds = parse_timestamp(ts)
    if not wanted:
        return {"verified": False, "reason": "empty quote", "diff": "", "turn": None}

    def text_of(turn):
        return normalize_for_match(turn.get("text"), fixes)

    def contains(turn):
        return f" {wanted} " in f" {text_of(turn)} "

    at_ts = [
        t for t in turns
        if str(t.get("speaker")) == label and seconds is not None
        and float(t.get("start") or 0) - TS_TOLERANCE_S <= seconds <= float(t.get("end") or t.get("start") or 0) + TS_TOLERANCE_S
    ]
    for turn in at_ts:
        if contains(turn):
            return {"verified": True, "reason": "", "diff": "", "turn": turn}

    elsewhere = next((t for t in turns if contains(t)), None)
    if elsewhere:
        where = f"[{elsewhere.get('speaker')}] {format_timestamp(float(elsewhere.get('start') or 0))}"
        return {"verified": False, "reason": f"quote is in {where}, not [{label}] {ts}", "diff": "", "turn": elsewhere}

    pool = at_ts or [t for t in turns if str(t.get("speaker")) == label] or turns
    words = wanted.split()

    def overlap(turn):
        sm = difflib.SequenceMatcher(None, words, text_of(turn).split(), autojunk=False)
        return sum(b.size for b in sm.get_matching_blocks())

    best = max(pool, key=overlap, default=None)
    reason = f"no turn [{label}] at {ts}" if not at_ts else f"not verbatim in [{label}] {ts}"
    diff = _word_diff(words, text_of(best).split()) if best else ""
    return {"verified": False, "reason": reason, "diff": diff, "turn": best}


def build_announcement_inputs(turns: list[dict] | None, guest_context: dict | None) -> dict:
    """What generation sees: timestamped turns (or none) and who was on the episode."""
    guest_context = guest_context or {}
    hosts = [h for h in guest_context.get("hosts_present") or [] if h]
    guests = guest_full_names(guest_context)
    usable = [t for t in turns or [] if isinstance(t, dict) and str(t.get("text") or "").strip()]
    lines = [format_turn_line(t) for t in usable]
    return {
        "has_turns": bool(usable),
        "turns": usable,
        "turns_text": "\n".join(lines),
        "speakers": sorted({str(t.get("speaker")) for t in usable}),
        "hosts_present": hosts,
        "andrey_present": AUTHOR_HOST in hosts,
        "guests": guests,
        "people": hosts + guests,
    }


# --- people and tags --------------------------------------------------------


def load_social_handles(path: str | None = None) -> dict:
    """Hosts, company, filename aliases and Buffer channels; {} disables Buffer, not the run."""
    path = path or SOCIAL_HANDLES_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"⚠ Could not read {path} ({e}); no Buffer channels or tags")
        return {}


def person_line(hosts_present, guests) -> str:
    names = list(hosts_present or []) + [f"{g} (guest)" for g in guests or []]
    presence = "present" if AUTHOR_HOST in (hosts_present or []) else "absent"
    return f"On this episode: {', '.join(names) or 'no hosts confirmed'} (Andrey {presence})"


def _alias_table(handles: dict) -> dict[str, str]:
    table = {host.casefold(): host for host in SHOW_HOSTS}
    table.update({host.split()[0].casefold(): host for host in SHOW_HOSTS})
    for alias, host in ((handles or {}).get("filename_aliases") or {}).items():
        if host in SHOW_HOSTS:
            table[str(alias).casefold()] = host
    return table


def hosts_from_filename(audio_path: str, handles: dict) -> list[str]:
    """Hosts named in a Riverside export name ("... - paulina, matte, andrey +1_...")."""
    table = _alias_table(handles)
    tokens = set(re.findall(r"[a-z]+", Path(audio_path or "").stem.casefold()))
    found = {table[t] for t in tokens if t in table}
    return [host for host in SHOW_HOSTS if host in found]


def parse_hosts(answer: str, handles: dict) -> tuple[list[str], list[str]]:
    table = _alias_table(handles)
    found, unknown = set(), []
    for chunk in re.split(r"[,;]", answer):
        key = " ".join(chunk.split()).casefold()
        if not key:
            continue
        if key in table:
            found.add(table[key])
        else:
            unknown.append(chunk.strip())
    return [host for host in SHOW_HOSTS if host in found], unknown


def confirm_hosts_present(guest_context: dict, audio_path: str, handles: dict | None = None,
                          guests_file: str | None = None, input_func=input) -> dict:
    """Operator confirms which hosts were on the episode; persisted to ``-guests.json``.

    The Riverside filename wins over guest detection when it names anyone,
    because it lists who was in the recording rather than who was inferred.
    """
    handles = load_social_handles() if handles is None else handles
    guests = [str(g.get("full_name")) for g in guest_context.get("guests") or [] if isinstance(g, dict)]
    detected = [h for h in guest_context.get("hosts_present") or [] if h in SHOW_HOSTS]
    from_file = hosts_from_filename(audio_path, handles)
    proposed = from_file or detected

    print(f"\n{person_line(proposed, guests)}")
    print(f"  guest detection:    {', '.join(detected) or 'no hosts'}")
    print(f"  recording filename: {', '.join(from_file) or 'no host names'}")
    if from_file and detected and set(from_file) != set(detected):
        print("⚠ Guest detection and the filename disagree; the filename is proposed.")

    hosts = proposed
    while True:
        print("Press Enter to confirm, or type who was on it (e.g. 'paulina, matte, andrey'): ", end="", flush=True)
        answer = input_func().strip()
        if not answer:
            if hosts:
                break
            print("No hosts are known for this episode; type who was on it.")
            continue
        parsed, unknown = parse_hosts(answer, handles)
        if unknown or not parsed:
            print(f"Unknown host name(s): {', '.join(unknown) or answer}. Hosts: {', '.join(SHOW_HOSTS)}")
            continue
        hosts = parsed
        print(person_line(hosts, guests))
        break

    updated = dict(guest_context)
    updated["hosts_present"] = hosts
    updated["andrey_present"] = AUTHOR_HOST in hosts
    if guests_file:
        save_guest_context(guests_file, updated)
    return updated


def _entity(name, linkedin_name, url, x_handle, entity_type) -> dict:
    """One credited party; an empty handle credits it in plain text on that network."""
    return {
        "name": str(name).strip(),
        "linkedin_name": str(linkedin_name or "").strip(),
        "linkedin_url": str(url or "").strip(),
        "x_handle": str(x_handle or "").strip().lstrip("@"),
        "entity_type": entity_type,
    }


def tagging_context(guest_context: dict | None, handles: dict | None = None) -> dict:
    """Guest context, confirmed hosts and handles as one value, so every render credits the same people."""
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
            people.append(_entity(name, guest.get("linkedin_name") or name, guest.get("linkedin_url"),
                                  guest.get("x_handle"), "person"))
    by_name = {str(h.get("name") or ""): h for h in handles.get("hosts") or [] if isinstance(h, dict)}
    for name in tags["hosts_present"]:
        if name == author:
            continue
        host = by_name.get(name) or {}
        people.append(_entity(name, host.get("linkedin_name"), host.get("linkedin_url"), host.get("x_handle"), "person"))
    return people


def company_entity(handles: dict) -> dict | None:
    company = (handles or {}).get("company")
    if not isinstance(company, dict) or not company.get("name"):
        return None
    return _entity(company["name"], company.get("linkedin_name"), company.get("linkedin_url"),
                   company.get("x_handle"), "organization")


def _credit(entity: dict, channel: str) -> str:
    handle = entity["x_handle"] if channel == "x" else entity["linkedin_name"]
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


def clean_announcement(raw: dict, inputs: dict) -> dict:
    """Coerce model output to the rendered shape: no quote fields outside ``quote``."""
    ann = {key: raw.get(key) for key in (
        "format", "quote", "source_speaker", "source_timestamp", "source_person", "context", "theme_hashtag"
    )}
    for key, value in ann.items():
        ann[key] = " ".join(str(value or "").split())
    ann["quote"] = ann["quote"].strip(_QUOTE_CHARS + " ")
    ann["source_speaker"] = ann["source_speaker"].strip("[]")
    ann["speaker_map"] = [
        {"label": str(m.get("label") or "").strip("[] "), "person": str(m.get("person") or "").strip()}
        for m in raw.get("speaker_map") or [] if isinstance(m, dict)
    ]
    if not inputs["has_turns"] and ann["format"] == "quote":
        ann["format"] = "no_quote"
    if ann["format"] != "quote":
        for key in ("quote", "source_speaker", "source_timestamp", "source_person"):
            ann[key] = ""
    if ann["theme_hashtag"].casefold() == DEVSECOPS_HASHTAG.casefold():
        ann["theme_hashtag"] = ""
    return ann


def hashtags(ann: dict) -> list[str]:
    theme = ann.get("theme_hashtag") or ""
    return [DEVSECOPS_HASHTAG] + ([theme] if _HASHTAG_RE.match(theme) else [])


def post_body(ann: dict, fixes=None) -> str:
    """Quote-led when there is a quote; otherwise the context carries the post."""
    if ann.get("format") == "quote" and ann.get("quote"):
        fixes = load_spelling_fixes() if fixes is None else fixes
        quote = apply_spelling_fixes(ann["quote"], fixes)
        return f"\"{quote[:1].upper()}{quote[1:]}\" - {ann['source_person']}\n\n{ann['context']}"
    return ann.get("context") or ""


def render_linkedin_post(ann: dict, tags: dict, episode_number: int, page_url: str) -> str:
    blocks = [post_body(ann), credits_line(tags, episode_number, "linkedin"), page_url, " ".join(hashtags(ann))]
    return "\n\n".join(b for b in blocks if b)


def render_x_posts(ann: dict, tags: dict, episode_number: int, page_url: str) -> list[str]:
    """One post, then one reply carrying the credits and the link."""
    reply = f"{credits_line(tags, episode_number, 'x')}\n\n{page_url}\n\n{' '.join(hashtags(ann))}"
    return [post_body(ann), reply]


def x_post_length(text: str) -> int:
    return len(_URL_RE.sub("x" * X_URL_WEIGHT, text))


def first_person_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z']+", text.replace("’", "'")) if w in _FIRST_PERSON]


def validate_announcement(ann: dict, inputs: dict) -> list[str]:
    """Schema rules re-checked in Python; each error is fed back to one retry."""
    errors: list[str] = []
    fmt = ann.get("format")
    context = ann.get("context") or ""
    if fmt not in FORMATS:
        return [f"format must be one of {', '.join(FORMATS)}"]
    if not context:
        errors.append("context is empty")
    if not inputs["has_turns"] and fmt != "no_quote":
        errors.append("there are no timestamped turns, so format must be no_quote")
    if fmt == "quote":
        words = len(ann["quote"].split())
        if not QUOTE_WORDS[0] <= words <= QUOTE_WORDS[1]:
            errors.append(f"quote is {words} words (must be {QUOTE_WORDS[0]}-{QUOTE_WORDS[1]})")
        if ann["source_speaker"] not in inputs["speakers"]:
            errors.append(f"source_speaker {ann['source_speaker']!r} is not a speaker label in the turns")
        if parse_timestamp(ann["source_timestamp"]) is None:
            errors.append(f"source_timestamp {ann['source_timestamp']!r} is not MM:SS")
        people = {p.casefold() for p in inputs["people"]}
        if ann["source_person"].casefold() not in people:
            errors.append(f"source_person {ann['source_person']!r} is not someone on this episode")
        if "..." in ann["quote"] or "…" in ann["quote"]:
            errors.append("quote contains an ellipsis; use one contiguous span")
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
    if x_post_length(post_body(ann)) > X_POST_LIMIT:
        errors.append(f"the X post is {x_post_length(post_body(ann))} chars (limit {X_POST_LIMIT})")
    return errors


def announcement_warnings(ann: dict, tags: dict, episode_number: int, page_url: str) -> list[str]:
    warnings: list[str] = []
    for i, post in enumerate(render_x_posts(ann, tags, episode_number, page_url), 1):
        if x_post_length(post) > X_POST_LIMIT:
            warnings.append(f"X post {i} is {x_post_length(post)} chars (limit {X_POST_LIMIT})")
    company = company_entity(tags.get("handles") or {})
    entities = ([company] if company else []) + credited_people(tags)
    untagged_li = [e["name"] for e in entities if not e["linkedin_name"]]
    if untagged_li:
        warnings.append(f"credited on LinkedIn in plain text (no linkedin_name): {', '.join(untagged_li)}")
    untagged_x = [e["name"] for e in entities if not e["x_handle"]]
    if untagged_x:
        warnings.append(f"credited on X in plain text (no x_handle): {', '.join(untagged_x)}")
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


def _generation_inputs(title: str, article: str, inputs: dict) -> str:
    turns = inputs["turns_text"] or "None: this transcript has no timestamped turns. Use format no_quote."
    return (
        f"--- EPISODE TITLE ---\n{title}\n\n"
        f"--- ON THIS EPISODE ---\n{person_line(inputs['hosts_present'], inputs['guests'])}\n"
        f"{voice_directive(inputs)}\n\n"
        f"--- ARTICLE ---\n{article}\n\n--- TIMESTAMPED TURNS ---\n{turns}\n"
    )


def generate_announcement(title: str, article: str, inputs: dict, guidance: str = "",
                          verbose: bool = False) -> tuple[dict | None, list[str]]:
    """One structured Codex call, one retry on rule violations; (None, errors) if Codex fails."""
    print("Writing the announcement with Codex...")
    prompt = load_prompt("announcement") + f"\n\n## This episode\n\n{voice_directive(inputs)}\n"
    if guidance:
        prompt += f"\nGuidance from the operator: {guidance}\n"
    stdin_text = _generation_inputs(title, article, inputs)
    ann, errors = None, []
    for _attempt in range(2):
        attempt_prompt = prompt + (
            "\nYour previous answer was rejected: " + "; ".join(errors) + ". Fix these.\n" if errors else ""
        )
        try:
            output = run_codex(attempt_prompt, stdin_text=stdin_text, verbose=verbose,
                               output_schema=ANNOUNCEMENT_SCHEMA)
            raw = json.loads(output)
        except SystemExit:
            return None, ["Codex failed"]
        except ValueError as e:
            errors = [f"output was not JSON ({e})"]
            continue
        if not isinstance(raw, dict):
            errors = ["output was not a JSON object"]
            continue
        ann = clean_announcement(raw, inputs)
        errors = validate_announcement(ann, inputs)
        if not errors:
            break
    return ann, errors


def check_quote(ann: dict, inputs: dict) -> dict:
    if ann.get("format") != "quote":
        return {"verified": False, "reason": "no verified quote", "diff": "", "turn": None}
    return verify_quote_against_turns(ann["quote"], inputs["turns"], ann["source_speaker"], ann["source_timestamp"])


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


def announcement_fingerprint(transcript: str, turns, page_url: str, target: dt.date, tags: dict) -> str:
    handles = {k: v for k, v in (tags.get("handles") or {}).items() if k != "_about"}
    payload = {
        "transcript_sha256": hashlib.sha256(transcript.encode("utf-8")).hexdigest(),
        "turns_sha256": hashlib.sha256(json.dumps(turns, sort_keys=True).encode("utf-8")).hexdigest() if turns else None,
        "page_url": page_url,
        "target_date": target.isoformat(),
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


def resolve_channels(configured: list[dict], fetched: dict[str, dict], done: dict) -> tuple[list[dict], list[str]]:
    """Configured channels still to post, or errors; nothing is posted when any is unusable."""
    channels, errors = [], []
    for conf in configured:
        cid = conf.get("id")
        if cid in done:
            continue
        channel = fetched.get(cid)
        label = f"{conf.get('service')} {conf.get('name') or ''} ({cid})".replace("  ", " ")
        if not channel:
            errors.append(f"{label} is not in this Buffer account")
        elif channel.get("isDisconnected") or channel.get("isLocked"):
            errors.append(f"{label} is disconnected or locked; reconnect it in Buffer")
        elif channel.get("service") not in ("linkedin", "twitter"):
            errors.append(f"{label} is a {channel.get('service')} channel, expected linkedin or twitter")
        else:
            channels.append(channel)
    return channels, errors


def post_input(channel: dict, text: str, due_at: dt.datetime, thread: list[str] | None = None) -> dict:
    payload = {
        "channelId": channel["id"],
        "text": text,
        "assets": [],
        "mode": "customScheduled",
        "schedulingType": "automatic",
        "dueAt": due_at.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if thread:
        payload["metadata"] = {"twitter": {"thread": [{"text": t, "assets": []} for t in thread]}}
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


def channel_posts(ann: dict, tags: dict, episode_number: int, page_url: str, channel: dict) -> tuple[str, list[str]]:
    if channel.get("service") == "twitter":
        main, reply = render_x_posts(ann, tags, episode_number, page_url)
        return main, [reply]
    return render_linkedin_post(ann, tags, episode_number, page_url), []


def _local(due: dt.datetime, channel: dict) -> str:
    tz = channel.get("timezone") or "UTC"
    try:
        local = due.astimezone(ZoneInfo(tz))
    except Exception:
        local = due
    return f"{local:%a %d %b %H:%M} {tz} ({due:%Y-%m-%d %H:%M} UTC)"


def schedule_channels(ann, tags, episode_number, page_url, channels, target, api_key, ledger_path,
                      now=None) -> list[dict]:
    """Create one post per channel; each success goes to the ledger before the next attempt."""
    results = []
    for channel in channels:
        due = announcement_due_at(channel, target, now=now)
        if not due:
            print(f"  ⚠ {channel['service']}: no usable slot in its Buffer posting schedule")
            results.append({"channel_id": channel["id"], "service": channel["service"], "error": "no schedule slot"})
            continue
        text, thread = channel_posts(ann, tags, episode_number, page_url, channel)
        try:
            post_id, error = create_buffer_post(api_key, post_input(channel, text, due, thread))
        except Exception as e:  # noqa: BLE001 - network/HTTP, reported not raised
            post_id, error = None, f"{type(e).__name__}: {e}"
        if not post_id:
            print(f"  ⚠ {channel['service']}: {error}")
            results.append({"channel_id": channel["id"], "service": channel["service"], "error": error})
            continue
        entry = {
            "channel_id": channel["id"],
            "service": channel["service"],
            "post_id": post_id,
            "due_at": due.isoformat(),
            "scheduled_at": dt.datetime.now(_UTC).replace(microsecond=0).isoformat(),
            "text": text,
            "thread": thread,
        }
        append_ledger(ledger_path, entry)
        print(f"  ✓ {channel['service']}: {_local(due, channel)} ({post_id})")
        results.append(entry)
    return results


# --- preview, approval, record ----------------------------------------------


def preview_announcement(ann, verification, errors, tags, inputs, episode_number, page_url, channels,
                         done, release_at, target, now=None) -> None:
    rule = "=" * 70
    print(f"\n{rule}\nANNOUNCEMENT  {page_url}\n{rule}")
    print(person_line(inputs["hosts_present"], inputs["guests"]))
    voice = "first person (Andrey present)" if inputs["andrey_present"] else "third person (Andrey absent)"
    print(f"Voice: {voice}   Format: {ann['format']}")
    if ann["format"] == "quote":
        state = "verified" if verification["verified"] else f"NOT VERIFIED: {verification['reason']}"
        print(f"Quote evidence: [{ann['source_speaker']}] {ann['source_timestamp']} -> {ann['source_person']} ({state})")
        if verification.get("diff"):
            print(f"  diff vs transcript: {verification['diff']}")
    else:
        print("Quote evidence: no verified quote")
    if ann.get("speaker_map"):
        print("Speakers: " + ", ".join(f"[{m['label']}] {m['person']}" for m in ann["speaker_map"]))

    body = render_linkedin_post(ann, tags, episode_number, page_url)
    print(f"\n-- LinkedIn ({len(body)} chars) --\n{body}")
    for i, post in enumerate(render_x_posts(ann, tags, episode_number, page_url)):
        print(f"\n-- X {'post' if i == 0 else 'reply'} ({x_post_length(post)}/{X_POST_LIMIT}) --\n{post}")
    print(f"\nTagged on LinkedIn: {', '.join(tag_set(tags, 'linkedin')) or 'nobody'}")
    print(f"Tagged on X:        {', '.join(tag_set(tags, 'x')) or 'nobody'}")

    print(f"\n-- Schedule (release {release_at.astimezone(_UTC):%a %d %b %H:%M} UTC + "
          f"{ANNOUNCEMENT_LEAD_DAYS} days: earliest {target:%a %d %b %Y}) --")
    earliest = None
    for channel in channels:
        due = announcement_due_at(channel, target, now=now)
        if not due:
            print(f"  {channel['service']}: no usable slot in its Buffer posting schedule")
            continue
        earliest = min(earliest or due, due)
        flag = "  ⚠ before the Podbean release" if due < release_at else ""
        print(f"  {channel['service']} {channel.get('displayName') or channel.get('name')}: {_local(due, channel)}{flag}")
    for entry in done.values():
        print(f"  {entry.get('service')}: already scheduled ({entry.get('post_id')}, due {entry.get('due_at')})")
        print("    " + (entry.get("text") or "").replace("\n", "\n    "))
    if earliest:
        print(f"⚠ The posts link {page_url}: push and deploy the page before {earliest:%a %d %b %H:%M} UTC.")

    problems = [f"rule: {e}" for e in errors] + announcement_warnings(ann, tags, episode_number, page_url)
    if problems:
        print(f"\n⚠ {len(problems)} warning(s):")
        for p in problems:
            print(f"  - {p}")


def approve_announcement(title, article, inputs, tags, episode_number, page_url, channels, done,
                         release_at, target, input_func=input, verbose=False, now=None) -> dict | None:
    """Generate, preview, then approve / regenerate with guidance / skip. Returns the saved record."""
    guidance = ""
    while True:
        ann, errors = generate_announcement(title, article, inputs, guidance=guidance, verbose=verbose)
        if ann is None:
            print("Generation failed. 'r' to retry, or Enter to skip Buffer: ", end="", flush=True)
            if input_func().strip().lower() != "r":
                return None
            continue
        verification = check_quote(ann, inputs)
        preview_announcement(ann, verification, errors, tags, inputs, episode_number, page_url, channels,
                             done, release_at, target, now=now)
        failed_quote = ann["format"] == "quote" and not verification["verified"]
        approve_key = "o" if failed_quote else "a"
        if failed_quote:
            print("\n'o' to post the quote anyway (logged as operator-verified), 'r' to regenerate with guidance,")
        else:
            print("\n'a' to approve and schedule, 'r' to regenerate with guidance,")
        print("or 's' to skip Buffer for this episode: ", end="", flush=True)
        choice = input_func().strip().lower()
        if choice == approve_key:
            if ann["format"] != "quote":
                quote_verified = "none"
            else:
                quote_verified = "transcript" if verification["verified"] else "operator"
            return {"announcement": ann, "quote_verified": quote_verified}
        if choice == "s":
            return None
        if choice == "r":
            print("Guidance (e.g. 'use the guest's line about SHA pinning'): ", end="", flush=True)
            guidance = input_func().strip()
        else:
            print("Invalid choice, try again.")


def load_saved_announcement(path: str, fingerprint: str, input_func=input) -> dict | None:
    """A previously approved announcement, only if built from the same inputs."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except OSError:
        return None
    except ValueError as e:
        print(f"⚠ Could not read {path} ({e}); regenerating")
        return None
    if saved.get("fingerprint") != fingerprint:
        print("Saved announcement was built from other inputs (transcript, page, date, hosts or tags); regenerating.")
        return None
    ann = saved.get("announcement") or {}
    print(f"\nFound saved announcement ({ann.get('format')}): {post_body(ann)[:100]}")
    print("Press Enter to reuse, or type 'new' to regenerate: ", end="", flush=True)
    if input_func().strip().lower() == "new":
        return None
    return saved


def render_announcement_markdown(record: dict, tags: dict, episode_number: int, page_url: str,
                                 ledger: dict[str, dict], failures: list[dict]) -> str:
    ann = record["announcement"]
    x_main, x_reply = render_x_posts(ann, tags, episode_number, page_url)
    lines = [f"# Episode {episode_number} announcement", "", f"Page: {page_url}", ""]
    if ann["format"] == "quote":
        lines += [f"Quote: [{ann['source_speaker']}] {ann['source_timestamp']} -> {ann['source_person']} "
                  f"(quote_verified: {record['quote_verified']})", ""]
    else:
        lines += [f"Format: {ann['format']} (no verified quote)", ""]
    lines += ["## LinkedIn", "", render_linkedin_post(ann, tags, episode_number, page_url), "",
              "## X", "", x_main, "", "Reply:", "", x_reply, "", "## Scheduled", ""]
    for entry in ledger.values():
        lines.append(f"- {entry.get('service')}: {entry.get('due_at')} ({entry.get('post_id')})")
    for entry in failures:
        lines.append(f"- {entry.get('service')}: FAILED {entry.get('error')}")
    return "\n".join(lines).rstrip() + "\n"


def schedule_episode_announcement(
    out_base: str,
    episode_number: int,
    page_path: str,
    title: str,
    article: str,
    transcript: str,
    turns: list[dict] | None,
    guest_context: dict,
    audio_path: str,
    input_func=input,
    api_key: str | None = None,
    handles: dict | None = None,
    now: dt.datetime | None = None,
    verbose: bool = False,
) -> None:
    """Approve and schedule the announcement on every configured channel not yet in the ledger.

    Re-runnable via --episode-number: the ledger keeps channels from being
    posted twice, and the eligibility record keeps historical pages out.
    """
    api_key = api_key or os.environ.get("BUFFER_API_KEY")
    if not api_key:
        print("\nBUFFER_API_KEY not set; skipping the Buffer announcement.")
        return
    release_at = load_announcement_eligibility(out_base)
    if release_at is None:
        print(f"\nNo {os.path.basename(out_base)}{ELIGIBILITY_SUFFIX} (episode not released by this "
              "pipeline); skipping the Buffer announcement.")
        return
    handles = load_social_handles() if handles is None else handles
    configured = [c for c in handles.get("buffer_channels") or [] if isinstance(c, dict) and c.get("id")]
    if not configured:
        print("\nNo buffer_channels in social-handles.json; skipping the Buffer announcement.")
        return

    ledger_path = f"{out_base}{LEDGER_SUFFIX}"
    done = load_ledger(ledger_path)
    if all(c["id"] in done for c in configured):
        print(f"\n✓ Announcement already scheduled on every channel ({os.path.basename(ledger_path)}).")
        return

    page_url = episode_page_url(page_path)
    target = announcement_target_date(release_at)
    try:
        fetched = fetch_buffer_channels(api_key)
    except Exception as e:  # noqa: BLE001 - network/HTTP, reported not raised
        print(f"\n⚠ Buffer channel lookup failed ({type(e).__name__}: {e}); skipping. "
              f"Re-run with --episode-number {episode_number} to retry.")
        return
    channels, errors = resolve_channels(configured, fetched, done)
    if errors:
        print("\n⚠ Buffer announcement not scheduled:")
        for error in errors:
            print(f"  - {error}")
        return

    guest_context = confirm_hosts_present(guest_context, audio_path, handles,
                                          guests_file=f"{out_base}-guests.json", input_func=input_func)
    tags = tagging_context(guest_context, handles)
    inputs = build_announcement_inputs(turns, guest_context)
    fingerprint = announcement_fingerprint(transcript, turns, page_url, target, tags)
    saved_path = f"{out_base}{SAVED_SUFFIX}"

    record = load_saved_announcement(saved_path, fingerprint, input_func=input_func)
    if record:
        ann = record["announcement"]
        preview_announcement(ann, check_quote(ann, inputs), validate_announcement(ann, inputs), tags, inputs,
                             episode_number, page_url, channels, done, release_at, target, now=now)
        print("\n'a' to schedule, anything else to skip: ", end="", flush=True)
        if input_func().strip().lower() != "a":
            print("Skipped the Buffer announcement.")
            return
    else:
        record = approve_announcement(title, article, inputs, tags, episode_number, page_url, channels, done,
                                      release_at, target, input_func=input_func, verbose=verbose, now=now)
        if not record:
            print("Skipped the Buffer announcement.")
            return
        record = {"fingerprint": fingerprint, **record,
                  "approved_at": dt.datetime.now(_UTC).replace(microsecond=0).isoformat()}
        with open(saved_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"✓ Announcement saved to {saved_path}")

    print("\nScheduling on Buffer...")
    results = schedule_channels(record["announcement"], tags, episode_number, page_url, channels, target,
                                api_key, ledger_path, now=now)
    failures = [r for r in results if not r.get("post_id")]
    record_path = f"{out_base}{RECORD_SUFFIX}"
    with open(record_path, "w", encoding="utf-8") as f:
        f.write(render_announcement_markdown(record, tags, episode_number, page_url, load_ledger(ledger_path), failures))
    print(f"✓ Announcement recorded in {record_path}")
    if failures:
        print(f"⚠ Failed on {', '.join(r['service'] for r in failures)}; re-run with --episode-number "
              f"{episode_number} to retry just those (the rest are in {os.path.basename(ledger_path)}).")
