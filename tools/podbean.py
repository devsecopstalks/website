#!/usr/bin/env python3

import os
import re
import argparse
import glob
import hashlib
import json
import requests
import mimetypes
import datetime
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import voice_match
from episode_pipeline import (
    ALLOWED_ARTICLE_TAGS,
    AUTHOR_HOST,
    PipelineStop,
    article_html_problems,
    correct_transcript,
    generate_article,
    guest_context_to_prompt_text,
    guest_full_names,
    load_raw_companion_markdown,
    load_guest_context,
    operator_guest_context,
    pick_description,
    pick_title,
    render_corrected_transcript,
    research_guests,
    save_guest_context,
)
from episode_metadata import (
    COMPANY_LINKEDIN_URL,
    build_podbean_show_notes,
    build_youtube_description,
    build_youtube_title,
    load_or_generate_chapters,
    load_or_generate_metadata,
    readtime_for,
    youtube_description_warnings,
)
from buffer_announce import (
    AnnouncementStop,
    approve_episode_announcement,
    episode_page_url,
    load_announcement_eligibility,
    preflight_buffer,
    record_announcement_eligibility,
    schedule_episode_announcement,
)
from generate_cover import draw_cover
from transcribe_local import resolve_cli, transcribe_local
from r2_staging import (
    R2CoverError,
    check_cover_lifecycle,
    cover_public_url,
    require_cover_client,
    upload_cover_to_r2,
    load_r2_youtube_staging_marker,
    remove_r2_youtube_staging_marker,
    r2_public_uploads_configured,
    save_r2_youtube_staging_marker,
    upload_staging_video_to_r2,
    wants_r2_staging_for_local_video,
)
from youtube import (
    scheduled_upload_job_id,
    status_to_youtube_embed_url,
    upload_to_youtube,
    youtube_embed_url_to_video_id,
    youtube_status_error_message,
)

# Podbean API docs
# https://developers.podbean.com/podbean-api-docs/

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(TOOLS_DIR, "raw")
OUT_DIR = os.path.join(TOOLS_DIR, "out")
DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
EPISODES_DIR = os.path.join(TOOLS_DIR, "..", "content", "episodes")

# Default Hugo front matter when --participants is omitted (current hosts).
DEFAULT_PARTICIPANTS = ["Paulina", "Mattias", "Andrey"]
TITLE_TARGET_CHARS = 55


@dataclass(frozen=True)
class PublishSchedule:
    """Normalized publish time for Podbean and upload-post."""

    source: str
    podbean_timestamp: int
    podbean_datetime: datetime.datetime
    display: str
    upload_post_scheduled_date: str
    upload_post_timezone: str | None = None


@dataclass(frozen=True)
class PodbeanEpisodePlan:
    """Episode numbering and scheduling context from Podbean."""

    next_episode_number: int
    anchor_episode: dict | None
    anchor_datetime: datetime.datetime | None
    publish_datetimes: tuple[datetime.datetime, ...]


GUEST_ROLE_STARTERS = {
    "advocate",
    "architect",
    "ceo",
    "chief",
    "ciso",
    "cloud",
    "co-founder",
    "cofounder",
    "consultant",
    "cto",
    "developer",
    "director",
    "engineer",
    "engineering",
    "evangelist",
    "founder",
    "head",
    "lead",
    "manager",
    "maintainer",
    "owner",
    "principal",
    "product",
    "professor",
    "researcher",
    "security",
    "senior",
    "software",
    "staff",
    "vice",
    "vp",
}


def checkpoint_prefix(episode_number: int) -> str:
    """Basename for tools/out/ files, e.g. episode097 (matches Podbean episode index)."""
    return f"episode{episode_number:03d}"


def audio_source_identity(audio_path: str) -> dict:
    """Stable identity used to prevent checkpoints crossing between recordings."""
    digest = hashlib.sha256()
    with open(audio_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "filename": os.path.basename(audio_path),
        "filesize": os.path.getsize(audio_path),
        "sha256": digest.hexdigest(),
    }


def validate_or_bind_checkpoint_source(
    out_base: str,
    audio_path: str,
    checkpoint_files: list[Path],
    input_func=input,
) -> None:
    """Validate checkpoint ownership, prompting once for legacy checkpoint sets."""
    source_file = f"{out_base}-source.json"
    current = audio_source_identity(audio_path)

    if os.path.isfile(source_file):
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError, TypeError) as e:
            raise ValueError(f"cannot read checkpoint source identity: {e}") from e
        if saved != current:
            saved_name = str(saved.get("filename") or "unknown") if isinstance(saved, dict) else "unknown"
            raise ValueError(
                "checkpoint source mismatch: checkpoints belong to "
                f"{saved_name}, selected audio is {current['filename']}"
            )
        print(f"✓ Checkpoint source verified: {current['filename']}")
        return

    if checkpoint_files:
        print(
            "\nLegacy checkpoints have no saved source identity.\n"
            f"Reuse them with {current['filename']} ({current['filesize'] / (1024 * 1024):.1f} MB)? [y/N]"
        )
        print("> ", end="", flush=True)
        try:
            confirmed = input_func().strip().lower()
        except EOFError:
            confirmed = ""
        if confirmed not in ("y", "yes"):
            raise ValueError(
                "checkpoint reuse was not confirmed; remove the stale episode checkpoints "
                "or select their original audio"
            )

    with open(source_file, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
        f.write("\n")
    print(f"✓ Checkpoint source saved: {current['filename']}")


def infer_resume_episode_number(next_episode_number: int) -> int | None:
    """Return the latest unfinished checkpoint set adjacent to Podbean's next number."""
    numbers: set[int] = set()
    if os.path.isdir(OUT_DIR):
        for path in Path(OUT_DIR).glob("episode*"):
            match = re.match(r"episode(\d+)(?:[.-]|$)", path.name)
            if match:
                numbers.add(int(match.group(1)))

    for number in sorted(numbers, reverse=True):
        # A generated page is the completion marker for the local pipeline.
        page_exists = any(Path(EPISODES_DIR).glob(f"{number:03d}-*.md"))
        if not page_exists and number in (next_episode_number, next_episode_number - 1):
            return number
    return None


def episode_number_for_audio(audio_path: str) -> int | None:
    """Latest episode whose checkpoint source is this exact recording, e.g. a re-run for social posts."""
    current = audio_source_identity(audio_path)
    matches = []
    for path in Path(OUT_DIR).glob("episode*-source.json"):
        match = re.fullmatch(r"episode(\d+)-source\.json", path.name)
        if not match:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                if json.load(f) == current:
                    matches.append(int(match.group(1)))
        except (OSError, ValueError):
            continue
    return max(matches) if matches else None


def confirm_resume_for_audio(audio_path: str, next_episode_number: int, input_func=input) -> int | None:
    """Offer to resume the episode this recording already belongs to instead of starting a new one."""
    number = episode_number_for_audio(audio_path)
    if number is None or number == next_episode_number:
        return None
    print(f"\nThis recording already has checkpoints as episode #{number}.")
    print(f"Resume #{number} (Enter), or type 'new' to start it as #{next_episode_number}: ", end="", flush=True)
    try:
        answer = input_func().strip().lower()
    except EOFError:
        answer = ""
    return None if answer == "new" else number


def find_companion_video(audio_path: str) -> str | None:
    """Return path to a video next to the audio with the same filename prefix (stem)."""
    p = Path(audio_path).resolve()
    stem, parent = p.stem, p.parent
    for ext in (".mp4", ".mov", ".mkv"):
        matches = sorted(parent.glob(f"{stem}*{ext}"))
        if matches:
            return str(matches[0])
    return None


def find_mp3_files_in_raw() -> list[str]:
    """Find mp3 files in tools/raw/."""
    if not os.path.isdir(RAW_DIR):
        return []
    return sorted(str(f) for f in Path(RAW_DIR).glob("*.mp3"))


def _media_files_in(directory: str) -> list[str]:
    """Return sorted mp3/mp4 files in ``directory`` (empty if it does not exist)."""
    if not os.path.isdir(directory):
        return []
    found: list[str] = []
    for pattern in ("*.mp3", "*.mp4"):
        found.extend(str(f) for f in Path(directory).glob(pattern))
    return sorted(found)


def stage_downloads_to_raw() -> None:
    """Move new mp3/mp4 (and their sidecar transcripts) from ~/Downloads into raw/, re-run-safe.

    Cases:
    - Downloads has media, raw/ is empty: move everything in and proceed.
    - Both Downloads and raw/ have media: offer to clear raw/ and replace its
      contents with the new downloads.
    - Only raw/ has media (typical re-run): confirm proceeding with raw/
      (defaults to yes).
    - Neither has media: nothing to do; downstream resolution reports it.
    """
    downloads = _media_files_in(DOWNLOADS_DIR)
    raw = _media_files_in(RAW_DIR)

    if downloads and raw:
        print(f"Found media in both ~/Downloads and {RAW_DIR}/:")
        print("  ~/Downloads:")
        for f in downloads:
            print(f"    {os.path.basename(f)}")
        print(f"  {RAW_DIR}/:")
        for f in raw:
            print(f"    {os.path.basename(f)}")
        answer = input(
            "\nDelete everything currently in raw/ and move the new "
            "Downloads files in? [Y/n]: "
        ).strip().lower()
        if answer in ("n", "no"):
            print("Aborting without changing raw/ or ~/Downloads.")
            sys.exit(0)

        for entry in Path(RAW_DIR).iterdir():
            if entry.name == ".gitignore":
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        print(f"Cleared {RAW_DIR}/.")

    if downloads:
        # Sidecar transcripts ride along only when named after a downloaded MP3,
        # so unrelated .txt files in ~/Downloads stay put.
        mp3_stems = [Path(f).stem for f in downloads if f.lower().endswith(".mp3")]
        downloads += _sidecar_transcripts_in(DOWNLOADS_DIR, mp3_stems)
        os.makedirs(RAW_DIR, exist_ok=True)
        print(f"Moving {len(downloads)} file(s) from ~/Downloads to {RAW_DIR}/:")
        for src in downloads:
            dst = os.path.join(RAW_DIR, os.path.basename(src))
            shutil.move(src, dst)
            print(f"    {os.path.basename(src)}")
        return

    if raw:
        print(f"No new media in ~/Downloads. Found {len(raw)} file(s) in {RAW_DIR}/:")
        for f in raw:
            print(f"    {os.path.basename(f)}")
        answer = input("Proceed with files in raw/? [Y/n]: ").strip().lower()
        if answer in ("n", "no"):
            print("Aborting.")
            sys.exit(0)


def yaml_escape_double_quoted(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def resolve_youtube_video_id(value: str) -> str:
    """Hugo shortcode wants an 11-char id."""
    s = (value or "").strip()
    if not s:
        return ""
    if s.startswith("http"):
        return youtube_embed_url_to_video_id(s)
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", s):
        return s
    return youtube_embed_url_to_video_id(s)


def _local_timezone() -> datetime.tzinfo:
    return datetime.datetime.now().astimezone().tzinfo or datetime.timezone.utc


def _iso_utc_z(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def publish_schedule_from_datetime(dt: datetime.datetime, source: str) -> PublishSchedule:
    """Build a schedule from an aware publish datetime."""
    if dt.tzinfo is None:
        raise ValueError("publish datetime must include a timezone")
    dt = dt.replace(microsecond=0)
    if dt <= datetime.datetime.now(dt.tzinfo):
        raise ValueError("scheduled publish time must be in the future")
    return PublishSchedule(
        source=source,
        podbean_timestamp=int(dt.timestamp()),
        podbean_datetime=dt,
        display=dt.isoformat(),
        upload_post_scheduled_date=_iso_utc_z(dt),
        upload_post_timezone=None,
    )


def publish_schedule_from_podbean_episode(
    episode: dict,
    local_tz: datetime.tzinfo | None = None,
) -> PublishSchedule | None:
    """Recover a future schedule from an existing Podbean episode."""
    if str(episode.get("status") or "").strip().lower() == "draft":
        return None
    timestamp = _episode_publish_timestamp(episode)
    if timestamp is None:
        return None
    local_tz = local_tz or _local_timezone()
    publish_dt = datetime.datetime.fromtimestamp(timestamp, local_tz).replace(microsecond=0)
    if publish_dt <= datetime.datetime.now(local_tz):
        return None
    return PublishSchedule(
        source=f"existing Podbean {_episode_display_title(episode)}",
        podbean_timestamp=timestamp,
        podbean_datetime=publish_dt,
        display=publish_dt.isoformat(),
        upload_post_scheduled_date=_iso_utc_z(publish_dt),
        upload_post_timezone=None,
    )


def _coerce_int(value) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _episode_number_from_title(title: str) -> int | None:
    match = re.search(r"#\s*(\d+)", title or "")
    return int(match.group(1)) if match else None


def _episode_number_value(episode: dict) -> int | None:
    explicit = _coerce_int(episode.get("episode_number"))
    if explicit is not None and explicit > 0:
        return explicit
    return _episode_number_from_title(str(episode.get("title") or ""))


def find_podbean_episode(data: dict, episode_number: int) -> dict | None:
    """Find an episode by its explicit number or numbered title."""
    episodes = data.get("episodes") if isinstance(data, dict) else None
    if not isinstance(episodes, list):
        return None
    return next(
        (
            episode
            for episode in episodes
            if isinstance(episode, dict)
            and _episode_number_value(episode) == episode_number
        ),
        None,
    )


def podbean_player_id(response_or_episode: dict) -> str:
    """Extract the value accepted by the Podbean single-episode player."""
    if not isinstance(response_or_episode, dict):
        raise ValueError("Podbean response is not an object")
    if response_or_episode.get("error") or response_or_episode.get("error_description"):
        error = str(response_or_episode.get("error") or "API error").strip()
        description = str(response_or_episode.get("error_description") or "").strip()
        detail = ": ".join(part for part in (error, description) if part)
        detail = " ".join(detail.split())[:500]
        raise ValueError(f"Podbean rejected episode creation: {detail}")
    wrapped = response_or_episode.get("episode")
    episode = wrapped if isinstance(wrapped, dict) else response_or_episode

    player_url = str(episode.get("player_url") or "").strip()
    if player_url:
        parsed = urlparse(player_url)
        query_id = (parse_qs(parsed.query).get("i") or [""])[0].strip()
        if query_id:
            return query_id
        path_match = re.search(r"/media/player/([^/?#]+)", parsed.path)
        if path_match:
            return path_match.group(1)

    # Podbean's Episode object defines `id` as the unique episode identifier.
    # Draft creation responses may omit player_url, while the identifier is
    # still valid for the single-episode player URL used by our shortcode.
    episode_id = str(episode.get("id") or "").strip()
    if episode_id:
        return episode_id

    keys = ", ".join(sorted(str(key) for key in episode)) or "none"
    raise ValueError(f"Podbean episode has no player_url or id (fields: {keys})")


def _episode_publish_timestamp(episode: dict) -> int | None:
    status = str(episode.get("status") or "").strip().lower()
    for key in ("publish_time", "publish_timestamp", "published_at"):
        value = _coerce_int(episode.get(key))
        if value is not None and value > 0:
            # Older versions created drafts instead of scheduling with status
            # 'future'. Reserve their intended future slots until the operator
            # repairs them, but ignore drafts whose timestamp has passed.
            if status == "draft" and value <= int(datetime.datetime.now().timestamp()):
                return None
            return value
    return None


def _episode_display_title(episode: dict | None) -> str:
    if not episode:
        return "episode"
    number = _episode_number_value(episode)
    title = str(episode.get("title") or "").strip()
    if number and title:
        return f"episode #{number} ({title})"
    if number:
        return f"episode #{number}"
    return title or "episode"


def episode_plan_from_podbean_response(data: dict, local_tz: datetime.tzinfo | None = None) -> PodbeanEpisodePlan:
    """Calculate next episode number and latest published/scheduled anchor."""
    local_tz = local_tz or _local_timezone()
    episodes = data.get("episodes") if isinstance(data, dict) else []
    if not isinstance(episodes, list):
        episodes = []

    numbers = [
        n
        for n in (_episode_number_value(ep) for ep in episodes if isinstance(ep, dict))
        if n is not None
    ]
    count = _coerce_int(data.get("count") if isinstance(data, dict) else None) or 0
    next_episode_number = max(numbers + [count, 0]) + 1

    anchor_episode = None
    anchor_ts = None
    publish_datetimes: list[datetime.datetime] = []
    for episode in episodes:
        if not isinstance(episode, dict):
            continue
        ts = _episode_publish_timestamp(episode)
        if ts is None:
            continue
        publish_datetimes.append(
            datetime.datetime.fromtimestamp(ts, local_tz).replace(microsecond=0)
        )
        if anchor_ts is None or ts > anchor_ts:
            anchor_ts = ts
            anchor_episode = episode
    anchor_datetime = (
        datetime.datetime.fromtimestamp(anchor_ts, local_tz).replace(microsecond=0)
        if anchor_ts is not None
        else None
    )
    return PodbeanEpisodePlan(
        next_episode_number,
        anchor_episode,
        anchor_datetime,
        tuple(publish_datetimes),
    )


def next_available_monday(
    episode_plan: PodbeanEpisodePlan,
    now: datetime.datetime | None = None,
) -> datetime.datetime:
    """Return the first unoccupied Monday at 11:00 UTC after the current queue."""
    utc = datetime.timezone.utc
    now_utc = (now or datetime.datetime.now(utc)).astimezone(utc).replace(microsecond=0)
    anchor_utc = (
        episode_plan.anchor_datetime.astimezone(utc)
        if episode_plan.anchor_datetime is not None
        else None
    )
    threshold = max(now_utc, anchor_utc) if anchor_utc is not None else now_utc
    candidate_date = threshold.date() + datetime.timedelta(
        days=(-threshold.weekday()) % 7
    )
    candidate = datetime.datetime.combine(
        candidate_date,
        datetime.time(hour=11),
        tzinfo=utc,
    )
    if candidate <= threshold:
        candidate += datetime.timedelta(days=7)

    occupied_dates = {
        publish_dt.astimezone(utc).date()
        for publish_dt in episode_plan.publish_datetimes
    }
    while candidate.date() in occupied_dates:
        candidate += datetime.timedelta(days=7)
    return candidate


def prompt_publish_action(
    episode_plan: PodbeanEpisodePlan,
    input_func=input,
    now: datetime.datetime | None = None,
) -> PublishSchedule | None:
    """Choose between the next available Monday and immediate publication."""
    candidate = next_available_monday(episode_plan, now=now)
    print("\nPublishing action — choose what happens when the episode is created:")
    print(f"  [Enter/s] Schedule for {candidate:%A, %d %B %Y at %H:%M UTC}")
    print("  [p]       Publish immediately")
    while True:
        print("> ", end="", flush=True)
        try:
            choice = input_func().strip().lower()
        except EOFError:
            print("\nNo input received; using the default schedule.")
            choice = ""
        if choice in ("", "s", "schedule"):
            return publish_schedule_from_datetime(
                candidate,
                "next available Monday at 11:00 UTC",
            )
        if choice in ("p", "publish", "y", "yes"):
            return None
        print("Please press Enter to schedule, or enter 'p' to publish immediately.")


def _participants_yaml_line(participants: list[str]) -> str:
    """Single YAML line: participants: ["A", "B"] with minimal escaping."""
    inner = ", ".join(f'"{yaml_escape_double_quoted(p)}"' for p in participants)
    return f"participants: [{inner}]"


def find_episode_page(episode_number: int) -> str | None:
    """Existing ``content/episodes/NNN-*.md`` for this episode, if any."""
    matches = sorted(Path(EPISODES_DIR).glob(f"{episode_number:03d}-*.md"))
    return str(matches[0]) if matches else None


def episode_page_path(episode_number: int, title_short: str) -> str:
    """Where ``write_episode_markdown`` writes: an existing page keeps its filename, and so its URL."""
    return find_episode_page(episode_number) or os.path.join(
        EPISODES_DIR, f"{episode_number:03d}-{title_to_url_safe(title_short)}.md"
    )


def _front_matter_blocks(text: str) -> tuple[list[tuple[str, list[str]]], str]:
    """Split a page into ordered (key, lines) front-matter blocks and the body."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("page has no front matter")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    blocks: list[tuple[str, list[str]]] = []
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z_][\w-]*):", line)
        if match or not blocks:
            blocks.append((match.group(1) if match else "", [line]))
        else:
            blocks[-1][1].append(line)
    return blocks, "\n".join(lines[end + 1:])


def _yaml_str(key: str, value: str) -> str:
    return f'{key}: "{yaml_escape_double_quoted(" ".join(str(value).split()))}"'


def _front_matter_scalar(lines: list[str]) -> str:
    """Value of a one-line ``key: "value"`` block as written by ``_yaml_str``."""
    value = lines[0].split(":", 1)[1].strip() if lines and ":" in lines[0] else ""
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = re.sub(r'\\(.)', r"\1", value[1:-1])
    return value


def write_episode_markdown(
    episode_number: int,
    title_short: str,
    description: str,
    article_md: str,
    podbean_id: str,
    youtube_video_id: str,
    participants: list[str] | None = None,
    publish_datetime: datetime.datetime | None = None,
    subtitle: str = "",
    readtime: str = "",
    image: str = "",
    audio_url: str = "",
) -> str:
    """Write the Hugo episode page: teaser, <!--more-->, TOC, players, article.

    An existing page for the episode is rewritten in place: filename, date,
    aliases and the other front matter stay; title, lastmod and the body change.
    An empty ``audio_url`` or ``youtube_video_id`` keeps the page's current value.
    """
    participants = participants if participants is not None else list(DEFAULT_PARTICIPANTS)
    existing = find_episode_page(episode_number)
    blocks: list[tuple[str, list[str]]] = []
    if existing:
        with open(existing, "r", encoding="utf-8") as f:
            blocks, _old_body = _front_matter_blocks(f.read())
        # A resume may lack these (no media_url from Podbean, video only scheduled).
        previous = {key: _front_matter_scalar(lines) for key, lines in blocks}
        audio_url = audio_url or previous.get("audio_url", "")
        youtube_video_id = youtube_video_id or previous.get("youtube_id", "")
    full_title = f"#{episode_number} - {title_short}"
    now_iso = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
    podbean_title = f"DEVSECOPS Talks {full_title}"
    # f-strings: {{ → literal {. Hugo needs {{< not {< — use {{{{ for {{ in output.
    podbean_line = f' {{{{<  podbean {podbean_id} "{podbean_title}"  >}}}} '

    optional = [
        _yaml_str(key, value)
        for key, value in (
            ("description", description),
            ("subtitle", subtitle),
            ("readtime", readtime),
            ("image", image),
            ("youtube_id", youtube_video_id),
            ("audio_url", audio_url),
        )
        if str(value or "").strip()
    ]

    if existing:
        path = existing
        replaced = {"title", "lastmod", "description", "subtitle", "readtime", "image", "youtube_id", "audio_url"}
        front = [_yaml_str("title", full_title)]
        for key, lines in blocks:
            if key in replaced:
                continue
            front.extend(lines)
            if key == "date":
                front.append(f"lastmod: {now_iso}")
        front.extend(optional)
    else:
        path = episode_page_path(episode_number, title_short)
        page_datetime = publish_datetime or datetime.datetime.now().astimezone()
        date_iso = page_datetime.astimezone().replace(microsecond=0).isoformat()
        front = [
            _yaml_str("title", full_title),
            f"date: {date_iso}",
            f"lastmod: {date_iso}",
            f"episode: {episode_number}",
            'author: "DevSecOps Talks"',
            _participants_yaml_line(participants),
            *optional,
            "aliases:",
            f'  - "/episodes/{episode_number:03d}/"',
        ]

    parts = [
        "---",
        *front,
        "---",
        "",
        description,
        "",
        f"[Discuss the episode or ask us anything on LinkedIn]({COMPANY_LINKEDIN_URL})",
        "",
        "<!--more-->",
        "",
        "{{< whats-in-this-post >}}",
        "",
        "<!-- Player -->",
        "",
        podbean_line.rstrip(),
        "",
        "---",
        "",
        "<!-- Video -->",
        "",
    ]
    if youtube_video_id:
        parts.append(f"{{{{< youtube {youtube_video_id} >}}}}")
        parts.append("")
    parts.append(article_md.rstrip())
    parts.append("")

    os.makedirs(EPISODES_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return path


REQUIRED_TOOLS = ("ffmpeg", "ffprobe", "claude", "codex", "grok")


def require_tools(draft_only: bool = False, which=shutil.which) -> None:
    """Stop before any work when a CLI or file a later step needs is missing.

    Each would otherwise stop the run only when its step comes up, after minutes
    of transcription and questions. Grok only drafts the announcement.
    """
    missing = [t for t in REQUIRED_TOOLS if not which(t) and not (draft_only and t == "grok")]
    if missing:
        raise PipelineStop(
            f"required CLI(s) not on PATH: {', '.join(missing)}. See Prerequisites in tools/README.md."
        )
    try:
        resolve_cli()
    except RuntimeError as e:
        raise PipelineStop(str(e)) from e
    try:
        voice_match.load_host_voices()
    except voice_match.VoicePrintError as e:
        raise PipelineStop(str(e), checkpoint=voice_match.HOST_VOICES_PATH) from e


TRANSCRIPT_SIDECAR_EXTENSIONS = (".vtt", ".txt")

CHECKPOINT_INPUTS_SUFFIX = "-inputs.json"
GUEST_LABELS_SUFFIX = "-guest-labels.json"
# Local steps in pipeline order with the out/ files each writes. When a step's
# inputs change, its files and every later step's go, so nothing outlives what
# it was built from. Upload markers and the Buffer ledger are remote state: never here.
CHECKPOINT_STEPS = (
    ("transcription", (
        "-asr.json", "-diarization.json", "-turns.json", "-local.txt", "-speakers.json", "-guest-labels.json",
    )),
    ("guests", ("-guests.json",)),
    ("transcript", (
        "-turns-corrected.json",
        ".txt",
        "-transcript-rewrite-*.json",
        "-transcript-review-*.md",
        "-transcript-review-limit.txt",
    )),
    ("chapters", ("-chapters-generated.txt",)),
    ("title", ("-title.txt", "-description.txt")),
    ("article", ("-draft.md", "-draft-v*.md", "-review-*.md", "-article.md")),
    ("metadata", ("-metadata.json", "-youtube-description.txt")),
)


def inputs_fingerprint(*inputs) -> str:
    """A short hash of JSON-serialisable step inputs."""
    source = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def refresh_checkpoints(out_base: str, step: str, *inputs) -> list[str]:
    """Record what ``step`` is built from, first discarding it and every later step if that changed.

    Called before the step runs, so its partial files (review rounds) resume.
    A step with no recorded entry counts as changed. Returns the removed basenames.
    """
    fingerprint = inputs_fingerprint(*inputs)
    record_file = out_base + CHECKPOINT_INPUTS_SUFFIX
    recorded: dict = {}
    if os.path.exists(record_file):
        try:
            with open(record_file, "r", encoding="utf-8") as f:
                recorded = json.load(f)
            if not isinstance(recorded, dict):
                raise ValueError("not a JSON object")
        except (OSError, ValueError) as e:
            raise PipelineStop(
                f"cannot read the step input record ({e}); delete it to rebuild every local step",
                checkpoint=record_file,
            ) from e
    if recorded.get(step) == fingerprint:
        return []

    names = [name for name, _ in CHECKPOINT_STEPS]
    later = CHECKPOINT_STEPS[names.index(step):]
    removed = []
    for name, suffixes in later:
        recorded.pop(name, None)
        for suffix in suffixes:
            for path in sorted(glob.glob(glob.escape(out_base) + suffix)):
                os.remove(path)
                removed.append(os.path.basename(path))
    recorded[step] = fingerprint
    with open(record_file, "w", encoding="utf-8") as f:
        json.dump(recorded, f, indent=2)
        f.write("\n")
    if removed:
        print(f"✓ {step} inputs changed; discarded: {', '.join(removed)}")
    return removed


def prompt_speaker_count(input_func=input) -> int | None:
    """Ask how many distinct voices are in the episode, to pin diarization.

    Pinning stops the diarizer inventing a phantom speaker from crosstalk, but
    pinning too low merges two real people irrecoverably. So there is no numeric
    default: Enter (and EOF) means auto-detect, whose failure mode is a visible
    extra speaker. ``EPISODE_SPEAKERS`` (a positive number, or ``auto``) skips the prompt.
    """
    env = os.environ.get("EPISODE_SPEAKERS", "").strip()
    if env:
        if env.lower() == "auto":
            return None
        if env.isdigit() and int(env) > 0:
            return int(env)
        print(f"⚠ Ignoring EPISODE_SPEAKERS={env!r}; expected a positive number or 'auto'.")

    while True:
        print("\nHow many distinct voices are in this episode?")
        print("Count everyone actually audible — hosts, guests, and any intro or clip voice.")
        print("Type a number to pin it, or press Enter to let the diarizer decide: ", end="", flush=True)
        try:
            raw = input_func().strip()
        except EOFError:
            print("\n(no input available — using auto-detect)")
            return None
        if not raw or raw.lower() == "auto":
            return None
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print(f"⚠ '{raw}' is not a valid speaker count.")


def load_turns(out_base: str) -> list[dict]:
    """The machine turns from ``-turns.json``; every later step is built from them."""
    turns_file = f"{out_base}-turns.json"
    try:
        with open(turns_file, "r", encoding="utf-8") as f:
            turns = json.load(f)
    except (OSError, ValueError) as e:
        raise PipelineStop(f"cannot read the transcript turns ({e})", checkpoint=turns_file) from e
    if not isinstance(turns, list) or not turns:
        raise PipelineStop("the transcript has no turns", checkpoint=turns_file)
    return turns


def load_or_transcribe(audio_path: str, out_base: str, skip_transcription: bool = False,
                       verbose: bool = False, input_func=input) -> list[dict]:
    """Transcribe and diarize locally unless this recording's turns are saved; returns the turns."""
    turns_file = f"{out_base}-turns.json"
    if skip_transcription:
        if not os.path.isfile(turns_file):
            raise PipelineStop("--skip-transcription, but there is no saved transcript", checkpoint=turns_file)
        print(f"✓ Using saved transcript turns {turns_file}")
        return load_turns(out_base)

    refresh_checkpoints(
        out_base, "transcription", audio_source_identity(audio_path)["sha256"], voice_match.fluidaudio_pin()
    )
    if os.path.isfile(turns_file):
        print(f"✓ Loaded transcript turns from {turns_file}")
        return load_turns(out_base)
    num_speakers = prompt_speaker_count(input_func=input_func)
    try:
        machine_transcript = transcribe_local(audio_path, out_base, num_speakers=num_speakers, verbose=verbose)
    except RuntimeError as e:
        raise PipelineStop(f"local transcription failed: {e}", checkpoint=turns_file) from e
    with open(f"{out_base}-local.txt", "w", encoding="utf-8") as f:
        f.write(machine_transcript)
    print(f"✓ Transcript turns saved to {turns_file}")
    return load_turns(out_base)


def named_machine_transcript(turns: list[dict], speaker_names: dict[str, str]) -> str:
    """The machine turns as ``Name: text`` lines, ``[B]: text`` for a label not named yet."""
    lines = []
    for turn in turns:
        label = str(turn.get("speaker") or "")
        name = speaker_names.get(label) or f"[{label}]"
        lines.append(f"{name}: {' '.join(str(turn.get('text') or '').split())}")
    return "\n".join(lines)


def confirm_speakers(audio_path: str, out_base: str, input_func=input) -> tuple[dict[str, str], list[dict]]:
    """Hosts named by voice print and confirmed by the operator; returns them and the current turns."""
    try:
        host_names, _rediarized = voice_match.confirm_speakers(audio_path, out_base, input_func=input_func)
    except voice_match.SpeakerConfirmationError as e:
        raise PipelineStop(str(e), checkpoint=e.checkpoint or "") from e
    # A re-diarization rewrote -turns.json; later steps read the new turns.
    return host_names, load_turns(out_base)


def _label_minutes(turns: list[dict]) -> dict[str, float]:
    minutes: dict[str, float] = {}
    for turn in turns:
        label = str(turn.get("speaker") or "")
        span = float(turn.get("end") or 0) - float(turn.get("start") or 0)
        minutes[label] = minutes.get(label, 0.0) + max(span, 0.0) / 60
    return minutes


def _label_sample(turns: list[dict], label: str) -> str:
    texts = [str(t.get("text") or "") for t in turns if str(t.get("speaker") or "") == label]
    longest = max(texts, key=len, default="")
    return " ".join(longest.split())[:160]


def _guest_answer(raw: str) -> dict:
    """``Jane Doe, CTO at Acme`` → name ``Jane Doe``, hint ``CTO at Acme`` for the research."""
    name, hint = _split_operator_guest_chunk(raw)
    return {"name": " ".join(name.split()), "hint": hint}


def people_from_answers(answers: dict[str, str]) -> list[dict]:
    """Distinct people in label order; the same name typed for two labels is one person."""
    people: dict[str, dict] = {}
    for label, raw in answers.items():
        answer = _guest_answer(raw)
        person = people.setdefault(answer["name"].casefold(), {"name": answer["name"], "hint": "", "labels": []})
        person["labels"].append(label)
        if answer["hint"] and answer["hint"] not in person["hint"]:
            person["hint"] = "; ".join(x for x in (person["hint"], answer["hint"]) if x)
    return list(people.values())


def ask_guest_labels(out_base: str, turns: list[dict], labels: list[str], input_func=input) -> dict[str, str]:
    """The operator's answer for each voice that is not a host."""
    minutes = _label_minutes(turns)
    print("\nName each voice that is not a host:")
    answers: dict[str, str] = {}
    for label in labels:
        print(f"\n[{label}] {minutes.get(label, 0):.1f} min, e.g. \"{_label_sample(turns, label)}\"")
        while True:
            print(
                f"Who is {label}? Full name, plus anything that helps find them (company, role, a link): ",
                end="",
                flush=True,
            )
            try:
                raw = " ".join(input_func().split())
            except EOFError:
                raise PipelineStop(
                    f"label {label} needs a name and no answer was given; re-run in a terminal",
                    checkpoint=out_base + GUEST_LABELS_SUFFIX,
                ) from None
            if raw and _guest_answer(raw)["name"]:
                answers[label] = raw
                break
            print("A name is required.")
    return answers


def _saved_guest_answers(labels_file: str, labels: list[str], turns_key: str) -> dict[str, str] | None:
    try:
        with open(labels_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("labels") == labels and saved.get("turns") == turns_key:
            answers = saved["answers"]
            if isinstance(answers, dict) and list(answers) == labels:
                return {str(k): str(v) for k, v in answers.items()}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def _handle_lines(guest: dict) -> str:
    linkedin = " ".join(x for x in (guest.get("linkedin_name"), guest.get("linkedin_url")) if x)
    x_handle = f"@{guest['x_handle']}" if guest.get("x_handle") else ""
    threads = f"@{guest['threads_handle']}" if guest.get("threads_handle") else ""
    if not (linkedin or x_handle or threads):
        return "not found — credited in plain text"
    return "  ".join(
        f"{network}: {value or 'not found'}"
        for network, value in (("LinkedIn", linkedin), ("X", x_handle), ("Threads", threads))
    )


def confirm_guests(people: list[dict], guest_context: dict, transcript: str, guidance: str,
                   raw_notes: str, verbose: bool = False, input_func=input) -> dict:
    """Show what research found; a correction looks that guest up again."""
    while True:
        print("\nGuests:")
        for i, (person, guest) in enumerate(zip(people, guest_context["guests"]), 1):
            detail = ", ".join(x for x in (guest.get("role"), guest.get("company")) if x)
            print(f"  {i}. {guest['full_name']} ({', '.join(person['labels'])})" + (f" — {detail}" if detail else ""))
            print(f"     {_handle_lines(guest)}")
        print("Enter accepts; or type a guest number and a correction to look them up again: ", end="", flush=True)
        try:
            raw = input_func().strip()
        except EOFError:
            print("\n(no input available — accepting the guests)")
            return guest_context
        if not raw:
            return guest_context
        number, _, correction = raw.partition(" ")
        if not (number.isdigit() and 1 <= int(number) <= len(people) and correction.strip()):
            print("⚠ Type a guest number, a space, then the correction (company, role, a link).")
            continue
        index = int(number) - 1
        person = people[index]
        person["hint"] = "; ".join(x for x in (person["hint"], correction.strip()) if x)
        redone = research_guests([person], transcript, guidance, raw_notes, verbose)
        guests = list(guest_context["guests"])
        guests[index] = redone["guests"][0]
        guest_context = {**guest_context, "guests": guests}


def identify_guests(out_base: str, turns: list[dict], host_names: dict[str, str], guidance: str,
                    raw_notes: str, verbose: bool = False, input_func=input) -> tuple[dict, dict[str, str]]:
    """Step 4: the operator names every voice that is not a host; research only looks them up.

    Returns the guest context and every label's name. A host name typed here
    names that label as the host.
    """
    labels = list(dict.fromkeys(str(t.get("speaker") or "") for t in turns))
    others = [label for label in labels if label not in host_names]
    labels_file = out_base + GUEST_LABELS_SUFFIX
    guests_file = f"{out_base}-guests.json"
    turns_key = inputs_fingerprint(turns)

    answers = None
    saved = _saved_guest_answers(labels_file, others, turns_key) if others else None
    if saved is not None:
        known = {}
        try:
            known = {g["full_name"].casefold(): g for g in load_guest_context(guests_file)["guests"]}
        except (OSError, ValueError):
            pass
        summary = []
        for label, raw in saved.items():
            name = _guest_answer(raw)["name"]
            company = (known.get(name.casefold()) or {}).get("company")
            summary.append(f"{label}={name}" + (f" ({company})" if company else ""))
        print(f"\nFound saved guests: {', '.join(summary)}. Enter reuses, 'new' asks again: ", end="", flush=True)
        try:
            reuse = input_func().strip().lower() != "new"
        except EOFError:
            reuse = True
        if reuse:
            answers = saved
    if answers is None:
        answers = ask_guest_labels(out_base, turns, others, input_func) if others else {}
        with open(labels_file, "w", encoding="utf-8") as f:
            json.dump({"labels": others, "turns": turns_key, "answers": answers}, f, indent=2, ensure_ascii=False)
            f.write("\n")

    speaker_names = dict(host_names)
    guest_answers = {}
    for label, raw in answers.items():
        host = voice_match.canonical_host(_guest_answer(raw)["name"])
        if host:
            speaker_names[label] = host
        else:
            guest_answers[label] = raw
    people = people_from_answers(guest_answers)
    for person in people:
        for label in person["labels"]:
            speaker_names[label] = person["name"]
    hosts_present = voice_match.hosts_present(speaker_names)

    refresh_checkpoints(out_base, "guests", answers, host_names, raw_notes)
    guest_context = None
    if os.path.exists(guests_file):
        try:
            saved_context = load_guest_context(guests_file)
            if guest_full_names(saved_context) == [p["name"] for p in people]:
                guest_context = saved_context
        except (OSError, ValueError):
            pass
    if guest_context is None:
        guest_context = operator_guest_context([])
        if people:
            transcript = named_machine_transcript(turns, speaker_names)
            guest_context = research_guests(people, transcript, guidance, raw_notes, verbose)
            guest_context = confirm_guests(people, guest_context, transcript, guidance, raw_notes, verbose, input_func)
    guest_context = {**guest_context, "hosts_present": hosts_present, "andrey_present": AUTHOR_HOST in hosts_present}
    save_guest_context(guests_file, guest_context)
    print(f"✓ Guests saved to {guests_file}")
    return guest_context, speaker_names


def parse_vtt(vtt_path: str) -> str:
    """Parse a WebVTT file into a plain text transcript."""
    lines = []
    with open(vtt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
                continue
            line = re.sub(r"<[\d:.]+>", "", line).strip()
            if line:
                lines.append(line)
    return "\n".join(lines)


def _sidecar_transcripts_in(directory: str, stems: list[str]) -> list[str]:
    """Return ``{stem}*.vtt|txt`` files in ``directory`` for any of ``stems``."""
    if not os.path.isdir(directory):
        return []
    return sorted(
        str(entry)
        for entry in Path(directory).iterdir()
        if entry.is_file()
        and entry.suffix.lower() in TRANSCRIPT_SIDECAR_EXTENSIONS
        and any(entry.name.startswith(stem) for stem in stems)
    )


def select_provided_transcript(audio_path: str, input_func=input) -> str | None:
    """Pick the sidecar transcript next to the MP3, asking when there are several."""
    p = Path(audio_path).resolve()
    candidates = _sidecar_transcripts_in(str(p.parent), [p.stem])
    if len(candidates) <= 1:
        return candidates[0] if candidates else None

    print("\nMultiple provided transcripts found:")
    for idx, path in enumerate(candidates, 1):
        print(f"  {idx}. {os.path.basename(path)}")
    while True:
        print(f"Choose one [1-{len(candidates)}]: ", end="", flush=True)
        try:
            choice = input_func().strip()
        except EOFError:
            choice = ""
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        print("Invalid choice, try again.")


def read_provided_transcript(path: str) -> str:
    """Read a VTT or text transcript into plain text."""
    if path.lower().endswith(".vtt"):
        return parse_vtt(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_reference_text(transcript_arg: str | None, audio_path: str, input_func=input) -> str:
    """``--transcript`` or a Riverside sidecar, given to the correction as spelling reference only."""
    path = transcript_arg or select_provided_transcript(audio_path, input_func=input_func)
    if not path:
        return ""
    try:
        text = read_provided_transcript(path)
    except OSError as e:
        raise PipelineStop(f"cannot read the reference transcript {path}: {e}") from e
    print(f"✓ Reference transcript for the correction: {os.path.basename(path)}")
    return text


# get podbean auth token
# curl -u YOUR_CLIENT_ID:YOUR_CLIENT_SECRET https://api.podbean.com/v1/oauth/token -X POST -d 'grant_type=client_credentials'
def get_podbean_auth_token(client_id, client_secret, url="https://api.podbean.com/v1/oauth/token"):
    response = None
    try:
        response = requests.post(
            url,
            data={"grant_type": "client_credentials", "expires_inoptional": 180},
            auth=(client_id, client_secret))
        access_token = response.json()['access_token']
        return access_token
    except Exception as e:
        extra = response.text if response is not None else ""
        print(f'An error occurred during getting podbean auth token: {str(e)}, response: {extra}')
        raise

# authorize file upload to podbean (get s3 presigned link)
# curl https://api.podbean.com/v1/files/uploadAuthorize -G -d 'access_token=YOUR_ACCESS_TOKEN' -d 'filename=abc.mp3' -d 'filesize=1291021' -d 'content_type=audio/mpeg'
def get_podbean_upload_link(access_token, filename, filesize, content_type="mp3", url="https://api.podbean.com/v1/files/uploadAuthorize"):
    response = requests.get(
        url,
        params={"access_token": access_token, "filename": filename, "filesize": filesize, "content_type": content_type})
    return response.json()

# upload file to podbean
# curl -v -H "Content-Type: image/jpeg" -T /your/path/file.ext "PRESIGNED_URL"
def upload_file_to_podbean(url, filepath):
    with open(filepath, "rb") as f:
        response = requests.put(
            url,
            headers={"Content-Type": mimetypes.guess_type(filepath)[0]},
            data=f,
        )
    response.raise_for_status()
    return response

# convert title into url safe string
def title_to_url_safe(title):
    return re.sub(r"[^0-9a-zA-Z]+", "-", title).lower()

# get episodes from Podbean; used for next number and schedule anchor
# curl https://api.podbean.com/v1/episodes -G -d 'access_token=YOUR_ACCESS_TOKEN' -d 'offset=0' -d 'limit=10'
def get_podbean_episodes(access_token, url="https://api.podbean.com/v1/episodes"):
    offset = 0
    limit = 100
    episodes: list[dict] = []
    total_count = 0
    while True:
        response = requests.get(
            url,
            params={"access_token": access_token, "offset": offset, "limit": limit},
        )
        data = response.json()
        page_episodes = data.get("episodes") or []
        if isinstance(page_episodes, list):
            episodes.extend(ep for ep in page_episodes if isinstance(ep, dict))
        total_count = _coerce_int(data.get("count")) or max(total_count, len(episodes))
        if not data.get("has_more"):
            break
        offset += limit
        if total_count and offset >= total_count:
            break
    return {
        "episodes": episodes,
        "count": max(total_count, len(episodes)),
        "offset": 0,
        "limit": limit,
        "has_more": False,
    }


def get_last_episode_number(access_token, url="https://api.podbean.com/v1/episodes"):
    """Backward-compatible helper: return highest known Podbean episode number/count."""
    return episode_plan_from_podbean_response(get_podbean_episodes(access_token, url)).next_episode_number - 1

# create new podbean episode
# curl https://api.podbean.com/v1/episodes -X POST -d access_token=YOUR_ACCESS_TOKEN -d title="Good day" \
# -d content="Time you <b>enjoy</b> wasting, was not wasted." -d status=publish -d type=public \
# -d media_key=audio.mp3 -d logo_key=logo.jpg -d transcripts_key=transcripts.srt -d season_number=1
# -d episode_number=1 -d apple_episode_type=full -d publish_timestamp=1667850511 -d content_explicit=clean
def create_podbean_episode(
        access_token, title, content, episode_number, media_key=None, status="draft", type="public",
        publish_timestamp=None, url="https://api.podbean.com/v1/episodes"):
    data = {"access_token": access_token, "title": title,
            "content": content, "status": status, "type": type,
            "media_key": media_key, "episode_number": episode_number}
    if publish_timestamp is not None:
        data["publish_timestamp"] = str(int(publish_timestamp))
    response = requests.post(
        url,
        data=data
        )
    return response.json()


def update_podbean_episode(access_token, episode_id, content, title, status="publish", type="public"):
    """Update an existing Podbean episode's content/description."""
    url = f"https://api.podbean.com/v1/episodes/{episode_id}"
    response = requests.post(url, data={
        "access_token": access_token,
        "content": content,
        "title": title,
        "status": status,
        "type": type,
    })
    return response.json()


def podbean_creation_status(publish_schedule: PublishSchedule | None) -> str:
    """Podbean requires status 'future' to queue a scheduled publication."""
    return "future" if publish_schedule is not None else "publish"


def validate_podbean_schedule(response: dict, schedule: PublishSchedule) -> None:
    """Do not continue publishing other surfaces unless Podbean queued audio."""
    episode = response.get("episode", response)
    status = str(episode.get("status") or "").strip().lower()
    if status != "future":
        raise ValueError(
            f"Podbean did not confirm scheduled publication (status: {status or 'missing'}; "
            "expected: future). Check the episode in the Podbean dashboard before rerunning."
        )
    if _episode_publish_timestamp(episode) != schedule.podbean_timestamp:
        raise ValueError(
            "Podbean returned a different or missing publication time. "
            "Check the episode schedule in the Podbean dashboard before rerunning."
        )


def parse_args():
    p = argparse.ArgumentParser(
        description="DevSecOps Talks: transcribe, Claude+Codex article loop, Podbean, YouTube"
    )
    p.add_argument("-f", "--filename", help="Path to mp3 (default: scan tools/raw/)", default=None)
    p.add_argument("-a", "--audio", help="Alias for --filename", default=None)
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    p.add_argument(
        "-s", "--scan", action="store_true",
        help="Process every .mp3 in tools/raw/",
    )
    p.add_argument("--skip-transcription", action="store_true", help="Use existing transcript in out/")
    p.add_argument("-t", "--transcript", help="External transcript file path")
    p.add_argument("--title", default=None, help="Episode title (skip Codex title picker)")
    p.add_argument("--description", default=None, help="Short teaser (skip Codex description picker)")
    p.add_argument("--guidance", default=None, help="Editorial angle for drafting/review")
    p.add_argument("--draft-only", action="store_true", help="Stop after article checkpoints in out/")
    p.add_argument(
        "--episode-number",
        type=int,
        default=None,
        help="Resume an existing numbered episode instead of choosing the next Podbean number",
    )
    p.add_argument("--youtube", default="", help="Embed URL — skip upload-post upload")
    p.add_argument("--video", default=None, help="Path to mp4/mov/mkv (default: same stem as audio in raw/)")
    p.add_argument(
        "--youtube-video-url", default="",
        help="Public HTTPS URL for upload-post to fetch (large files)",
    )
    p.add_argument("--youtube-via-r2", action="store_true", help="Always stage local video on R2 before upload-post")
    p.add_argument("--youtube-no-r2-staging", action="store_true", help="Never use R2 staging for video")
    p.add_argument("--skip-youtube-upload", action="store_true", help="Do not upload video even if present")
    p.add_argument(
        "--participants",
        default=None,
        help='Comma-separated names for front matter (default: Paulina, Mattias, Andrey). Example: --participants "Paulina,Mattias,Andrey,Guest Name"',
    )
    return p.parse_args()


def _collect_audio_paths(args) -> list[str]:
    """Resolve which mp3 file(s) to process."""
    explicit = args.filename or args.audio
    if explicit:
        if not explicit.endswith(".mp3"):
            print(f"Expected .mp3 file, got: {explicit}")
            sys.exit(1)
        return [os.path.abspath(explicit)]
    if args.scan:
        found = find_mp3_files_in_raw()
        if not found:
            print(f"No .mp3 files in {RAW_DIR}/")
            sys.exit(1)
        return found
    found = find_mp3_files_in_raw()
    if len(found) == 1:
        return found
    if not found:
        print(f"No .mp3 in {RAW_DIR}/ — add one or pass -f /path/to/file.mp3")
        sys.exit(1)
    print("Multiple .mp3 files in raw/; use --scan to process all or -f to pick one:")
    for f in found:
        print(f"  {f}")
    sys.exit(1)


def _parse_participants_arg(arg: str | None) -> list[str]:
    if not arg or not str(arg).strip():
        return list(DEFAULT_PARTICIPANTS)
    out = [p.strip() for p in str(arg).split(",") if p.strip()]
    return out if out else list(DEFAULT_PARTICIPANTS)


def _split_operator_guest_chunk(chunk: str) -> tuple[str, str]:
    """Split loose operator input into a likely full name and details."""
    chunk = chunk.strip()
    name = chunk
    details = ""
    for sep in (" - ", " -- ", " – ", " — "):
        if sep in chunk:
            name, details = chunk.split(sep, 1)
            return name.strip(), details.strip()
    if "," in chunk:
        name, details = chunk.split(",", 1)
        return name.strip(), details.strip()

    tokens = chunk.split()
    if len(tokens) < 3:
        return name, details
    for idx in range(2, len(tokens)):
        token = tokens[idx].strip(".,:;()[]{}").casefold()
        if token in GUEST_ROLE_STARTERS:
            return " ".join(tokens[:idx]).strip(), " ".join(tokens[idx:]).strip()
    return name, details


def _text_includes_guest_names(text: str, guest_context: dict) -> bool:
    required = guest_full_names(guest_context)
    if not required:
        return True
    folded = text.casefold()
    return all(name.casefold() in folded for name in required)


def _participants_for_episode(arg: str | None, guest_context: dict) -> list[str]:
    participants = _parse_participants_arg(arg)
    if arg and str(arg).strip():
        return participants

    seen = {p.casefold() for p in participants}
    for guest_name in guest_full_names(guest_context):
        key = guest_name.casefold()
        if key not in seen:
            participants.append(guest_name)
            seen.add(key)
    return participants


def _load_or_prompt_guidance(guidance_file: str, guidance: str | None) -> str:
    if guidance is None:
        if os.path.exists(guidance_file):
            with open(guidance_file, "r", encoding="utf-8") as f:
                saved_g = f.read().strip()
            print(f'\nFound saved editorial guidance:\n  "{saved_g[:120]}{"..." if len(saved_g) > 120 else ""}"')
            print("Press Enter to reuse, or type new guidance: ", end="", flush=True)
            user_input = input().strip()
            guidance = user_input if user_input else saved_g
        else:
            print("\nEditorial guidance for drafting? (angle, focus, or Enter to skip)")
            print("> ", end="", flush=True)
            guidance = input().strip()
    if guidance:
        with open(guidance_file, "w", encoding="utf-8") as f:
            f.write(guidance)
        print(f"✓ Guidance saved to {guidance_file}")
    return guidance


def _load_or_pick(kind: str, path: str, given: str | None, guest_context: dict, pick) -> str:
    """The title or teaser: ``given`` (CLI), else the saved pick, else a new Codex pick.

    Each must name every guest in full; a saved one that does not is picked again.
    """
    guests = ", ".join(guest_full_names(guest_context))
    value = (given or "").strip() or None
    if value and not _text_includes_guest_names(value, guest_context):
        raise PipelineStop(f"--{kind} must include guest full name(s): {guests}")
    if not value and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            saved = f.read().strip()
        if not _text_includes_guest_names(saved, guest_context):
            print(f"\nSaved {kind} does not include guest full name(s); picking again.")
        else:
            print(f'\nFound saved {kind}: "{saved}"')
            print("Press Enter to reuse, or type 'new' to pick again: ", end="", flush=True)
            if input().strip().lower() != "new":
                value = saved
    while not value:
        picked = pick()
        if _text_includes_guest_names(picked, guest_context):
            value = picked
        else:
            print(f"Picked {kind} is missing guest full name(s): {guests}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(value)
    return value


def youtube_upload_done(out_base: str, args) -> bool:
    """The video needs no upload: already uploaded or scheduled, given, or opted out."""
    for marker in (f"{out_base}-youtube-url.txt", f"{out_base}-youtube-scheduled.txt"):
        if os.path.isfile(marker):
            with open(marker, "r", encoding="utf-8") as f:
                if f.read().strip():
                    return True
    return bool((args.youtube or "").strip()) or args.skip_youtube_upload


def resolve_video_source(args, audio_path: str) -> str | None:
    """A video URL for upload-post, or the local companion video; None when there is neither."""
    override = (args.youtube_video_url or os.environ.get("UPLOAD_POST_VIDEO_URL") or "").strip()
    if override:
        return override
    video = args.video or find_companion_video(audio_path)
    return video if video and os.path.isfile(video) else None


def announcement_expected(out_base: str, existing_episode: dict | None) -> bool:
    """Buffer runs for an episode this run creates on Podbean, or one an earlier run created."""
    return existing_episode is None or load_announcement_eligibility(out_base) is not None


def require_publishing_prerequisites(args, audio_path: str, out_base: str, existing_episode: dict | None) -> None:
    """Stop before the questions when an upload or post that will run cannot.

    A finished upload (its marker) needs neither its source nor its keys.
    """
    problems: list[str] = []
    if not youtube_upload_done(out_base, args):
        if not (os.environ.get("UPLOAD_POST_API_KEY") and os.environ.get("UPLOAD_POST_USER")):
            problems.append("UPLOAD_POST_API_KEY / UPLOAD_POST_USER are not set (YouTube upload)")
        video = resolve_video_source(args, audio_path)
        if not video:
            problems.append(
                f"no video for {os.path.basename(audio_path)}: put the .mp4/.mov/.mkv next to it, "
                "or pass --video, --youtube-video-url, --youtube URL or --skip-youtube-upload"
            )
        elif (
            not video.lower().startswith(("http://", "https://"))
            and wants_r2_staging_for_local_video(video, args)
            and not r2_public_uploads_configured()
        ):
            problems.append(
                "this video needs R2 staging but R2 is not configured; set the R2_* variables "
                "or pass --youtube-no-r2-staging"
            )
    try:
        check_cover_lifecycle(require_cover_client())
    except R2CoverError as e:
        problems.append(str(e))
    if announcement_expected(out_base, existing_episode):
        try:
            preflight_buffer()
        except AnnouncementStop as e:
            problems.append(str(e))
    if problems:
        raise PipelineStop("cannot publish this episode:\n  - " + "\n  - ".join(problems))


def resolve_episode(audio_path: str, args, podbean_episode_data: dict) -> tuple[int, dict | None, PodbeanEpisodePlan]:
    """The episode number this recording publishes as, and its Podbean episode if one exists."""
    episode_plan = episode_plan_from_podbean_response(podbean_episode_data)
    if args.episode_number is not None and args.episode_number < 1:
        raise PipelineStop("--episode-number must be greater than zero")
    audio_resume = (
        None
        if args.episode_number is not None or args.scan
        else confirm_resume_for_audio(audio_path, episode_plan.next_episode_number)
    )
    inferred_resume = (
        None
        if args.episode_number is not None or args.scan or audio_resume is not None
        else infer_resume_episode_number(episode_plan.next_episode_number)
    )
    episode_number = (
        args.episode_number or audio_resume or inferred_resume or episode_plan.next_episode_number
    )
    if args.episode_number is not None or audio_resume is not None:
        print(f"✓ Resuming episode number: {episode_number}")
    elif inferred_resume is not None:
        print(f"✓ Automatically resuming unfinished episode #{episode_number}")
    else:
        print(f"✓ Next episode number (from Podbean episodes): {episode_number}")
    existing_episode = find_podbean_episode(podbean_episode_data, episode_number)
    if existing_episode and not args.draft_only and (
        str(existing_episode.get("status") or "").strip().lower() == "draft"
    ):
        raise PipelineStop(
            f"Podbean episode #{episode_number} is still a draft; a future timestamp alone does "
            "not schedule publication. Schedule it or publish it in the Podbean dashboard, then "
            f"re-run with --episode-number {episode_number} to resume."
        )
    return episode_number, existing_episode, episode_plan


def publish_to_podbean(
    auth_token: str,
    audio_path: str,
    out_base: str,
    episode_number: int,
    title: str,
    show_notes: str,
    publish_schedule: PublishSchedule | None,
    release_at: datetime.datetime,
    verbose: bool = False,
) -> dict:
    """Upload the audio and create the episode; returns Podbean's episode object.

    ``release_at`` is the release time the announcement was approved for, recorded as is."""
    podbean_upload_checkpoint = f"{out_base}-podbean-upload.json"
    file_size = os.path.getsize(audio_path)
    episode_file_name_mp3 = f"{episode_number:03d}-{title_to_url_safe(title)}.mp3"
    media_key = ""
    if os.path.isfile(podbean_upload_checkpoint):
        try:
            with open(podbean_upload_checkpoint, "r", encoding="utf-8") as f:
                saved_upload = json.load(f)
            if saved_upload.get("filename") == episode_file_name_mp3 and saved_upload.get("filesize") == file_size:
                media_key = str(saved_upload.get("media_key") or "")
        except (OSError, ValueError, TypeError):
            media_key = ""
    if media_key:
        print(f"✓ Reusing previously uploaded Podbean audio: {episode_file_name_mp3}")
    else:
        print("\nUploading audio to Podbean...")
        presigned_url_response = get_podbean_upload_link(auth_token, episode_file_name_mp3, file_size)
        try:
            presigned_url = presigned_url_response["presigned_url"]
            media_key = presigned_url_response["file_key"]
        except (KeyError, TypeError) as e:
            raise PipelineStop(f"Podbean did not authorize the audio upload: {presigned_url_response!r:.500}") from e
        print(f"Uploading {episode_file_name_mp3} ({file_size / (1024*1024):.1f} MB)...")
        upload_file_to_podbean(presigned_url, audio_path)
        with open(podbean_upload_checkpoint, "w", encoding="utf-8") as f:
            json.dump({"filename": episode_file_name_mp3, "filesize": file_size, "media_key": media_key}, f)
        print("✓ Audio uploaded and checkpointed")

    create_episode_response = create_podbean_episode(
        auth_token,
        f"#{episode_number} - {title}",
        show_notes,
        episode_number,
        media_key=media_key,
        status=podbean_creation_status(publish_schedule),
        publish_timestamp=publish_schedule.podbean_timestamp if publish_schedule else None,
    )
    if verbose:
        print(create_episode_response)
    try:
        podbean_player_id(create_episode_response)
        if publish_schedule:
            validate_podbean_schedule(create_episode_response, publish_schedule)
    except ValueError as e:
        raise PipelineStop(str(e), checkpoint=podbean_upload_checkpoint) from e
    # Only episodes released by this pipeline are announced; regenerated old pages never are.
    record_announcement_eligibility(out_base, release_at)
    if os.path.isfile(podbean_upload_checkpoint):
        os.remove(podbean_upload_checkpoint)
    return create_episode_response.get("episode") or create_episode_response


def publish_to_youtube(
    args,
    audio_path: str,
    out_base: str,
    episode_number: int,
    youtube_title: str,
    youtube_description_text: str,
    publish_schedule: PublishSchedule | None,
) -> str:
    """The YouTube embed URL, uploading the video unless a marker or ``--youtube`` covers it.

    "" when the upload is only scheduled or the operator opted out.
    """
    youtube_url_file = f"{out_base}-youtube-url.txt"
    youtube_scheduled_file = f"{out_base}-youtube-scheduled.txt"
    youtube_staging_marker = f"{out_base}-r2-youtube-staging.txt"

    def stop(message: str) -> PipelineStop:
        return PipelineStop(message, checkpoint=youtube_url_file)

    youtube_embed_url = (args.youtube or "").strip()
    youtube_scheduled = False
    if not youtube_embed_url and os.path.exists(youtube_url_file):
        with open(youtube_url_file, "r", encoding="utf-8") as f:
            youtube_embed_url = f.read().strip()
        if youtube_embed_url:
            print(f"✓ Loaded YouTube embed URL from {youtube_url_file}")
    if not youtube_embed_url and os.path.exists(youtube_scheduled_file):
        with open(youtube_scheduled_file, "r", encoding="utf-8") as f:
            marker = f.read().strip()
        if marker:
            youtube_scheduled = True
            print(f"✓ Loaded scheduled YouTube upload marker from {youtube_scheduled_file}")

    if youtube_embed_url and os.path.isfile(youtube_staging_marker):
        print(f"✓ YouTube embed present; removing R2 staging marker and object ({youtube_staging_marker})")
        remove_r2_youtube_staging_marker(youtube_staging_marker)
    if youtube_embed_url and os.path.isfile(youtube_scheduled_file):
        os.unlink(youtube_scheduled_file)
    if youtube_embed_url or youtube_scheduled:
        return youtube_embed_url
    if args.skip_youtube_upload:
        print("\n--skip-youtube-upload: no video on this page.")
        return ""

    # require_publishing_prerequisites checked these before the questions.
    video_source = resolve_video_source(args, audio_path)
    if not video_source:
        raise stop(f"no video for {audio_path}")
    if not (os.environ.get("UPLOAD_POST_API_KEY") and os.environ.get("UPLOAD_POST_USER")):
        raise stop("UPLOAD_POST_API_KEY / UPLOAD_POST_USER are not set")

    print(f"\nUploading video to YouTube via upload-post: {video_source}")
    video_for_upload = video_source
    is_url = str(video_source).lower().startswith(("http://", "https://"))
    if not is_url and wants_r2_staging_for_local_video(video_source, args):
        if not r2_public_uploads_configured():
            raise stop(
                "R2 staging is required for this local video (size >= "
                f"{os.environ.get('YOUTUBE_VIDEO_R2_THRESHOLD_MB', '400')} MB or --youtube-via-r2) "
                "but R2 is not fully configured. Set R2_PUBLIC_URL and R2_ACCOUNT_ID, "
                "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (see tools/README.md), "
                "or pass --youtube-no-r2-staging to allow direct upload-post (fragile for large files)."
            )
        threshold = int(os.environ.get("YOUTUBE_VIDEO_R2_THRESHOLD_MB", "400"))
        mb = os.path.getsize(video_source) / (1024 * 1024)
        if getattr(args, "youtube_via_r2", False):
            print("R2 staging: forced via --youtube-via-r2")
        elif mb >= threshold:
            print(f"R2 staging: auto ({mb:.0f} MB >= {threshold} MB)")
        cached_stage = load_r2_youtube_staging_marker(youtube_staging_marker, episode_number)
        if cached_stage:
            video_for_upload, _ = cached_stage
            preview = video_for_upload if len(video_for_upload) <= 90 else video_for_upload[:88] + "…"
            print(f"✓ Reusing R2-staged video from {youtube_staging_marker} (no re-upload to R2): {preview}")
        else:
            staged = upload_staging_video_to_r2(video_source, episode_number, verbose=args.verbose)
            if not staged:
                raise stop(
                    "R2 staging upload failed; refusing direct upload to upload-post. "
                    "Fix R2 credentials/bucket or use --youtube-video-url / UPLOAD_POST_VIDEO_URL "
                    "with a public HTTPS URL, or --youtube-no-r2-staging if you accept direct upload."
                )
            video_for_upload, new_key = staged
            save_r2_youtube_staging_marker(youtube_staging_marker, video_for_upload, new_key, episode_number)

    kept = (
        f" Staged MP4 kept on R2 for retry; URL and key in {youtube_staging_marker}."
        if os.path.isfile(youtube_staging_marker)
        else ""
    )
    try:
        status = upload_to_youtube(
            video_for_upload,
            youtube_title,
            youtube_description_text,
            scheduled_date=publish_schedule.upload_post_scheduled_date if publish_schedule else None,
            schedule_timezone=publish_schedule.upload_post_timezone if publish_schedule else None,
        )
    except Exception as e:  # noqa: BLE001 - upload-post and HTTP raise many types
        raise stop(f"YouTube upload failed: {e}.{kept}") from e

    youtube_embed_url = status_to_youtube_embed_url(status) or ""
    youtube_job_id = scheduled_upload_job_id(status)
    if youtube_embed_url:
        print(f"✓ YouTube embed URL: {youtube_embed_url}")
        with open(youtube_url_file, "w", encoding="utf-8") as f:
            f.write(youtube_embed_url + "\n")
        remove_r2_youtube_staging_marker(youtube_staging_marker)
        return youtube_embed_url
    if youtube_job_id:
        with open(youtube_scheduled_file, "w", encoding="utf-8") as f:
            f.write(f"job_id={youtube_job_id}\n")
            if isinstance(status, dict) and status.get("scheduled_date"):
                f.write(f"scheduled_date={status['scheduled_date']}\n")
            if publish_schedule:
                f.write(f"requested_schedule={publish_schedule.source}\n")
        print(
            f"✓ YouTube upload scheduled via upload-post: {youtube_job_id} "
            f"({publish_schedule.upload_post_scheduled_date if publish_schedule else 'scheduled'})"
        )
        if os.path.isfile(youtube_staging_marker):
            print(f"  R2 staging marker kept until the scheduled video is published: {youtube_staging_marker}")
        return ""
    yt_err = youtube_status_error_message(status) if isinstance(status, dict) else None
    raise stop(
        f"YouTube did not publish a video: {yt_err or 'upload-post completed without a YouTube embed URL'}."
        f"{kept} Re-run after fixing upload-post / YouTube, or write the embed URL into the checkpoint."
    )


def process_audio(audio_path: str, args) -> None:
    """Run the full pipeline for one mp3: every question first, then the uploads."""
    audio_path = os.path.abspath(audio_path)
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Audio: {audio_path}")
    print(f"File stem: {Path(audio_path).stem}")
    print(f"{'='*60}")

    client_id = os.environ.get("PODBEAN_CLIENT_ID")
    client_secret = os.environ.get("PODBEAN_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise PipelineStop("PODBEAN_CLIENT_ID and PODBEAN_CLIENT_SECRET must be set")

    print("Authenticating with Podbean...")
    auth_token = get_podbean_auth_token(client_id, client_secret)
    print("✓ Authenticated")

    episode_number, existing_episode, episode_plan = resolve_episode(
        audio_path, args, get_podbean_episodes(auth_token)
    )
    publish_schedule = None
    if existing_episode:
        publish_schedule = publish_schedule_from_podbean_episode(existing_episode)
        if publish_schedule:
            print(f"✓ Preserved existing Podbean schedule: {publish_schedule.display}")

    out_base = os.path.join(OUT_DIR, checkpoint_prefix(episode_number))
    print(f"✓ Checkpoints under: {out_base}-*")

    checkpoint_files = sorted(Path(OUT_DIR).glob(f"{checkpoint_prefix(episode_number)}*"))
    # The source marker itself is metadata, not evidence of reusable content.
    reusable_checkpoint_files = [
        path for path in checkpoint_files if path.name != f"{checkpoint_prefix(episode_number)}-source.json"
    ]
    try:
        validate_or_bind_checkpoint_source(out_base, audio_path, reusable_checkpoint_files)
    except ValueError as e:
        raise PipelineStop(str(e), checkpoint=f"{out_base}-source.json") from e
    if reusable_checkpoint_files:
        print(
            f"✓ Found {len(reusable_checkpoint_files)} existing checkpoint file(s); "
            f"resuming episode #{episode_number}"
        )

    if not args.draft_only:
        require_publishing_prerequisites(args, audio_path, out_base, existing_episode)

    # 1. Editorial guidance
    guidance = _load_or_prompt_guidance(f"{out_base}-guidance.txt", args.guidance)
    raw_notes, raw_note_names = load_raw_companion_markdown(audio_path)
    if raw_note_names:
        print(f"✓ Companion show notes: {', '.join(raw_note_names)}")

    # 2. Local transcription; 3. hosts named by voice
    load_or_transcribe(audio_path, out_base, args.skip_transcription, verbose=args.verbose)
    host_names, turns = confirm_speakers(audio_path, out_base)

    # 4. The operator names every other voice; research looks those guests up
    guest_context, speaker_names = identify_guests(
        out_base, turns, host_names, guidance, raw_notes, verbose=args.verbose
    )
    guest_prompt_text = guest_context_to_prompt_text(guest_context)
    article_guidance = "\n\n".join(x for x in (guidance, guest_prompt_text) if x).strip()

    # 5. Transcript correction; every later step reads its output
    reference_text = load_reference_text(args.transcript, audio_path)
    refresh_checkpoints(out_base, "transcript", turns, guest_context, reference_text, speaker_names)
    corrected_turns = correct_transcript(
        out_base, turns, guest_context, reference_text, speaker_names=speaker_names, verbose=args.verbose
    )
    transcript = render_corrected_transcript(corrected_turns)

    # 6. Chapters; 7. title and teaser, from the corrected transcript
    refresh_checkpoints(out_base, "chapters", corrected_turns)
    chapters = load_or_generate_chapters(out_base, corrected_turns, verbose=args.verbose)
    refresh_checkpoints(out_base, "title", chapters, transcript, article_guidance)
    title = _load_or_pick(
        "title", f"{out_base}-title.txt", args.title, guest_context,
        lambda: pick_title(chapters, transcript, editorial_guidance=article_guidance, verbose=args.verbose),
    )
    print(f"✓ Title: {title}")
    if len(title) > TITLE_TARGET_CHARS:
        # Guest names are required, so the length target is advisory only.
        print(f"⚠ Title is {len(title)} chars (target under {TITLE_TARGET_CHARS}); kept as picked.")
    description = _load_or_pick(
        "description", f"{out_base}-description.txt", args.description, guest_context,
        lambda: pick_description(chapters, transcript, editorial_guidance=article_guidance, verbose=args.verbose),
    )
    print("✓ Description saved")

    # 8. Article, written to the picked title, teaser and chapters
    refresh_checkpoints(out_base, "article", transcript, title, description, chapters, article_guidance, raw_notes)
    article_md = generate_article(
        transcript,
        out_base,
        editorial_guidance=article_guidance,
        raw_notes=raw_notes,
        verbose=args.verbose,
        title=title,
        teaser=description,
        chapters=chapters,
    )
    html_problems = article_html_problems(article_md)
    if html_problems:
        raise PipelineStop(
            f"the article carries HTML the episode page does not allow "
            f"({', '.join(sorted(ALLOWED_ARTICLE_TAGS))} only):\n  - " + "\n  - ".join(html_problems)
            + "\nFix it, then re-run. Nothing was uploaded.",
            checkpoint=f"{out_base}-article.md",
        )
    if args.draft_only:
        print(f"\nDraft-only: done. Article: {out_base}-article.md")
        return

    # 9. Metadata and the YouTube text
    refresh_checkpoints(out_base, "metadata", title, description, article_md, transcript, guest_context)
    metadata = load_or_generate_metadata(
        out_base, title, description, article_md, transcript,
        guest_context=guest_context, guest_text=guest_prompt_text, verbose=args.verbose,
    )
    youtube_title = build_youtube_title(metadata, episode_number, title)
    youtube_description_text = build_youtube_description(
        metadata, episode_number, chapters=chapters, guest_context=guest_context,
    )
    yt_desc_path = f"{out_base}-youtube-description.txt"
    with open(yt_desc_path, "w", encoding="utf-8") as f:
        f.write(youtube_description_text)
    print(f"✓ YouTube title: {youtube_title}")
    print(f"✓ YouTube description saved to {yt_desc_path}")
    for warning in youtube_description_warnings(youtube_description_text, metadata, chapters):
        print(f"⚠ YouTube description: {warning}")

    # 10. Cover, drawn locally; uploaded with the rest below
    try:
        cover_path = draw_cover(episode_number, title, guest_full_names(guest_context), f"{out_base}-cover.png")
    except Exception as e:  # noqa: BLE001 - Pillow and disk fail differently
        raise PipelineStop(f"cover generation failed ({e}); nothing was uploaded") from e
    cover_url = cover_public_url(cover_path, episode_number)

    # 11. Release time. An existing Podbean episode keeps its own.
    if existing_episode is None:
        publish_schedule = prompt_publish_action(episode_plan)
        if publish_schedule:
            print(f"✓ Episode will be published on: {publish_schedule.display}")
        else:
            print("✓ Episode will be published immediately")

    # 12. Announcement approval, at the URL the page will have
    page_path = episode_page_path(episode_number, title)
    release_at = None
    if existing_episode is None:
        release_at = (
            publish_schedule.podbean_datetime if publish_schedule else datetime.datetime.now(datetime.timezone.utc)
        )
    approve_episode_announcement(
        out_base, episode_number, episode_page_url(page_path), title, article_md, corrected_turns,
        guest_context, release_at, cover_path, cover_url, verbose=args.verbose,
    )

    # Nothing below asks the operator anything: uploads, page and posts run unattended.

    # 14. Cover, Podbean, YouTube
    cover_url = upload_cover_to_r2(cover_path, episode_number)
    if existing_episode:
        print(f"\n✓ Reusing existing Podbean {_episode_display_title(existing_episode)}")
        podbean_episode = existing_episode
    else:
        podbean_episode = publish_to_podbean(
            auth_token, audio_path, out_base, episode_number, title,
            build_podbean_show_notes(metadata, episode_number), publish_schedule, release_at, verbose=args.verbose,
        )
    podbean_id = podbean_player_id(podbean_episode)
    when = publish_schedule.display if publish_schedule else str(podbean_episode.get("status") or "publish")
    print(f"✓ Podbean player id: {podbean_id} ({when})")
    youtube_embed_url = publish_to_youtube(
        args, audio_path, out_base, episode_number, youtube_title, youtube_description_text, publish_schedule,
    )

    # 15. Episode page
    episode_path = write_episode_markdown(
        episode_number,
        title,
        description,
        article_md,
        podbean_id,
        resolve_youtube_video_id(youtube_embed_url),
        participants=_participants_for_episode(getattr(args, "participants", None), guest_context),
        publish_datetime=publish_schedule.podbean_datetime if publish_schedule else None,
        subtitle=str(metadata.get("subtitle") or ""),
        readtime=readtime_for(article_md),
        image=cover_url,
        audio_url=str(podbean_episode.get("media_url") or ""),
    )
    print(f"✓ Episode page: {episode_path}")

    # 16. The approved announcement, after the page so the post can link it
    schedule_episode_announcement(out_base, episode_number, episode_path, guest_context, cover_url)

    print(f"\n{'='*60}")
    print(f"Episode #{episode_number} complete.")
    print(f"{'='*60}")


# Errors a step raises to stop the run; main prints them once and exits 1.
STOP_ERRORS = (
    PipelineStop,
    AnnouncementStop,
    R2CoverError,
    voice_match.SpeakerConfirmationError,
    voice_match.VoicePrintError,
)


def report_stop(error: Exception) -> None:
    print(f"\nError: {error}", file=sys.stderr)
    checkpoint = getattr(error, "checkpoint", "") or ""
    if checkpoint:
        print(f"Checkpoint: {checkpoint}", file=sys.stderr)
    print("Fix the cause and re-run ./do.sh; it resumes at this step.", file=sys.stderr)


def main():
    args = parse_args()
    try:
        require_tools(draft_only=args.draft_only)
        # Stage downloads into raw/ unless an explicit file path was given.
        if not (args.filename or args.audio):
            stage_downloads_to_raw()
        audio_paths = _collect_audio_paths(args)
        if len(audio_paths) > 1 and args.episode_number is not None:
            raise PipelineStop("--episode-number cannot be combined with multiple input files")
        # One episode at a time, so each episode's questions come after the previous one's uploads.
        for ap in audio_paths:
            process_audio(ap, args)
    except STOP_ERRORS as e:
        report_stop(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
