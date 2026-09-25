"""
Episode packaging after the article is final: YouTube chapters from timestamped
turns, one structured Codex call for subtitle / YouTube / Podbean copy, and the
builders that turn those into the upload description and show notes.
House rules: youtube-description.md and podcast-description.md.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys

from episode_pipeline import PROMPTS_DIR, guest_full_names, load_prompt, run_codex

SITE_URL = "https://devsecops.fm/"
COMPANY_LINKEDIN_URL = "https://www.linkedin.com/company/devsecops-talks/"
YOUTUBE_CHANNEL_URL = "https://www.youtube.com/channel/UCRjpE9xKxZeBkRgYiLErEjw"
METADATA_SCHEMA = os.path.join(PROMPTS_DIR, "metadata-schema.json")

CHAPTER_TURN_TEXT_CAP = 300
CHAPTER_MIN_COUNT = 3
CHAPTER_MIN_GAP_S = 10
CHAPTER_TARGET = (5, 8)
YOUTUBE_TITLE_MAX_CHARS = 100
YOUTUBE_HOOK_MAX_CHARS = 400
YOUTUBE_DESC_MAX_CHARS = 5000
YOUTUBE_DESC_TARGET_WORDS = (200, 350)
DEVSECOPS_HASHTAG = "#DevSecOps"
HASHTAG_LAST = "#DevSecOpsTalks"
HASHTAG_FALLBACKS = ("#DevOps", "#CloudSecurity", "#Security")
READ_WORDS_PER_MINUTE = 220

_CHAPTER_LINE = re.compile(r"^((?:\d{1,2}:)?\d{1,2}:\d{2})\s*[-–—:]\s*(.+)$")
_SKIPPED_MARKER = "# chapters skipped by operator"


# --- chapters ---------------------------------------------------------------


def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_timestamp(stamp: str) -> int | None:
    """Seconds in ``MM:SS`` or ``H:MM:SS`` (digits only), or None."""
    parts = str(stamp or "").strip().split(":")
    if not 2 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def parse_chapters(text: str) -> list[tuple[int, str]]:
    """``MM:SS - Label`` lines as (seconds, label); other lines are ignored."""
    parsed = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*").strip()
        match = _CHAPTER_LINE.match(line)
        if match:
            parsed.append((parse_timestamp(match.group(1)), match.group(2).strip()))
    return parsed


def validate_youtube_chapters(text: str, duration_s: float | None = None) -> list[str]:
    """Why YouTube would not render these chapters; empty when it would."""
    chapters = parse_chapters(text)
    errors: list[str] = []
    if len(chapters) < CHAPTER_MIN_COUNT:
        errors.append(f"{len(chapters)} chapter line(s); YouTube needs at least {CHAPTER_MIN_COUNT}")
    if chapters and chapters[0][0] != 0:
        errors.append(f"first chapter starts at {format_timestamp(chapters[0][0])}, not 00:00")
    for (a, _), (b, label) in zip(chapters, chapters[1:]):
        if b <= a:
            errors.append(f"{format_timestamp(b)} - {label} is not after {format_timestamp(a)}")
        elif b - a < CHAPTER_MIN_GAP_S:
            errors.append(f"{format_timestamp(b)} - {label} is under {CHAPTER_MIN_GAP_S}s after the previous chapter")
    if duration_s and chapters and chapters[-1][0] >= duration_s:
        errors.append(f"last chapter {format_timestamp(chapters[-1][0])} is past the end of the recording")
    return errors


def render_chapters(text: str) -> str:
    """Normalise to one ``MM:SS - Label`` per line."""
    return "\n".join(f"{format_timestamp(s)} - {label}" for s, label in parse_chapters(text))


def format_turn_line(turn: dict, cap: int | None = None) -> str:
    """``[MM:SS] [A]: text`` with whitespace collapsed; ``cap`` trims at a word."""
    text = " ".join(str(turn.get("text") or "").split())
    if cap is not None and len(text) > cap:
        text = text[:cap].rsplit(" ", 1)[0] + " ..."
    return f"[{format_timestamp(float(turn.get('start') or 0))}] [{turn.get('speaker')}]: {text}"


def turns_for_prompt(turns: list[dict], cap: int = CHAPTER_TURN_TEXT_CAP) -> str:
    """One line per turn, text capped so long episodes stay bounded."""
    return "\n".join(format_turn_line(turn, cap) for turn in turns)


def generate_chapters(article: str, turns: list[dict], guidance: str = "", verbose: bool = False) -> str:
    prompt = load_prompt("chapters")
    if guidance:
        prompt += f"\nAdditional guidance from the operator: {guidance}"
    stdin_text = f"--- ARTICLE ---\n{article}\n\n--- TIMESTAMPED TURNS ---\n{turns_for_prompt(turns)}\n"
    return render_chapters(run_codex(prompt, stdin_text=stdin_text, verbose=verbose))


def load_or_generate_chapters(
    out_base: str,
    article: str,
    turns: list[dict] | None,
    verbose: bool = False,
    input_func=input,
) -> str:
    """Chapters for the YouTube description, or "" when there are none.

    A hand-written ``-chapters.txt`` wins; otherwise chapters are proposed from
    the timestamped turns and saved to ``-chapters-generated.txt`` once approved.
    """
    manual_file = f"{out_base}-chapters.txt"
    generated_file = f"{out_base}-chapters-generated.txt"
    duration = float(turns[-1].get("end") or 0) if turns else None

    if os.path.isfile(manual_file):
        with open(manual_file, "r", encoding="utf-8") as f:
            manual = f.read()
        errors = validate_youtube_chapters(manual, duration)
        if errors:
            print(f"Error: {manual_file} would not render as YouTube chapters:")
            for error in errors:
                print(f"  - {error}")
            print("Fix or delete the file, then re-run.")
            sys.exit(1)
        print(f"✓ Using hand-written chapters from {manual_file}")
        return render_chapters(manual)

    if os.path.isfile(generated_file):
        with open(generated_file, "r", encoding="utf-8") as f:
            saved = f.read()
        if saved.strip() == _SKIPPED_MARKER:
            print(f"✓ Chapters skipped earlier ({generated_file}); YouTube description has none")
            return ""
        if not validate_youtube_chapters(saved, duration):
            print(f"✓ Loaded approved chapters from {generated_file}")
            return render_chapters(saved)
        print(f"⚠ {generated_file} no longer validates; proposing new chapters")

    if not turns:
        print(
            "\n⚠ No timestamped turns for this transcript (OpenAI backend, --transcript, or an "
            "older run): the YouTube description will have no chapters. "
            f"Write {manual_file} by hand to add them."
        )
        return ""

    guidance = ""
    while True:
        print("\nProposing YouTube chapters from the timestamped transcript...")
        chapters = generate_chapters(article, turns, guidance=guidance, verbose=verbose)
        errors = validate_youtube_chapters(chapters, duration)
        print(f"\n{chapters or '(no chapter lines returned)'}\n")
        for error in errors:
            print(f"  ✗ {error}")
        low, high = CHAPTER_TARGET
        count = len(parse_chapters(chapters))
        if not errors and not low <= count <= high:
            print(f"  ⚠ {count} chapters (target {low}-{high})")
        prompt = "Press Enter to accept, " if not errors else ""
        print(f"{prompt}'r' to regenerate with guidance, or 's' to skip chapters: ", end="", flush=True)
        try:
            choice = input_func().strip().lower()
        except EOFError:
            choice = "s" if errors else ""
        if choice == "" and not errors:
            with open(generated_file, "w", encoding="utf-8") as f:
                f.write(chapters + "\n")
            print(f"✓ Chapters saved to {generated_file}")
            return chapters
        if choice == "s":
            with open(generated_file, "w", encoding="utf-8") as f:
                f.write(_SKIPPED_MARKER + "\n")
            print("✓ Skipping chapters")
            return ""
        if choice == "r":
            print("Guidance for the new chapters: ", end="", flush=True)
            try:
                guidance = input_func().strip()
            except EOFError:
                guidance = ""
        else:
            print("Invalid choice, try again.")


# --- metadata ---------------------------------------------------------------


def readtime_for(article: str) -> str:
    words = len(re.sub(r"\{\{[<%].*?[>%]\}\}", " ", article).split())
    return f"{max(1, round(words / READ_WORDS_PER_MINUTE))} min read"


def validate_metadata(meta: dict, guest_names: list[str] = ()) -> list[str]:
    """Checks the schema cannot express; empty when the metadata is usable."""
    errors: list[str] = []
    for key in ("subtitle", "youtube_title", "youtube_hook", "youtube_intro",
                "youtube_substance", "podcast_hook", "podcast_who_what"):
        if not str(meta.get(key) or "").strip():
            errors.append(f"{key} is empty")
    for key, low, high in (("youtube_learn", 3, 4), ("podcast_learn", 3, 5), ("youtube_hashtags", 5, 5)):
        items = [str(i).strip() for i in meta.get(key) or [] if str(i).strip()]
        if not low <= len(items) <= high:
            errors.append(f"{key} has {len(items)} item(s), expected {low}-{high}")
    for key in ("youtube_intro", "podcast_who_what"):
        folded = str(meta.get(key) or "").casefold()
        missing = [n for n in guest_names if n.casefold() not in folded]
        if missing:
            errors.append(f"{key} does not name guest(s): {', '.join(missing)}")
    return errors


def _metadata_inputs(title: str, teaser: str, article: str, transcript: str, guest_text: str) -> str:
    return (
        f"--- EPISODE TITLE ---\n{title}\n\n--- TEASER ---\n{teaser}\n\n"
        + (f"--- GUEST CONTEXT ---\n{guest_text}\n\n" if guest_text else "")
        + f"--- ARTICLE ---\n{article}\n\n--- TRANSCRIPT ---\n{transcript}\n"
    )


def extract_metadata(
    title: str,
    teaser: str,
    article: str,
    transcript: str,
    guest_context: dict | None = None,
    guest_text: str = "",
    verbose: bool = False,
) -> dict:
    """One structured Codex call; one retry on unusable output, then stop."""
    print("Packaging YouTube and Podbean copy with Codex...")
    stdin_text = _metadata_inputs(title, teaser, article, transcript, guest_text)
    prompt = load_prompt("metadata")
    errors: list[str] = []
    for _attempt in range(2):
        attempt_prompt = prompt
        if errors:
            attempt_prompt += "\nYour previous answer was rejected: " + "; ".join(errors) + ". Fix these."
        output = run_codex(attempt_prompt, stdin_text=stdin_text, verbose=verbose, output_schema=METADATA_SCHEMA)
        try:
            meta = json.loads(output)
        except json.JSONDecodeError as e:
            errors = [f"output was not JSON ({e})"]
            continue
        if not isinstance(meta, dict):
            errors = ["output was not a JSON object"]
            continue
        errors = validate_metadata(meta, guest_full_names(guest_context))
        if not errors:
            return meta
    print("Error: metadata packaging failed: " + "; ".join(errors), file=sys.stderr)
    print("Nothing was uploaded. Re-run to retry this step.", file=sys.stderr)
    sys.exit(1)


def _inputs_fingerprint(title: str, teaser: str, article: str) -> str:
    return hashlib.sha256("\0".join((title, teaser, article)).encode("utf-8")).hexdigest()


def load_or_generate_metadata(
    out_base: str,
    title: str,
    teaser: str,
    article: str,
    transcript: str,
    guest_context: dict | None = None,
    guest_text: str = "",
    verbose: bool = False,
) -> dict:
    """``-metadata.json``, regenerated when the title, teaser or article changed."""
    metadata_file = f"{out_base}-metadata.json"
    fingerprint = _inputs_fingerprint(title, teaser, article)
    if os.path.isfile(metadata_file):
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if saved.get("inputs_sha256") == fingerprint and not validate_metadata(
                saved.get("metadata") or {}, guest_full_names(guest_context)
            ):
                print(f"✓ Loaded metadata from {metadata_file}")
                return saved["metadata"]
            print("Title, teaser or article changed since the saved metadata; regenerating.")
        except (OSError, ValueError, AttributeError) as e:
            print(f"⚠ Could not read {metadata_file} ({e}); regenerating")

    meta = extract_metadata(title, teaser, article, transcript, guest_context, guest_text, verbose)
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump({"inputs_sha256": fingerprint, "metadata": meta}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"✓ Metadata saved to {metadata_file} (subtitle: {meta['subtitle'][:60]})")
    return meta


# --- builders ---------------------------------------------------------------


def episode_short_url(episode_number: int) -> str:
    return f"{SITE_URL}episodes/{episode_number:03d}/"


def _plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text or "")
    text = text.replace("**", "").replace("`", "").replace("—", "-")
    return " ".join(text.split())


def _items(meta: dict, key: str) -> list[str]:
    return [_plain(str(i)).lstrip("-").strip() for i in meta.get(key) or [] if str(i).strip()]


def normalize_hashtags(tags: list[str]) -> list[str]:
    """Five tags: #DevSecOps first, #DevSecOpsTalks last, gaps from house tags."""
    fixed = {DEVSECOPS_HASHTAG.casefold(), HASHTAG_LAST.casefold()}
    middle: list[str] = []
    seen = set(fixed)
    for raw in tags or []:
        tag = "#" + re.sub(r"\s+", "", str(raw)).lstrip("#")
        if len(tag) > 1 and tag.casefold() not in seen:
            middle.append(tag)
            seen.add(tag.casefold())
    for fallback in HASHTAG_FALLBACKS:
        if fallback.casefold() not in seen:
            middle.append(fallback)
            seen.add(fallback.casefold())
    return [DEVSECOPS_HASHTAG] + middle[:3] + [HASHTAG_LAST]


def build_youtube_title(metadata: dict | None, episode_number: int, title: str) -> str:
    """``<hook> - DevSecOps Talks #NN``, the hook trimmed at a word to YouTube's limit."""
    suffix = f" - DevSecOps Talks #{episode_number}"
    hook = _plain(str((metadata or {}).get("youtube_title") or "")) or _plain(title)
    room = YOUTUBE_TITLE_MAX_CHARS - len(suffix)
    if len(hook) > room:
        hook = hook[:room].rsplit(" ", 1)[0].rstrip(" -:,.")
    return hook + suffix


def _guest_link_lines(guest_context: dict | None) -> list[str]:
    lines: list[str] = []
    for guest in (guest_context or {}).get("guests") or []:
        name = str(guest.get("full_name") or "").strip()
        links = guest.get("links") or []
        best = next(
            (str(link.get("url")).strip()
             for wanted in ("linkedin", "official", "company", "github")
             for link in links
             if str(link.get("type") or "").strip() == wanted and link.get("url")),
            "",
        )
        if name and best:
            lines.extend([f"{name}", best, ""])
    return lines


def build_youtube_description(
    metadata: dict,
    episode_number: int,
    chapters: str = "",
    guest_context: dict | None = None,
) -> str:
    """Plain text for upload-post; URLs on their own lines so YouTube does not ellipsize them."""
    meta = metadata or {}
    lines: list[str] = [_plain(meta.get("youtube_hook", "")), ""]
    learn = _items(meta, "youtube_learn")
    if learn:
        lines.append("What you will learn in this episode:")
        lines.extend(f"- {item}" for item in learn)
        lines.append("")
    for key in ("youtube_intro", "youtube_substance"):
        if _plain(meta.get(key, "")):
            lines.extend([_plain(meta[key]), ""])
    if _plain(meta.get("youtube_comment_prompt", "")):
        lines.extend([_plain(meta["youtube_comment_prompt"]), ""])
    if chapters and not validate_youtube_chapters(chapters):
        lines.append("Timestamps:")
        lines.extend(render_chapters(chapters).splitlines())
        lines.append("")
    lines.extend([
        "____________________________",
        "Episode page, full article and audio",
        episode_short_url(episode_number),
        "",
        "Discuss the episode on LinkedIn",
        COMPANY_LINKEDIN_URL,
        "",
    ])
    lines.extend(_guest_link_lines(guest_context))
    lines.extend([
        "Podcast website",
        SITE_URL,
        "",
        "Subscribe on YouTube",
        f"{YOUTUBE_CHANNEL_URL}?sub_confirmation=1",
        "",
        " ".join(normalize_hashtags(meta.get("youtube_hashtags") or [])),
    ])
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def youtube_description_warnings(description: str, metadata: dict, chapters: str = "") -> list[str]:
    """House-style checks from youtube-description.md, printed rather than enforced."""
    warnings: list[str] = []
    hook = _plain((metadata or {}).get("youtube_hook", ""))
    if len(hook) > YOUTUBE_HOOK_MAX_CHARS:
        warnings.append(f"hook is {len(hook)} chars (target under {YOUTUBE_HOOK_MAX_CHARS})")
    if not _plain((metadata or {}).get("youtube_comment_prompt", "")):
        warnings.append("no comment prompt")
    count = 0 if not chapters or validate_youtube_chapters(chapters) else len(parse_chapters(chapters))
    low, high = CHAPTER_TARGET
    if not count:
        warnings.append("no chapters")
    elif not low <= count <= high:
        warnings.append(f"{count} chapters (target {low}-{high})")
    if len(description) > YOUTUBE_DESC_MAX_CHARS:
        warnings.append(f"{len(description)} chars; YouTube's cap is {YOUTUBE_DESC_MAX_CHARS}")
    prose = description.split("Timestamps:", 1)[0].split("____", 1)[0]
    words = len(prose.split())
    low, high = YOUTUBE_DESC_TARGET_WORDS
    if not low <= words <= high:
        warnings.append(f"{words} words of prose (target {low}-{high})")
    return warnings


def build_podbean_show_notes(metadata: dict, episode_number: int) -> str:
    """HTML show notes limited to the tags Apple Podcasts and Spotify render."""
    meta = metadata or {}
    esc = lambda text: html.escape(_plain(text), quote=True)  # noqa: E731
    parts = [f"<p>{esc(meta.get('podcast_hook', ''))}</p>", f"<p>{esc(meta.get('podcast_who_what', ''))}</p>"]
    learn = _items(meta, "podcast_learn")
    if learn:
        parts.append("<p><strong>What you will learn</strong></p>")
        parts.append("<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in learn) + "</ul>")
    url = episode_short_url(episode_number)
    parts.append(f"<p>Full article and show notes: <a href='{url}'>{url}</a></p>")
    parts.append(f"<p><a href='{COMPANY_LINKEDIN_URL}'>Discuss the episode on LinkedIn</a></p>")
    parts.append(f"<p><a href='{YOUTUBE_CHANNEL_URL}'>DevSecOps Talks on YouTube</a></p>")
    return "".join(p for p in parts if p != "<p></p>")
