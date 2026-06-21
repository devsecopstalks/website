#!/usr/bin/env python3

import os
import re
import argparse
import hashlib
import json
import requests
import mimetypes
import datetime
import sys
import tempfile
import subprocess
import shutil
import math
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from openai import OpenAI

from episode_pipeline import (
    detect_guests,
    generate_article,
    guest_context_to_prompt_text,
    load_raw_companion_markdown,
    load_guest_context,
    normalize_operator_guest_notes,
    pick_description,
    pick_title,
    save_guest_context,
)
from r2_staging import (
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
    """Move new mp3/mp4 from ~/Downloads into raw/, in a re-run-safe way.

    Cases:
    - Downloads has media, raw/ is empty: move everything in and proceed.
    - Both Downloads and raw/ have media: refuse and ask the operator to clean
      up raw/ first, so a re-run never mixes old and new files.
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
        print(
            "\nClean up raw/ before proceeding so old and new files do not mix, "
            "then re-run."
        )
        sys.exit(1)

    if downloads:
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


def parse_publish_schedule(value: str | None, timezone_name: str | None = None) -> PublishSchedule | None:
    """
    Parse a future publish date for Podbean and upload-post.

    Accepted values are ISO-8601 datetimes, e.g. ``2026-07-01T09:00:00Z``,
    ``2026-07-01T11:00:00+02:00``, or a naive local time such as
    ``2026-07-01 11:00``. Naive values use ``--schedule-timezone`` when
    provided, otherwise the machine's local timezone.
    """
    raw = (value or "").strip()
    if not raw:
        if timezone_name:
            raise ValueError("--schedule-timezone requires --schedule-at")
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise ValueError("--schedule-at must include a time, e.g. 2026-07-01T09:00:00Z")

    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.datetime.fromisoformat(normalized)
    except ValueError as e:
        raise ValueError(
            f"Invalid --schedule-at value: {raw!r}. Use an ISO-8601 datetime."
        ) from e

    if parsed.tzinfo is not None and timezone_name:
        raise ValueError(
            "--schedule-timezone is only valid when --schedule-at has no timezone offset"
        )

    upload_post_timezone = None
    if parsed.tzinfo is None:
        if timezone_name:
            try:
                tz = ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError as e:
                raise ValueError(f"Unknown --schedule-timezone: {timezone_name}") from e
            podbean_dt = parsed.replace(tzinfo=tz)
            upload_post_date = parsed.replace(microsecond=0).isoformat()
            upload_post_timezone = timezone_name
        else:
            podbean_dt = parsed.replace(tzinfo=_local_timezone())
            upload_post_date = _iso_utc_z(podbean_dt)
    else:
        podbean_dt = parsed
        upload_post_date = _iso_utc_z(parsed)

    podbean_dt = podbean_dt.replace(microsecond=0)
    if podbean_dt <= datetime.datetime.now(podbean_dt.tzinfo):
        raise ValueError("--schedule-at must be in the future")

    return PublishSchedule(
        source=raw,
        podbean_timestamp=int(podbean_dt.timestamp()),
        podbean_datetime=podbean_dt,
        display=podbean_dt.isoformat(),
        upload_post_scheduled_date=upload_post_date,
        upload_post_timezone=upload_post_timezone,
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
            # Podbean stores scheduled episodes as drafts carrying a future
            # publish timestamp. Ignore ordinary drafts whose timestamp is not
            # in the future, but retain scheduled drafts as timeline anchors.
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
    for episode in episodes:
        if not isinstance(episode, dict):
            continue
        ts = _episode_publish_timestamp(episode)
        if ts is None:
            continue
        if anchor_ts is None or ts > anchor_ts:
            anchor_ts = ts
            anchor_episode = episode
    anchor_datetime = (
        datetime.datetime.fromtimestamp(anchor_ts, local_tz).replace(microsecond=0)
        if anchor_ts is not None
        else None
    )
    return PodbeanEpisodePlan(next_episode_number, anchor_episode, anchor_datetime)


def should_prompt_for_schedule(
    anchor_datetime: datetime.datetime | None,
    now: datetime.datetime | None = None,
    minimum_spacing_days: int = 7,
) -> bool:
    if anchor_datetime is None:
        return False
    now = now or datetime.datetime.now(anchor_datetime.tzinfo)
    if anchor_datetime >= now:
        return True
    return now - anchor_datetime < datetime.timedelta(days=minimum_spacing_days)


def prompt_schedule_after_anchor(
    anchor_episode: dict,
    anchor_datetime: datetime.datetime,
    input_func=input,
) -> PublishSchedule | None:
    """Ask whether to schedule relative to latest published/scheduled episode."""
    now = datetime.datetime.now(anchor_datetime.tzinfo)
    delta = anchor_datetime - now
    if delta.total_seconds() >= 0:
        relation = f"scheduled {max(0, math.ceil(delta.total_seconds() / 86400))} day(s) from now"
    else:
        relation = f"published {max(0, math.floor((-delta).total_seconds() / 86400))} day(s) ago"

    print("\nEpisode spacing")
    print(
        f"Latest published/scheduled Podbean episode: {_episode_display_title(anchor_episode)} "
        f"at {anchor_datetime.isoformat()} ({relation})."
    )
    default_datetime = (anchor_datetime + datetime.timedelta(days=7)).replace(
        microsecond=0
    )
    print("Enter the number of days after that episode to schedule this one.")
    print(
        f"  Example: 7 → {default_datetime.isoformat()}\n"
        "  Press Enter to not schedule and choose draft or immediate publication."
    )

    raw_days: str | None = None
    while raw_days is None:
        print("> ", end="", flush=True)
        try:
            choice = input_func().strip().lower()
        except EOFError:
            print("\nNo input received; not scheduling this episode.")
            return None
        if choice in ("", "n", "no"):
            return None
        # Keep `y` compatible with the old prompt by treating it as the
        # displayed seven-day default. Numeric input schedules directly.
        raw_days = "7" if choice in ("y", "yes") else choice
        try:
            days = float(raw_days)
        except ValueError:
            print("Please enter a number of days, for example 8, or press Enter.")
            raw_days = None
            continue
        if days <= 0:
            print("Please enter a positive number of days.")
            raw_days = None
            continue
        candidate = (anchor_datetime + datetime.timedelta(days=days)).replace(microsecond=0)
        if candidate <= datetime.datetime.now(candidate.tzinfo):
            print(
                f"That would schedule at {candidate.isoformat()}, which is not in the future. "
                "Enter a larger number of days."
            )
            raw_days = None
            continue
        return publish_schedule_from_datetime(
            candidate,
            f"{days:g} days after {_episode_display_title(anchor_episode)}",
        )


def build_youtube_description_plain(teaser: str, episode_number: int, title_short: str) -> str:
    """
    Plain-text description for upload-post → YouTube.

    Uses short labels with **URL on the following line**. Episode link uses
    ``/episodes/NNN/`` (requires matching Hugo ``aliases`` on the episode page)
    so paths stay short — YouTube often ellipsizes long URLs in the description UI.
    ``title_short`` is kept for a stable call signature; the website still uses
    the full slug in the episode filename and canonical URL.
    """
    _ = title_short
    episode_url = f"https://devsecops.fm/episodes/{episode_number:03d}/"
    lines = [
        teaser.strip(),
        "",
        "We are always happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.",
        "",
        "Podcast website",
        "https://devsecops.fm/",
        "",
        "LinkedIn",
        "https://linkedin.com/company/devsecops-talks/",
        "",
        "YouTube channel",
        "https://www.youtube.com/channel/UCRjpE9xKxZeBkRgYiLErEjw",
        "",
        "This episode — audio & show notes",
        episode_url,
        "",
        "Subscribe to the podcast",
        "https://devsecops.fm/",
        "",
        "#DevSecOps #InfraAsCode #CloudSecurity #DevOps #Podcast #CyberSecurity #Security #SSDLC #Devsecopstalks",
    ]
    return "\n".join(lines)


def _participants_yaml_line(participants: list[str]) -> str:
    """Single YAML line: participants: ["A", "B"] with minimal escaping."""
    inner = ", ".join(f'"{yaml_escape_double_quoted(p)}"' for p in participants)
    return f"participants: [{inner}]"


def write_episode_markdown(
    episode_number: int,
    title_short: str,
    description: str,
    article_md: str,
    podbean_id: str,
    youtube_video_id: str,
    participants: list[str] | None = None,
    publish_datetime: datetime.datetime | None = None,
) -> str:
    """Write Hugo episode page; mirrors published episode layout."""
    participants = participants if participants is not None else list(DEFAULT_PARTICIPANTS)
    full_title = f"#{episode_number} - {title_short}"
    slug = title_to_url_safe(title_short)
    filename = f"{episode_number:03d}-{slug}.md"
    path = os.path.join(EPISODES_DIR, filename)
    page_datetime = publish_datetime or datetime.datetime.now().astimezone()
    date_iso = page_datetime.astimezone().replace(microsecond=0).isoformat()
    title_yaml = yaml_escape_double_quoted(full_title)
    podbean_title = f"DEVSECOPS Talks {full_title}"
    # f-strings: {{ → literal {. Hugo needs {{< not {< — use {{{{ for {{ in output.
    podbean_line = f' {{{{<  podbean {podbean_id} "{podbean_title}"  >}}}} '

    parts = [
        "---",
        f'title: "{title_yaml}"',
        f"date: {date_iso}",
        f"lastmod: {date_iso}",
        f"episode: {episode_number}",
        'author: "DevSecOps Talks"',
        _participants_yaml_line(participants),
        "aliases:",
        f'  - "/episodes/{episode_number:03d}/"',
        "---",
        "",
        description,
        "",
        "[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)",
        "",
        "<!--more-->",
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


def compress_audio_for_transcription(audio_file_path, bitrate='32k', verbose=False):
    """
    Compress audio file using ffmpeg to reduce file size for OpenAI transcription uploads.
    
    Args:
        audio_file_path: Path to the audio file
        bitrate: Target bitrate (default '32k' for 32kbps mono)
        verbose: Whether to print verbose output
    
    Returns:
        Path to compressed file
    """
    if not shutil.which('ffmpeg'):
        print("Error: ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)
    
    base_name = os.path.splitext(audio_file_path)[0]
    compressed_file = f"{base_name}_compressed.mp3"
    
    original_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
    print(f"Compressing audio ({original_size_mb:.2f} MB) to {bitrate} mono...")
    
    cmd = [
        'ffmpeg', '-i', audio_file_path,
        '-ac', '1',  # Convert to mono
        '-b:a', bitrate,  # Set bitrate
        '-y',  # Overwrite output file
        compressed_file
    ]
    
    if not verbose:
        cmd.extend(['-loglevel', 'error'])
    
    try:
        subprocess.run(cmd, check=True, capture_output=not verbose)
        
        compressed_size_mb = os.path.getsize(compressed_file) / (1024 * 1024)
        reduction = ((original_size_mb - compressed_size_mb) / original_size_mb) * 100
        
        print(f"Compressed: {original_size_mb:.2f} MB → {compressed_size_mb:.2f} MB ({reduction:.1f}% reduction)")
        
        return compressed_file
    except subprocess.CalledProcessError as e:
        print(f"Error compressing audio: {e}")
        raise


# gpt-4o-transcribe accepts at most 1400s per request; stay below with chunk size.
_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"
_MAX_TRANSCRIPTION_SECONDS = 1400
_CHUNK_SECONDS = 1200

_TRANSCRIPTION_PROMPT = (
    "DevSecOps Talks podcast. Hosts: Andrey Devyatkin, Mattias Hemmingsson, Paulina Dubas. "
    "Former host: Julien Bisconti. Companies: FivexL, Dubas Consulting, Sirob Technologies, "
    "Boris, Hacking Robots and Beer. Topics: AWS, Kubernetes, Terraform, HashiCorp Vault, "
    "CI/CD, Jenkins, GitOps, Argo CD, CloudFormation, IAM, SSO Elevator, Control Tower, "
    "GuardDuty, CloudTrail, ECS, EKS, SOC2, HIPAA, PCI DSS."
)


def get_audio_duration_seconds(audio_file_path):
    """Return duration in seconds using ffprobe."""
    if not shutil.which("ffprobe"):
        print("Error: ffprobe not found. Install with: brew install ffmpeg")
        sys.exit(1)
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def extract_audio_segment(
    input_path, start_sec, duration_sec, output_path, verbose=False
):
    """Write [start_sec, start_sec + duration_sec) to output_path (mono 32k mp3)."""
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_sec),
        "-i",
        input_path,
        "-t",
        str(duration_sec),
        "-ac",
        "1",
        "-b:a",
        "32k",
        output_path,
    ]
    if not verbose:
        cmd.extend(["-loglevel", "error"])
    subprocess.run(cmd, check=True, capture_output=not verbose)


def transcribe_audio_openai(client, audio_file_path, verbose=False):
    """
    Transcribe an audio file using OpenAI audio transcriptions API (see _TRANSCRIPTION_MODEL).
    Automatically compresses large files if needed.
    Long audio is split into segments under the API duration limit, then merged.
    
    Args:
        client: OpenAI client instance
        audio_file_path: Path to the audio file to transcribe
        verbose: Whether to print verbose output
    
    Returns:
        Transcription text
    """
    try:
        print(f"Transcribing audio file: {audio_file_path}")
        
        # Check file size and compress if needed
        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        max_size_mb = 24  # Stay under 25MB limit
        
        file_to_transcribe = audio_file_path
        cleanup_file = None
        
        if file_size_mb > max_size_mb:
            print(f"File size ({file_size_mb:.2f} MB) exceeds {max_size_mb} MB limit")
            file_to_transcribe = compress_audio_for_transcription(audio_file_path, verbose=verbose)
            cleanup_file = file_to_transcribe
        
        duration_sec = get_audio_duration_seconds(file_to_transcribe)
        if verbose:
            print(f"Audio duration: {duration_sec:.1f}s ({duration_sec / 60:.1f} min)")

        def transcribe_one(path):
            with open(path, "rb") as audio_file:
                return client.audio.transcriptions.create(
                    model=_TRANSCRIPTION_MODEL,
                    file=audio_file,
                    response_format="text",
                    language="en",
                    prompt=_TRANSCRIPTION_PROMPT,
                )

        print(_TRANSCRIPTION_MODEL)

        if duration_sec <= _MAX_TRANSCRIPTION_SECONDS:
            transcript = transcribe_one(file_to_transcribe)
        else:
            n_chunks = math.ceil(duration_sec / _CHUNK_SECONDS)
            print(
                f"Audio exceeds {_MAX_TRANSCRIPTION_SECONDS}s model limit; "
                f"transcribing in {n_chunks} segment(s) (≤{_CHUNK_SECONDS}s each)..."
            )
            parts = []
            tmpdir = tempfile.mkdtemp(prefix="podbean_transcribe_")
            try:
                for i in range(n_chunks):
                    start = i * _CHUNK_SECONDS
                    seg_len = min(_CHUNK_SECONDS, duration_sec - start)
                    chunk_path = os.path.join(tmpdir, f"chunk_{i:04d}.mp3")
                    extract_audio_segment(
                        file_to_transcribe,
                        start,
                        seg_len,
                        chunk_path,
                        verbose=verbose,
                    )
                    if verbose:
                        print(f"Transcribing segment {i + 1}/{n_chunks} ({seg_len:.0f}s)...")
                    parts.append(transcribe_one(chunk_path))
                transcript = "\n\n".join(parts)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

        # Clean up compressed file if created
        if cleanup_file and os.path.exists(cleanup_file):
            os.remove(cleanup_file)
            if verbose:
                print(f"Removed temporary file: {cleanup_file}")
        
        if verbose:
            print(f"Transcription completed. Length: {len(transcript)} characters")
        
        return transcript
    
    except Exception as e:
        print(f'An error occurred during transcription: {str(e)}')
        raise


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


def prompt_podbean_episode_status(input_func=input) -> str:
    """Ask whether the new Podbean episode should publish immediately or stay draft."""
    print("\nPodbean action — choose what happens when the episode is created:")
    print("  [Enter/d] Save as draft (not publicly visible)")
    print("  [p]       Publish immediately")
    while True:
        print("> ", end="", flush=True)
        try:
            choice = input_func().strip().lower()
        except EOFError:
            print("\nNo input received; keeping Podbean episode in draft mode.")
            return "draft"

        if choice in ("", "d", "draft"):
            print("✓ Podbean action selected: save as draft")
            return "draft"
        if choice in ("p", "publish", "y", "yes"):
            print("✓ Podbean action selected: publish immediately")
            return "publish"
        print("Please enter 'd' for draft or 'p' for publish.")


def resolve_podbean_episode_status(status_arg: str) -> str:
    """Resolve CLI status selection; prompts only for the interactive default."""
    status = (status_arg or "ask").strip().lower()
    if status == "ask":
        return prompt_podbean_episode_status()
    if status in ("draft", "publish"):
        return status
    raise ValueError(f"Unsupported Podbean status: {status_arg}")


def podbean_creation_status(
    requested_status: str,
    publish_schedule: PublishSchedule | None,
) -> str:
    """Podbean schedules future episodes as drafts with a publish timestamp."""
    return "draft" if publish_schedule is not None else requested_status


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
    p.add_argument(
        "--podbean-status",
        choices=("ask", "draft", "publish"),
        default="ask",
        help="Podbean episode status: ask at publish time (default), draft, or publish",
    )
    p.add_argument(
        "--schedule-at",
        default=None,
        help=(
            "Future publish datetime for Podbean and upload-post YouTube, "
            "e.g. 2026-07-01T09:00:00Z or '2026-07-01 11:00'"
        ),
    )
    p.add_argument(
        "--schedule-timezone",
        default=None,
        help="IANA timezone for naive --schedule-at values, e.g. Europe/Madrid",
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


def _guest_names(guest_context: dict) -> list[str]:
    names: list[str] = []
    for guest in guest_context.get("guests") or []:
        if not isinstance(guest, dict):
            continue
        name = str(guest.get("participant_name") or guest.get("full_name") or "").strip()
        if name:
            names.append(name)
    return names


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


def _operator_details_to_fields(details: str) -> tuple[str, str, str]:
    """Convert loose role/company details into structured fields."""
    details = details.strip()
    clean_details = re.sub(r"https?://\S+", "", details).strip(" ,.;")
    if not clean_details:
        return "", "", ""

    if "@" in clean_details:
        role, company = clean_details.split("@", 1)
        return role.strip(" ,.;"), company.strip(" ,.;"), ""

    org_match = re.match(r"(.+?)\s+(?:at|from|for)\s+(.+)$", clean_details, flags=re.I)
    if org_match:
        return org_match.group(1).strip(" ,.;"), org_match.group(2).strip(" ,.;"), ""

    tokens = clean_details.split()
    role_tokens: list[str] = []
    for token in tokens:
        key = token.strip(".,:;()[]{}").casefold()
        if key in GUEST_ROLE_STARTERS or key in {"&", "and", "of"}:
            role_tokens.append(token)
            continue
        break

    if len(role_tokens) >= 2 and len(role_tokens) < len(tokens):
        company = " ".join(tokens[len(role_tokens) :]).strip(" ,.;")
        return " ".join(role_tokens).strip(" ,.;"), company, ""

    return "", "", details


def _repair_guest_context_names(guest_context: dict) -> dict:
    """Fix old operator checkpoints where full_name accidentally included role/company."""
    for guest in guest_context.get("guests") or []:
        if not isinstance(guest, dict):
            continue
        full_name = str(guest.get("full_name") or "").strip()
        participant_name = str(guest.get("participant_name") or "").strip()
        if not full_name or (participant_name and participant_name != full_name):
            continue
        name, details = _split_operator_guest_chunk(full_name)
        if not details or name == full_name:
            continue
        guest["full_name"] = name
        guest["participant_name"] = name
        role, company, summary = _operator_details_to_fields(details)
        if role and not str(guest.get("role") or "").strip():
            guest["role"] = role
        if company and not str(guest.get("company") or "").strip():
            guest["company"] = company
        if summary and not str(guest.get("professional_summary") or "").strip():
            guest["professional_summary"] = summary
    return guest_context


def _text_includes_guest_names(text: str, guest_context: dict) -> bool:
    required = _guest_names(guest_context)
    if not required:
        return True
    folded = text.casefold()
    return all(name.casefold() in folded for name in required)


def _participants_for_episode(arg: str | None, guest_context: dict) -> list[str]:
    participants = _parse_participants_arg(arg)
    if arg and str(arg).strip():
        return participants

    seen = {p.casefold() for p in participants}
    for guest_name in _guest_names(guest_context):
        key = guest_name.casefold()
        if key not in seen:
            participants.append(guest_name)
            seen.add(key)
    return participants


def _guest_context_needs_operator(guest_context: dict) -> bool:
    if guest_context.get("status") == "needs_operator":
        return True
    for guest in guest_context.get("guests") or []:
        if isinstance(guest, dict) and guest.get("needs_operator"):
            return True
    return False


def _fallback_manual_guest_context(raw: str) -> dict:
    guests: list[dict] = []
    for chunk in re.split(r"\s*;\s*", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, details = _split_operator_guest_chunk(chunk)
        if not name:
            continue
        urls = re.findall(r"https?://\S+", details)
        links = [
            {"label": url.rstrip(".,)"), "url": url.rstrip(".,)"), "type": "operator"}
            for url in urls
        ]
        role, company, summary = _operator_details_to_fields(details)
        guests.append(
            {
                "full_name": name,
                "participant_name": name,
                "role": role,
                "company": company,
                "professional_summary": summary,
                "links": links,
                "confidence": "operator",
                "needs_operator": False,
                "question": "",
            }
        )
    if guests:
        return {
            "status": "verified",
            "guests": guests,
            "notes": "Guest context provided by operator.",
        }
    return {"status": "needs_operator", "guests": [], "notes": "Could not parse guest names."}


def _manual_guest_context_from_operator(guest_context: dict, verbose: bool = False) -> dict:
    print("\nGuest lookup needs clarification.")
    notes = str(guest_context.get("notes") or "").strip()
    if notes:
        print(f"Notes: {notes}")
    for guest in guest_context.get("guests") or []:
        if not isinstance(guest, dict):
            continue
        question = str(guest.get("question") or "").strip()
        full_name = str(guest.get("full_name") or "Unknown guest").strip()
        if question:
            print(f"- {full_name}: {question}")

    while True:
        print(
            "Enter guest context as free-form text with names, roles, companies, and links. "
            "Type 'none' if there are no guests."
        )
        print("> ", end="", flush=True)
        raw = input().strip()
        if not raw:
            print("Guest clarification is required to continue.")
            continue
        if raw.lower() in ("none", "no", "no guests"):
            return {"status": "no_guests", "guests": [], "notes": "Operator reported no guests."}

        try:
            normalized = normalize_operator_guest_notes(raw, guest_context, verbose=verbose)
        except Exception as e:
            print(f"⚠ Could not normalize guest context with Claude ({e}); using local parser.")
            normalized = _fallback_manual_guest_context(raw)
        normalized = _repair_guest_context_names(normalized)
        if normalized.get("guests"):
            return normalized
        print("Could not parse a guest name. Try again.")


def _load_or_detect_guest_context(
    guest_context_file: str,
    transcript: str,
    guidance: str,
    raw_notes: str,
    verbose: bool,
) -> dict:
    guest_context: dict | None = None
    if os.path.exists(guest_context_file):
        try:
            saved = load_guest_context(guest_context_file)
            names = _guest_names(saved)
            summary = ", ".join(names) if names else "no guests"
            print(f'\nFound saved guest context: {summary}')
            print("Press Enter to reuse, or type 'new' to refresh guest lookup: ", end="", flush=True)
            if input().strip().lower() != "new":
                guest_context = _repair_guest_context_names(saved)
        except Exception as e:
            print(f"⚠ Could not read saved guest context ({e}); regenerating")

    if guest_context is None:
        guest_context = detect_guests(
            transcript,
            editorial_guidance=guidance,
            raw_notes=raw_notes,
            verbose=verbose,
        )

    if _guest_context_needs_operator(guest_context):
        guest_context = _manual_guest_context_from_operator(guest_context, verbose=verbose)
    guest_context = _repair_guest_context_names(guest_context)

    save_guest_context(guest_context_file, guest_context)
    print(f"✓ Guest context saved to {guest_context_file}")
    return guest_context


def process_audio(audio_path: str, args, client: OpenAI) -> None:
    """Run full pipeline for one mp3."""
    audio_path = os.path.abspath(audio_path)
    stem = Path(audio_path).stem
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Audio: {audio_path}")
    print(f"File stem: {stem}")
    print(f"{'='*60}")

    client_id = os.environ.get("PODBEAN_CLIENT_ID")
    client_secret = os.environ.get("PODBEAN_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Error: PODBEAN_CLIENT_ID and PODBEAN_CLIENT_SECRET must be set")
        sys.exit(1)

    try:
        publish_schedule = parse_publish_schedule(args.schedule_at, args.schedule_timezone)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    if publish_schedule:
        print(f"✓ Episode will be scheduled for: {publish_schedule.display}")

    print("Authenticating with Podbean...")
    auth_token = get_podbean_auth_token(client_id, client_secret)
    print("✓ Authenticated")

    podbean_episode_data = get_podbean_episodes(auth_token)
    episode_plan = episode_plan_from_podbean_response(podbean_episode_data)
    if args.episode_number is not None and args.episode_number < 1:
        print("Error: --episode-number must be greater than zero")
        sys.exit(1)
    inferred_resume = (
        None
        if args.episode_number is not None or args.scan
        else infer_resume_episode_number(episode_plan.next_episode_number)
    )
    episode_number = (
        args.episode_number or inferred_resume or episode_plan.next_episode_number
    )
    existing_episode = find_podbean_episode(podbean_episode_data, episode_number)
    if args.episode_number is not None:
        print(f"✓ Resuming episode number: {episode_number}")
    elif inferred_resume is not None:
        print(f"✓ Automatically resuming unfinished episode #{episode_number}")
    else:
        print(f"✓ Next episode number (from Podbean episodes): {episode_number}")

    if existing_episode and (
        args.schedule_at is not None or args.podbean_status != "ask"
    ):
        print(
            "Error: publishing options cannot be applied while reusing an existing "
            "Podbean episode; update it in Podbean or resume without those options"
        )
        sys.exit(1)
    if existing_episode and publish_schedule is None:
        publish_schedule = publish_schedule_from_podbean_episode(existing_episode)
        if publish_schedule:
            print(f"✓ Preserved existing Podbean schedule: {publish_schedule.display}")

    out_base = os.path.join(OUT_DIR, checkpoint_prefix(episode_number))
    print(f"✓ Checkpoints under: {out_base}-*.txt|.md")

    checkpoint_files = sorted(Path(OUT_DIR).glob(f"{checkpoint_prefix(episode_number)}*"))
    # The source marker itself is metadata, not evidence of reusable content.
    reusable_checkpoint_files = [
        path for path in checkpoint_files if path.name != f"{checkpoint_prefix(episode_number)}-source.json"
    ]
    try:
        validate_or_bind_checkpoint_source(
            out_base,
            audio_path,
            reusable_checkpoint_files,
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    if reusable_checkpoint_files:
        print(
            f"✓ Found {len(reusable_checkpoint_files)} existing checkpoint file(s); "
            f"resuming episode #{episode_number}"
        )

    transcript_file = f"{out_base}.txt"
    title_file = f"{out_base}-title.txt"
    description_file = f"{out_base}-description.txt"
    guidance_file = f"{out_base}-guidance.txt"
    guest_context_file = f"{out_base}-guests.json"
    youtube_url_file = f"{out_base}-youtube-url.txt"
    youtube_scheduled_file = f"{out_base}-youtube-scheduled.txt"
    youtube_staging_marker = f"{out_base}-r2-youtube-staging.txt"
    podbean_upload_checkpoint = f"{out_base}-podbean-upload.json"

    # Editorial guidance
    guidance = args.guidance
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

    raw_notes, raw_note_names = load_raw_companion_markdown(audio_path)
    if raw_note_names:
        print(f"✓ Companion show notes: {', '.join(raw_note_names)}")

    # Transcript
    if args.transcript:
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript = f.read()
        print(f"✓ Loaded transcript from {args.transcript}")
    elif os.path.exists(transcript_file):
        with open(transcript_file, "r", encoding="utf-8") as f:
            transcript = f.read()
        print(f"✓ Loaded existing transcript {transcript_file}")
    elif args.skip_transcription:
        print(f"Error: --skip-transcription but no transcript at {transcript_file} (use -t)")
        sys.exit(1)
    else:
        print("Transcribing...")
        transcript = transcribe_audio_openai(client, audio_path, verbose=args.verbose)
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript)
        print(f"✓ Transcript saved to {transcript_file}")

    guest_context = _load_or_detect_guest_context(
        guest_context_file,
        transcript,
        guidance,
        raw_notes,
        args.verbose,
    )
    guest_prompt_text = guest_context_to_prompt_text(guest_context)
    article_guidance = "\n\n".join(x for x in (guidance, guest_prompt_text) if x).strip()

    article_md = generate_article(
        transcript,
        out_base,
        editorial_guidance=article_guidance,
        raw_notes=raw_notes,
        verbose=args.verbose,
    )

    if args.draft_only:
        print(f"\nDraft-only: done. Article: {out_base}-article.md")
        return

    # Title
    title = (args.title or "").strip() or None
    if title and not _text_includes_guest_names(title, guest_context):
        print(
            "Error: --title must include guest full name(s): "
            + ", ".join(_guest_names(guest_context))
        )
        sys.exit(1)
    if not title and os.path.exists(title_file):
        with open(title_file, "r", encoding="utf-8") as f:
            saved_t = f.read().strip()
        print(f'\nFound saved title: "{saved_t}"')
        if not _text_includes_guest_names(saved_t, guest_context):
            print("Saved title does not include guest full name(s); picking again.")
        else:
            print("Press Enter to reuse, or type 'new' to pick again: ", end="", flush=True)
        if _text_includes_guest_names(saved_t, guest_context) and input().strip().lower() != "new":
            title = saved_t
    if not title:
        while not title:
            picked_title = pick_title(
                article_md, editorial_guidance=article_guidance, verbose=args.verbose
            )
            if _text_includes_guest_names(picked_title, guest_context):
                title = picked_title
            else:
                print(
                    "Picked title is missing guest full name(s): "
                    + ", ".join(_guest_names(guest_context))
                )
    with open(title_file, "w", encoding="utf-8") as f:
        f.write(title)
    print(f"✓ Title: {title}")

    # Short teaser description (Podbean + above-the-fold)
    description = (args.description or "").strip() or None
    if description and not _text_includes_guest_names(description, guest_context):
        print(
            "Error: --description must include guest full name(s): "
            + ", ".join(_guest_names(guest_context))
        )
        sys.exit(1)
    if not description and os.path.exists(description_file):
        with open(description_file, "r", encoding="utf-8") as f:
            saved_d = f.read().strip()
        if not _text_includes_guest_names(saved_d, guest_context):
            print("\nSaved description does not include guest full name(s); picking again.")
        else:
            print(f"\nFound saved description ({len(saved_d)} chars). Press Enter to reuse, or 'new': ", end="", flush=True)
        if _text_includes_guest_names(saved_d, guest_context) and input().strip().lower() != "new":
            description = saved_d
    if not description:
        while not description:
            picked_description = pick_description(
                article_md, editorial_guidance=article_guidance, verbose=args.verbose
            )
            if _text_includes_guest_names(picked_description, guest_context):
                description = picked_description
            else:
                print(
                    "Picked description is missing guest full name(s): "
                    + ", ".join(_guest_names(guest_context))
                )
    with open(description_file, "w", encoding="utf-8") as f:
        f.write(description)
    print("✓ Description saved")

    # Scheduling is a publishing decision. Ask only after all reusable content
    # checkpoints have been loaded so a resumed run is visibly resumed first.
    if (
        publish_schedule is None
        and existing_episode is None
        and args.schedule_at is None
        and args.podbean_status == "ask"
        and should_prompt_for_schedule(episode_plan.anchor_datetime)
    ):
        publish_schedule = prompt_schedule_after_anchor(
            episode_plan.anchor_episode or {},
            episode_plan.anchor_datetime,
        )
        if publish_schedule:
            print(f"✓ Episode will be published on: {publish_schedule.display}")
        else:
            print("✓ No schedule selected; choose draft or immediate publication next")

    full_title = f"#{episode_number} - {title}"

    extended_description = (
        f"{description}<p>&nbsp;</p>"
        "<p>We are always happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.</p>"
        "<p><a href='https://www.linkedin.com/company/devsecops-talks/'>DevSecOps Talks podcast LinkedIn page</a></p>"
        "<p><a href='https://devsecops.fm/'>DevSecOps Talks podcast website</a></p>"
        "<p><a href='https://youtube.com/channel/UCRjpE9xKxZeBkRgYiLErEjw'>DevSecOps Talks podcast YouTube channel</a></p>"
    )
    if existing_episode:
        podbean_status = str(existing_episode.get("status") or "existing")
    else:
        if publish_schedule and args.podbean_status == "draft":
            print("Error: --schedule-at cannot be combined with --podbean-status draft")
            sys.exit(1)
        if publish_schedule:
            podbean_status = "publish"
        else:
            podbean_status = resolve_podbean_episode_status(args.podbean_status)

    if existing_episode:
        print(f"\n✓ Reusing existing Podbean {_episode_display_title(existing_episode)}")
        podbean_id = podbean_player_id(existing_episode)
    else:
        if args.episode_number is not None:
            print(f"\nNo existing Podbean episode #{episode_number}; creating it.")
        else:
            print("\nUploading audio to Podbean...")
        file_size = os.path.getsize(audio_path)
        episode_file_name_mp3 = f"{episode_number:03d}-{title_to_url_safe(title)}.mp3"
        media_key = ""
        if os.path.isfile(podbean_upload_checkpoint):
            try:
                with open(podbean_upload_checkpoint, "r", encoding="utf-8") as f:
                    saved_upload = json.load(f)
                if (
                    saved_upload.get("filename") == episode_file_name_mp3
                    and saved_upload.get("filesize") == file_size
                ):
                    media_key = str(saved_upload.get("media_key") or "")
            except (OSError, ValueError, TypeError):
                media_key = ""
        if media_key:
            print(f"✓ Reusing previously uploaded Podbean audio: {episode_file_name_mp3}")
        else:
            presigned_url_response = get_podbean_upload_link(
                auth_token, episode_file_name_mp3, file_size
            )
            presigned_url = presigned_url_response["presigned_url"]
            media_key = presigned_url_response["file_key"]
            print(f"Uploading {episode_file_name_mp3} ({file_size / (1024*1024):.1f} MB)...")
            upload_file_to_podbean(presigned_url, audio_path)
            with open(podbean_upload_checkpoint, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "filename": episode_file_name_mp3,
                        "filesize": file_size,
                        "media_key": media_key,
                    },
                    f,
                )
            print("✓ Audio uploaded and checkpointed")

        create_episode_response = create_podbean_episode(
            auth_token,
            full_title,
            extended_description,
            episode_number,
            media_key=media_key,
            status=podbean_creation_status(podbean_status, publish_schedule),
            publish_timestamp=publish_schedule.podbean_timestamp if publish_schedule else None,
        )
        if args.verbose:
            print(create_episode_response)
        podbean_id = podbean_player_id(create_episode_response)
        if os.path.isfile(podbean_upload_checkpoint):
            os.remove(podbean_upload_checkpoint)
    if publish_schedule:
        print(f"✓ Podbean player id: {podbean_id} (scheduled {publish_schedule.display})")
    else:
        print(f"✓ Podbean player id: {podbean_id} ({podbean_status})")

    # YouTube: plain text with URLs on their own lines (not HTML→text), so links are not visually cut off with …
    youtube_description_text = build_youtube_description_plain(description, episode_number, title)
    yt_desc_path = f"{out_base}-youtube-description.txt"
    with open(yt_desc_path, "w", encoding="utf-8") as f:
        f.write(youtube_description_text)
        f.write("\n")
    print(f"✓ YouTube description saved to {yt_desc_path}")

    # YouTube
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
        print(
            f"✓ YouTube embed present; removing R2 staging marker and object ({youtube_staging_marker})"
        )
        remove_r2_youtube_staging_marker(youtube_staging_marker)
    if youtube_embed_url and os.path.isfile(youtube_scheduled_file):
        os.unlink(youtube_scheduled_file)

    video_source = None
    if not youtube_embed_url and not youtube_scheduled and not args.skip_youtube_upload:
        override = (args.youtube_video_url or os.environ.get("UPLOAD_POST_VIDEO_URL") or "").strip()
        if override:
            video_source = override
            print(f"\nUsing --youtube-video-url for upload-post: {video_source[:90]}…")
        else:
            video_source = args.video or find_companion_video(audio_path)
            if video_source and not str(video_source).lower().startswith(("http://", "https://")):
                if not os.path.isfile(video_source):
                    print(f"⚠ Video path not found: {video_source}")
                    video_source = None

    if not youtube_embed_url and video_source and os.environ.get("UPLOAD_POST_API_KEY") and os.environ.get(
        "UPLOAD_POST_USER"
    ):
        print(f"\nUploading video to YouTube via upload-post: {video_source}")
        video_for_upload = video_source
        is_url = str(video_source).lower().startswith(("http://", "https://"))
        try:
            if not is_url and os.path.isfile(video_source) and wants_r2_staging_for_local_video(
                video_source, args
            ):
                if not r2_public_uploads_configured():
                    print(
                        "Error: R2 staging is required for this local video (size >= "
                        f"{os.environ.get('YOUTUBE_VIDEO_R2_THRESHOLD_MB', '400')} MB or --youtube-via-r2) "
                        "but R2 is not fully configured. Set R2_PUBLIC_URL and R2_ACCOUNT_ID, "
                        "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (see tools/README.md). "
                        "Or pass --youtube-no-r2-staging to allow direct upload-post (fragile for large files)."
                    )
                    sys.exit(1)
                threshold = int(os.environ.get("YOUTUBE_VIDEO_R2_THRESHOLD_MB", "400"))
                mb = os.path.getsize(video_source) / (1024 * 1024)
                if getattr(args, "youtube_via_r2", False):
                    print("R2 staging: forced via --youtube-via-r2")
                elif mb >= threshold:
                    print(f"R2 staging: auto ({mb:.0f} MB >= {threshold} MB)")
                cached_stage = load_r2_youtube_staging_marker(youtube_staging_marker, episode_number)
                if cached_stage:
                    video_for_upload, _ = cached_stage
                    preview = (
                        video_for_upload
                        if len(video_for_upload) <= 90
                        else video_for_upload[:88] + "…"
                    )
                    print(
                        f"✓ Reusing R2-staged video from {youtube_staging_marker} "
                        f"(no re-upload to R2): {preview}"
                    )
                else:
                    staged = upload_staging_video_to_r2(video_source, episode_number, verbose=args.verbose)
                    if not staged:
                        print(
                            "Error: R2 staging upload failed; refusing direct upload to upload-post. "
                            "Fix R2 credentials/bucket or use --youtube-video-url / UPLOAD_POST_VIDEO_URL "
                            "with a public HTTPS URL, or --youtube-no-r2-staging if you accept direct upload."
                        )
                        sys.exit(1)
                    video_for_upload, new_key = staged
                    save_r2_youtube_staging_marker(
                        youtube_staging_marker,
                        video_for_upload,
                        new_key,
                        episode_number,
                    )

            yt_title = f"DEVSECOPS Talks {full_title}"
            status = upload_to_youtube(
                video_for_upload,
                yt_title,
                youtube_description_text,
                scheduled_date=publish_schedule.upload_post_scheduled_date if publish_schedule else None,
                schedule_timezone=publish_schedule.upload_post_timezone if publish_schedule else None,
            )
            youtube_embed_url = status_to_youtube_embed_url(status) or ""
            youtube_job_id = scheduled_upload_job_id(status)
            if youtube_embed_url:
                print(f"✓ YouTube embed URL: {youtube_embed_url}")
                with open(youtube_url_file, "w", encoding="utf-8") as f:
                    f.write(youtube_embed_url + "\n")
                remove_r2_youtube_staging_marker(youtube_staging_marker)
            elif youtube_job_id:
                youtube_scheduled = True
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
                    print(
                        f"  R2 staging marker kept until the scheduled video is published: {youtube_staging_marker}"
                    )
            else:
                yt_err = (
                    youtube_status_error_message(status)
                    if isinstance(status, dict)
                    else None
                )
                if yt_err:
                    print(f"⚠ YouTube did not publish a video: {yt_err}")
                else:
                    print(
                        "⚠ Upload-post job completed but no YouTube embed URL was found "
                        "(see response above)."
                    )
                print(
                    f"  Staged MP4 kept on R2 for retry; URL and key in {youtube_staging_marker}. "
                    "Re-run after fixing upload-post / YouTube, or add the embed URL to "
                    f"{youtube_url_file} — staging is removed only after a successful embed URL is saved."
                )
                sys.exit(1)
        except Exception as e:
            print("Error: YouTube upload failed:")
            for line in str(e).splitlines():
                print(f"  {line}")
            if os.path.isfile(youtube_staging_marker):
                print(
                    f"  Staged MP4 kept on R2 for retry; URL and key in {youtube_staging_marker}"
                )
            sys.exit(1)
    elif video_source and not youtube_embed_url:
        print(
            "\n⚠ UPLOAD_POST_API_KEY / UPLOAD_POST_USER not set — skipping YouTube upload. "
            "Use --youtube with embed URL or configure env."
        )
    elif not video_source and not youtube_embed_url and not youtube_scheduled:
        print("\nNo companion video — skipping YouTube upload.")

    video_id = resolve_youtube_video_id(youtube_embed_url)

    episode_path = write_episode_markdown(
        episode_number,
        title,
        description,
        article_md,
        podbean_id,
        video_id,
        participants=_participants_for_episode(getattr(args, "participants", None), guest_context),
        publish_datetime=publish_schedule.podbean_datetime if publish_schedule else None,
    )
    print(f"✓ Episode page: {episode_path}")

    print(f"\n{'='*60}")
    print(f"Episode #{episode_number} complete.")
    print(f"{'='*60}")


def main():
    args = parse_args()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    # Stage downloads into raw/ unless an explicit file path was given.
    if not (args.filename or args.audio):
        stage_downloads_to_raw()

    audio_paths = _collect_audio_paths(args)
    if len(audio_paths) > 1 and args.episode_number is not None:
        print("Error: --episode-number cannot be combined with multiple input files")
        sys.exit(1)
    for ap in audio_paths:
        process_audio(ap, args, client)


if __name__ == "__main__":
    main()
