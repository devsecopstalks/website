#!/usr/bin/env python3

import os
import re
import argparse
import requests
import mimetypes
import datetime
import sys
import tempfile
import subprocess
import shutil
import math
from pathlib import Path
from openai import OpenAI

from episode_pipeline import (
    generate_article,
    load_raw_companion_markdown,
    pick_description,
    pick_title,
)
from r2_staging import (
    delete_r2_object,
    upload_staging_video_to_r2,
    use_r2_staging_for_local_video,
)
from youtube import (
    status_to_youtube_embed_url,
    upload_to_youtube,
    youtube_embed_url_to_video_id,
)

# Podbean API docs
# https://developers.podbean.com/podbean-api-docs/

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(TOOLS_DIR, "raw")
OUT_DIR = os.path.join(TOOLS_DIR, "out")
EPISODES_DIR = os.path.join(TOOLS_DIR, "..", "content", "episodes")

# Default Hugo front matter when --participants is omitted (current hosts).
DEFAULT_PARTICIPANTS = ["Paulina", "Mattias", "Andrey"]


def checkpoint_prefix(episode_number: int) -> str:
    """Basename for tools/out/ files, e.g. episode097 (matches Podbean episode index)."""
    return f"episode{episode_number:03d}"


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


def build_youtube_description_plain(teaser: str, episode_number: int, title_short: str) -> str:
    """
    Plain-text description for upload-post → YouTube.

    Uses short labels with **full URL on the following line** so the YouTube app
    shows complete clickable links (it often truncates long single-line URLs with …).
    """
    slug = title_to_url_safe(title_short)
    episode_url = f"https://devsecops.fm/episodes/{episode_number:03d}-{slug}/"
    lines = [
        teaser.strip(),
        "",
        "We are always happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.",
        "",
        "Podcast website",
        "https://devsecops.fm/",
        "",
        "LinkedIn",
        "https://www.linkedin.com/company/devsecops-talks/",
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
    esc = [p.replace("\\", "\\\\").replace('"', '\\"') for p in participants]
    inner = ", ".join(f'"{x}"' for x in esc)
    return f"participants: [{inner}]"


def write_episode_markdown(
    episode_number: int,
    title_short: str,
    description: str,
    article_md: str,
    podbean_id: str,
    youtube_video_id: str,
    participants: list[str] | None = None,
) -> str:
    """Write Hugo episode page; mirrors published episode layout."""
    participants = participants if participants is not None else list(DEFAULT_PARTICIPANTS)
    full_title = f"#{episode_number} - {title_short}"
    slug = title_to_url_safe(title_short)
    filename = f"{episode_number:03d}-{slug}.md"
    path = os.path.join(EPISODES_DIR, filename)
    date_iso = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
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
    Compress audio file using ffmpeg to reduce file size for Whisper API.
    
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
    Transcribe an audio file using OpenAI Whisper API.
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
                    model="gpt-4o-transcribe",
                    file=audio_file,
                    response_format="text",
                    language="en",
                    prompt=_TRANSCRIPTION_PROMPT,
                )

        print("Using OpenAI Whisper API...")

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
        return requests.put(
            url,
            headers={"Content-Type": mimetypes.guess_type(filepath)[0]},
            data=f,
        )

# convert title into url safe string
def title_to_url_safe(title):
    return re.sub(r"[^0-9a-zA-Z]+", "-", title).lower()

# get last episode number by getting all episodes till there are no more left
# curl https://api.podbean.com/v1/episodes -G -d 'access_token=YOUR_ACCESS_TOKEN' -d 'offset=0' -d 'limit=10'
def get_last_episode_number(access_token, url="https://api.podbean.com/v1/episodes"):
    response = requests.get(url, params={"access_token": access_token, "limit": 100})
    return response.json()["count"]

# create new podbean episode
# curl https://api.podbean.com/v1/episodes -X POST -d access_token=YOUR_ACCESS_TOKEN -d title="Good day" \
# -d content="Time you <b>enjoy</b> wasting, was not wasted." -d status=publish -d type=public \
# -d media_key=audio.mp3 -d logo_key=logo.jpg -d transcripts_key=transcripts.srt -d season_number=1
# -d episode_number=1 -d apple_episode_type=full -d publish_timestamp=1667850511 -d content_explicit=clean
def create_podbean_episode(
        access_token, title, content, episode_number, media_key=None, status="draft", type="public",
        url="https://api.podbean.com/v1/episodes"):
    response = requests.post(
        url,
        data={"access_token": access_token, "title": title,
              "content": content, "status": status, "type": type,
              "media_key": media_key, "episode_number": episode_number}
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

    print("Authenticating with Podbean...")
    auth_token = get_podbean_auth_token(client_id, client_secret)
    print("✓ Authenticated")

    episode_number = int(get_last_episode_number(auth_token)) + 1
    print(f"✓ Next episode number (from Podbean): {episode_number}")

    out_base = os.path.join(OUT_DIR, checkpoint_prefix(episode_number))
    print(f"✓ Checkpoints under: {out_base}-*.txt|.md")

    transcript_file = f"{out_base}.txt"
    title_file = f"{out_base}-title.txt"
    description_file = f"{out_base}-description.txt"
    guidance_file = f"{out_base}-guidance.txt"
    youtube_url_file = f"{out_base}-youtube-url.txt"

    participants = _parse_participants_arg(getattr(args, "participants", None))

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

    article_md = generate_article(
        transcript,
        out_base,
        editorial_guidance=guidance,
        raw_notes=raw_notes,
        verbose=args.verbose,
    )

    if args.draft_only:
        print(f"\nDraft-only: done. Article: {out_base}-article.md")
        return

    # Title
    title = (args.title or "").strip() or None
    if not title and os.path.exists(title_file):
        with open(title_file, "r", encoding="utf-8") as f:
            saved_t = f.read().strip()
        print(f'\nFound saved title: "{saved_t}"')
        print("Press Enter to reuse, or type 'new' to pick again: ", end="", flush=True)
        if input().strip().lower() != "new":
            title = saved_t
    if not title:
        title = pick_title(article_md, editorial_guidance=guidance, verbose=args.verbose)
    with open(title_file, "w", encoding="utf-8") as f:
        f.write(title)
    print(f"✓ Title: {title}")

    # Short teaser description (Podbean + above-the-fold)
    description = (args.description or "").strip() or None
    if not description and os.path.exists(description_file):
        with open(description_file, "r", encoding="utf-8") as f:
            saved_d = f.read().strip()
        print(f"\nFound saved description ({len(saved_d)} chars). Press Enter to reuse, or 'new': ", end="", flush=True)
        if input().strip().lower() != "new":
            description = saved_d
    if not description:
        description = pick_description(article_md, editorial_guidance=guidance, verbose=args.verbose)
    with open(description_file, "w", encoding="utf-8") as f:
        f.write(description)
    print("✓ Description saved")

    full_title = f"#{episode_number} - {title}"

    # Podbean upload
    print("\nUploading audio to Podbean...")
    file_size = os.path.getsize(audio_path)
    episode_file_name_mp3 = f"{episode_number:03d}-{title_to_url_safe(title)}.mp3"
    presigned_url_response = get_podbean_upload_link(auth_token, episode_file_name_mp3, file_size)
    presigned_url = presigned_url_response["presigned_url"]
    media_key = presigned_url_response["file_key"]
    print(f"Uploading {episode_file_name_mp3} ({file_size / (1024*1024):.1f} MB)...")
    upload_file_to_podbean(presigned_url, audio_path)
    print("✓ Audio uploaded")

    extended_description = (
        f"{description}<p>&nbsp;</p>"
        "<p>We are always happy to answer any questions, hear suggestions for new episodes, or hear from you, our listeners.</p>"
        "<p><a href='https://www.linkedin.com/company/devsecops-talks/'>DevSecOps Talks podcast LinkedIn page</a></p>"
        "<p><a href='https://devsecops.fm/'>DevSecOps Talks podcast website</a></p>"
        "<p><a href='https://youtube.com/channel/UCRjpE9xKxZeBkRgYiLErEjw'>DevSecOps Talks podcast YouTube channel</a></p>"
    )

    create_episode_response = create_podbean_episode(
        auth_token, full_title, extended_description, episode_number, media_key=media_key
    )
    if args.verbose:
        print(create_episode_response)

    podbean_id = create_episode_response["episode"]["player_url"].split("=")[-1]
    print(f"✓ Podbean player id: {podbean_id}")

    # YouTube: plain text with URLs on their own lines (not HTML→text), so links are not visually cut off with …
    youtube_description_text = build_youtube_description_plain(description, episode_number, title)
    yt_desc_path = f"{out_base}-youtube-description.txt"
    with open(yt_desc_path, "w", encoding="utf-8") as f:
        f.write(youtube_description_text)
        f.write("\n")
    print(f"✓ YouTube description saved to {yt_desc_path}")

    # YouTube
    youtube_embed_url = (args.youtube or "").strip()
    if not youtube_embed_url and os.path.exists(youtube_url_file):
        with open(youtube_url_file, "r", encoding="utf-8") as f:
            youtube_embed_url = f.read().strip()
        if youtube_embed_url:
            print(f"✓ Loaded YouTube embed URL from {youtube_url_file}")

    video_source = None
    if not youtube_embed_url and not args.skip_youtube_upload:
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

    r2_staging_key = None
    if not youtube_embed_url and video_source and os.environ.get("UPLOAD_POST_API_KEY") and os.environ.get(
        "UPLOAD_POST_USER"
    ):
        print(f"\nUploading video to YouTube via upload-post: {video_source}")
        video_for_upload = video_source
        is_url = str(video_source).lower().startswith(("http://", "https://"))
        try:
            if not is_url and os.path.isfile(video_source) and use_r2_staging_for_local_video(video_source, args):
                threshold = int(os.environ.get("YOUTUBE_VIDEO_R2_THRESHOLD_MB", "400"))
                mb = os.path.getsize(video_source) / (1024 * 1024)
                if getattr(args, "youtube_via_r2", False):
                    print("R2 staging: forced via --youtube-via-r2")
                elif mb >= threshold:
                    print(f"R2 staging: auto ({mb:.0f} MB >= {threshold} MB)")
                staged = upload_staging_video_to_r2(video_source, episode_number, verbose=args.verbose)
                if staged:
                    video_for_upload, r2_staging_key = staged
                else:
                    print("⚠ R2 staging failed — falling back to direct upload to upload-post")

            yt_title = f"DEVSECOPS Talks {full_title}"
            status = upload_to_youtube(video_for_upload, yt_title, youtube_description_text)
            youtube_embed_url = status_to_youtube_embed_url(status) or ""
            if youtube_embed_url:
                print(f"✓ YouTube embed URL: {youtube_embed_url}")
                with open(youtube_url_file, "w", encoding="utf-8") as f:
                    f.write(youtube_embed_url + "\n")
            else:
                print("⚠ Could not parse YouTube URL from upload-post; use --youtube with embed URL")
        except Exception as e:
            print(f"⚠ YouTube upload failed: {e}")
        finally:
            if r2_staging_key:
                delete_r2_object(r2_staging_key, verbose=args.verbose)
    elif video_source and not youtube_embed_url:
        print(
            "\n⚠ UPLOAD_POST_API_KEY / UPLOAD_POST_USER not set — skipping YouTube upload. "
            "Use --youtube with embed URL or configure env."
        )
    elif not video_source and not youtube_embed_url:
        print("\nNo companion video — skipping YouTube upload.")

    video_id = resolve_youtube_video_id(youtube_embed_url)

    episode_path = write_episode_markdown(
        episode_number,
        title,
        description,
        article_md,
        podbean_id,
        video_id,
        participants=participants,
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

    audio_paths = _collect_audio_paths(args)
    for ap in audio_paths:
        process_audio(ap, args, client)


if __name__ == "__main__":
    main()