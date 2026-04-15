#!/usr/bin/env python3
"""
Generate SEO-friendly articles from podcast episodes (legacy tool).

Prefer the main pipeline in podbean.py with tools/raw/ and tools/out/, Claude+Codex
review loop, and Codex title/description picks.

This script still: fetches audio from Podbean (or local), transcribes, GPT draft,
single Claude review, checkpoints as episode{NNN}-* in the current working directory,
and can append to content/episodes/.
"""

import os
import re
import sys
import glob
import json
import shutil
import argparse
import subprocess

# Force unbuffered output so progress shows in real time
sys.stdout.reconfigure(line_buffering=True)
import requests
from openai import OpenAI

from podbean import (
    get_podbean_auth_token,
    compress_audio_for_transcription,
    update_podbean_episode,
)

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "..", "content", "episodes")

# Load podcast context from external file
PODCAST_CONTEXT_FILE = os.path.join(os.path.dirname(__file__), "podcast-context.md")
with open(PODCAST_CONTEXT_FILE, "r", encoding="utf-8") as _f:
    PODCAST_CONTEXT = _f.read()

DRAFT_SYSTEM_PROMPT = f"""\
You are a skilled technical writer converting a podcast transcript into an article.

{PODCAST_CONTEXT}

Additional guidelines for the draft:
- Extract the main speaking points as article sections
- Identify "spicy moments": strong opinions, disagreements, surprising takes, or humor
- Leave the ## Resources section empty — it will be filled during the review pass.
"""

CLAUDE_REVIEW_PROMPT = f"""\
You are reviewing a draft article generated from a podcast transcript.

{PODCAST_CONTEXT}

Your job is to improve the draft by:

1. ACCURACY: Cross-reference every claim in the draft against the transcript.
   Fix any incorrect statements, misattributions, or fabricated content.
2. GAPS: Identify important points from the transcript that the draft missed.
   Add them as new sections or expand existing ones.
3. NARRATIVE: Improve flow, readability, and transitions between sections.
4. HIGHLIGHTS: Keep and enhance the spicy moments. If the draft missed good ones,
   add them with proper speaker attribution.
5. RESOURCES: Use web search to find 3-8 relevant articles, docs, or tools
   mentioned in or related to the topics discussed. Add them to the Resources
   section with brief descriptions. Validate that URLs are real and working.
6. CONTEXT: Where the hosts reference external concepts, tools, or events,
   add brief contextual notes so readers unfamiliar with them can follow along.

Output the complete improved article in markdown. Do not include any preamble,
explanation, thinking, or meta-commentary — just the article content starting
with ## Summary. Your very first line of output MUST be "## Summary".

Keep the same structure: Summary, Key Topics (with subsections), Highlights, Resources.
"""


def list_podbean_episodes(access_token, limit=100):
    """Fetch all episodes from Podbean API with pagination."""
    episodes = []
    offset = 0
    while True:
        resp = requests.get(
            "https://api.podbean.com/v1/episodes",
            params={"access_token": access_token, "offset": offset, "limit": limit},
        )
        data = resp.json()
        episodes.extend(data.get("episodes", []))
        if not data.get("has_more", False):
            break
        offset += limit
    return episodes


def find_podbean_episode(access_token, episode_number):
    """Find a specific episode by number from Podbean."""
    episodes = list_podbean_episodes(access_token)
    for ep in episodes:
        if ep.get("episode_number") == episode_number:
            return ep
    # Fallback: match by title pattern like "#96 -" or "96 -"
    for ep in episodes:
        title = ep.get("title", "")
        if re.match(rf"#?{episode_number}\b", title):
            return ep
    return None


def download_audio(url, dest_path):
    """Download audio file from URL."""
    print(f"Downloading audio from Podbean...")
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f"\r  {downloaded / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB ({pct:.0f}%)", end="")
    print(f"\n✓ Downloaded to {dest_path}")


def split_audio(audio_path, max_duration_s=1300, verbose=False):
    """Split audio into chunks under max_duration_s using ffmpeg. Returns list of chunk paths."""
    import subprocess as sp

    # Get duration
    probe = sp.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    duration = float(probe.stdout.strip())

    if duration <= max_duration_s:
        return [audio_path]

    num_chunks = int(duration // max_duration_s) + 1
    chunk_len = int(duration // num_chunks) + 1
    base = os.path.splitext(audio_path)[0]
    chunks = []

    print(f"Splitting {duration:.0f}s audio into {num_chunks} chunks of ~{chunk_len}s...")
    for i in range(num_chunks):
        start = i * chunk_len
        chunk_path = f"{base}_chunk{i:02d}.mp3"
        cmd = ["ffmpeg", "-y", "-i", audio_path, "-ss", str(start),
               "-t", str(chunk_len), "-acodec", "copy", "-loglevel", "error", chunk_path]
        sp.run(cmd, check=True, capture_output=True)
        chunks.append(chunk_path)
        if verbose:
            print(f"  Chunk {i}: {start}s - {start + chunk_len}s -> {chunk_path}")

    print(f"✓ Split into {len(chunks)} chunks")
    return chunks


def transcribe_diarized(api_key, audio_path, verbose=False):
    """Transcribe with speaker diarization using gpt-4o-transcribe-diarize (streaming SSE)."""
    import httpx

    print("Transcribing with gpt-4o-transcribe-diarize (speaker diarization)...")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
    }

    chunking_strategy = json.dumps({
        "type": "server_vad",
        "prefix_padding_ms": 300,
        "silence_duration_ms": 200,
        "threshold": 0.5,
    })

    with open(audio_path, "rb") as audio_file:
        files = [
            ("file", (os.path.basename(audio_path), audio_file)),
            ("model", (None, "gpt-4o-transcribe-diarize")),
            ("language", (None, "en")),
            ("response_format", (None, "diarized_json")),
            ("chunking_strategy", (None, chunking_strategy)),
            ("stream", (None, "true")),
        ]

        timeout = httpx.Timeout(600.0, read=None)
        with httpx.Client(timeout=timeout) as http_client:
            with http_client.stream("POST", url, headers=headers, files=files) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    error_body = response.read()
                    raise RuntimeError(
                        f"Diarize API error {exc.response.status_code}: "
                        f"{error_body.decode('utf-8', errors='replace')}"
                    ) from exc

                segments = []
                full_text = ""
                pending_data = []

                for line in response.iter_lines():
                    if not line:
                        if pending_data:
                            data = "\n".join(pending_data)
                            pending_data.clear()
                            if data == "[DONE]":
                                break
                            event = json.loads(data)
                            if event["type"] == "transcript.text.segment":
                                segments.append(event)
                                if verbose:
                                    speaker = event.get("speaker", "?")
                                    print(f"  [{speaker}] {event['text'][:80]}")
                            elif event["type"] == "transcript.text.done":
                                full_text = event["text"]
                        continue

                    if line.startswith("data:"):
                        pending_data.append(line[len("data:"):].strip())

                if pending_data:
                    data = "\n".join(pending_data)
                    if data != "[DONE]":
                        event = json.loads(data)
                        if event["type"] == "transcript.text.done":
                            full_text = event["text"]

    # Build speaker-labeled transcript
    if segments:
        labeled_lines = []
        current_speaker = None
        for seg in segments:
            speaker = seg.get("speaker", "Unknown")
            text = seg.get("text", "").strip()
            if speaker != current_speaker:
                current_speaker = speaker
                labeled_lines.append(f"\n[{speaker}]: {text}")
            else:
                labeled_lines.append(f" {text}")
        transcript = "".join(labeled_lines).strip()
        print(f"✓ Diarized transcription complete ({len(segments)} segments, {len(transcript)} chars)")
        return transcript

    # Fallback to plain text if no segments
    if full_text:
        print(f"✓ Transcription complete (no segments, {len(full_text)} chars)")
        return full_text

    raise ValueError("Empty response from diarize model")


def transcribe(client, audio_path, verbose=False):
    """Transcribe audio, trying diarize first, then gpt-4o-transcribe, then whisper-1."""
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    max_size_mb = 24

    file_to_transcribe = audio_path
    cleanup_file = None

    if file_size_mb > max_size_mb:
        print(f"File size ({file_size_mb:.1f} MB) exceeds {max_size_mb} MB, compressing...")
        file_to_transcribe = compress_audio_for_transcription(audio_path, verbose=verbose)
        cleanup_file = file_to_transcribe

    # Try diarized transcription first
    try:
        chunks = split_audio(file_to_transcribe, max_duration_s=1300, verbose=verbose)
        parts = []
        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                print(f"  Processing chunk {i+1}/{len(chunks)}...")
            parts.append(transcribe_diarized(client.api_key, chunk, verbose=verbose))
            if chunk != file_to_transcribe and os.path.exists(chunk):
                os.remove(chunk)
        transcript = "\n\n".join(parts)
        if cleanup_file and os.path.exists(cleanup_file):
            os.remove(cleanup_file)
        print(f"✓ Total transcript: {len(transcript)} chars")
        return transcript
    except Exception as e:
        print(f"⚠ Diarize failed: {e}")
        print("Falling back to standard transcription...")

    # Fallback to standard models
    upload_client = OpenAI(
        api_key=client.api_key,
        timeout=600.0,
        max_retries=3,
    )

    for model in ["gpt-4o-transcribe", "whisper-1"]:
        print(f"Transcribing with {model}...")
        try:
            with open(file_to_transcribe, "rb") as f:
                transcript = upload_client.audio.transcriptions.create(
                    model=model,
                    file=f,
                    response_format="text",
                    language="en",
                    prompt="DevSecOps Talks podcast. Hosts: Andrey Devyatkin, Mattias Hemmingsson, Paulina Dubas. Former host: Julien Bisconti. Companies: FivexL, Dubas Consulting, Sirob Technologies, Boris, Hacking Robots and Beer. Topics: AWS, Kubernetes, Terraform, HashiCorp Vault, CI/CD, Jenkins, GitOps, Argo CD, CloudFormation, IAM, SSO Elevator, Control Tower, GuardDuty, CloudTrail, ECS, EKS, SOC2, HIPAA, PCI DSS.",
                )
            break
        except Exception as e:
            if model == "gpt-4o-transcribe":
                print(f"⚠ {model} failed ({e}), falling back to whisper-1...")
                continue
            raise

    if cleanup_file and os.path.exists(cleanup_file):
        os.remove(cleanup_file)

    print(f"✓ Transcription complete ({len(transcript)} chars)")
    return transcript


def generate_draft(client, transcript, verbose=False):
    """Generate article draft using GPT-5.4."""
    print("Generating article draft with GPT-5.4...")
    response = client.responses.create(
        model="gpt-5.4",
        instructions=DRAFT_SYSTEM_PROMPT,
        input=f"Here is the podcast transcript:\n\n{transcript}",
        max_output_tokens=8000,
    )
    draft = response.output_text
    if not draft:
        raise ValueError("Empty response from GPT-5.4")
    if verbose:
        print(f"Draft length: {len(draft)} chars")
    print("✓ Draft generated")
    return draft


def review_with_claude(transcript, draft, verbose=False):
    """Review and enrich draft using Claude CLI with web search."""
    if not shutil.which("claude"):
        print("Error: 'claude' CLI not found. Install Claude Code to use the review step.")
        print("Skipping review — using draft as-is.")
        return draft

    print("Reviewing draft with Claude (Opus 4.6)...")

    # Build the prompt with both transcript and draft
    prompt = f"""{CLAUDE_REVIEW_PROMPT}

--- ORIGINAL TRANSCRIPT ---
{transcript}

--- DRAFT ARTICLE ---
{draft}
"""

    # Pipe the full content via stdin, with -p providing the instruction
    cmd = [
        "claude",
        "--print",
        "--model", "opus",
        "--allowedTools", "WebSearch", "WebFetch",
        "-p", "Process the input provided on stdin.",
    ]

    if verbose:
        print(f"Running claude CLI...")
        print(f"Prompt length: {len(prompt)} chars")

    result = subprocess.run(
        cmd,
        input=prompt,
        stdout=subprocess.PIPE,
        stderr=None,  # let stderr pass through to terminal in real time
        text=True,
        timeout=600,  # 10 min timeout for web search
    )

    if verbose:
        print(f"Exit code: {result.returncode}")
        print(f"stdout length: {len(result.stdout)}")

    if result.returncode != 0:
        print(f"Claude review failed (exit {result.returncode})")
        print(f"stdout: {result.stdout[:2000]}")
        sys.exit(1)

    article = result.stdout.strip()
    if not article:
        print("Claude returned empty response")
        sys.exit(1)

    # Strip any thinking/preamble before the actual article
    summary_marker = "## Summary"
    if summary_marker in article:
        # Keep only the last occurrence (Claude sometimes outputs multiple drafts)
        parts = article.split(summary_marker)
        article = summary_marker + parts[-1]
    else:
        print(f"Claude output missing '## Summary' — got:\n{article[:500]}")
        sys.exit(1)

    # Sanity check: article should be substantial
    if len(article) < 500:
        print(f"Claude output too short ({len(article)} chars) — likely incomplete:\n{article[:500]}")
        sys.exit(1)

    print(f"✓ Review complete ({len(article)} chars)")
    return article


def find_episode_file(episode_number):
    """Find the markdown file for a given episode number."""
    pattern = os.path.join(CONTENT_DIR, f"{episode_number:03d}-*.md")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    # Also try without zero-padding
    pattern = os.path.join(CONTENT_DIR, f"{episode_number}-*.md")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return None


def append_article_to_episode(episode_file, article):
    """Replace ## Notes (if present) or append article at end of episode markdown."""
    with open(episode_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove existing ## Notes section and anything after it
    notes_marker = "## Notes"
    if notes_marker in content:
        idx = content.index(notes_marker)
        content = content[:idx].rstrip() + "\n\n"

    # Append article at end
    new_content = content.rstrip() + "\n\n" + article + "\n"

    with open(episode_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✓ Article written to {episode_file}")


def markdown_to_html(md_text):
    """Convert markdown to HTML for Podbean."""
    import markdown
    return markdown.markdown(md_text, extensions=["extra", "sane_lists"])


def update_podbean_description(access_token, episode_number, article, existing_content, verbose=False):
    """Update Podbean episode description with the article content."""
    episodes = list_podbean_episodes(access_token)
    episode = None
    for ep in episodes:
        if ep.get("episode_number") == episode_number:
            episode = ep
            break
    if not episode:
        for ep in episodes:
            if re.match(rf"#?{episode_number}\b", ep.get("title", "")):
                episode = ep
                break

    if not episode:
        print(f"⚠ Episode {episode_number} not found on Podbean, skipping update")
        return

    article_html = markdown_to_html(article)
    new_content = f"{existing_content}<hr/>{article_html}"

    if verbose:
        print(f"Updating Podbean episode {episode['id']} ({len(new_content)} chars)")

    result = update_podbean_episode(
        access_token, episode["id"], new_content,
        title=episode["title"],
        status=episode.get("status", "publish"),
        type=episode.get("type", "public"),
    )
    if "episode" in result:
        print(f"✓ Podbean episode description updated")
    else:
        print(f"⚠ Podbean update response: {result}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate SEO-friendly articles from podcast episodes"
    )
    parser.add_argument(
        "-e", "--episode", type=int, required=True,
        help="Episode number to process",
    )
    parser.add_argument(
        "-t", "--transcript", type=str, default=None,
        help="Path to existing transcript file (skips transcription)",
    )
    parser.add_argument(
        "-a", "--audio", type=str, default=None,
        help="Path to local audio file (skips Podbean download)",
    )
    parser.add_argument(
        "--draft-only", action="store_true",
        help="Stop after generating the draft (skip Claude review)",
    )
    parser.add_argument(
        "--skip-draft", action="store_true",
        help="Skip draft generation, review existing draft with Claude",
    )
    parser.add_argument(
        "--no-append", action="store_true",
        help="Don't append to episode file, just save the article",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose output",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    ep_num = args.episode

    # Initialize OpenAI client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    transcript_file = f"episode{ep_num:03d}.txt"
    draft_file = f"episode{ep_num:03d}-draft.md"
    article_file = f"episode{ep_num:03d}-article.md"

    step = 0
    total_steps = 5 - (1 if args.draft_only else 0) - (1 if args.skip_draft else 0)

    def progress(msg):
        nonlocal step
        step += 1
        print(f"\n[{step}/{total_steps}] {msg}")

    # Step 1: Get transcript
    transcript = None
    if args.transcript:
        progress("Loading transcript...")
        with open(args.transcript, "r", encoding="utf-8") as f:
            transcript = f.read()
        print(f"✓ Loaded from {args.transcript}")
    elif os.path.exists(transcript_file):
        progress("Loading existing transcript...")
        with open(transcript_file, "r", encoding="utf-8") as f:
            transcript = f.read()
        print(f"✓ Loaded from {transcript_file}")
    else:
        progress("Getting audio and transcribing...")

        audio_path = args.audio

        if not audio_path:
            audio_path = f"episode{ep_num:03d}.mp3"

            if os.path.exists(audio_path):
                print(f"✓ Reusing existing {audio_path}")
            else:
                # Download from Podbean
                client_id = os.environ.get("PODBEAN_CLIENT_ID")
                client_secret = os.environ.get("PODBEAN_CLIENT_SECRET")
                if not client_id or not client_secret:
                    print("Error: PODBEAN_CLIENT_ID and PODBEAN_CLIENT_SECRET required for download")
                    sys.exit(1)

                auth_token = get_podbean_auth_token(client_id, client_secret)
                episode = find_podbean_episode(auth_token, ep_num)
                if not episode:
                    print(f"Error: Episode {ep_num} not found on Podbean")
                    sys.exit(1)

                media_url = episode.get("media_url")
                if not media_url:
                    print(f"Error: No media URL for episode {ep_num}")
                    sys.exit(1)

                print(f"Found: {episode.get('title', 'Unknown')}")
                download_audio(media_url, audio_path)

        transcript = transcribe(client, audio_path, verbose=args.verbose)

        # Save transcript
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript)
        print(f"✓ Transcript saved to {transcript_file}")

    # Step 2: Generate draft
    draft = None
    if args.skip_draft:
        if os.path.exists(draft_file):
            with open(draft_file, "r", encoding="utf-8") as f:
                draft = f.read()
            print(f"✓ Loaded existing draft from {draft_file}")
        else:
            print(f"Error: --skip-draft specified but {draft_file} not found")
            sys.exit(1)
    elif os.path.exists(draft_file):
        progress("Loading existing draft...")
        with open(draft_file, "r", encoding="utf-8") as f:
            draft = f.read()
        print(f"✓ Loaded from {draft_file}")
    else:
        progress("Generating article draft...")
        draft = generate_draft(client, transcript, verbose=args.verbose)
        with open(draft_file, "w", encoding="utf-8") as f:
            f.write(draft)
        print(f"✓ Draft saved to {draft_file}")

    if args.draft_only:
        print(f"\n{'='*60}")
        print(f"Draft complete for episode {ep_num}: {draft_file}")
        print(f"{'='*60}")
        return

    # Step 3: Review with Claude
    if os.path.exists(article_file):
        progress("Loading existing article...")
        with open(article_file, "r", encoding="utf-8") as f:
            article = f.read()
        print(f"✓ Loaded from {article_file}")
    else:
        progress("Reviewing and enriching with Claude...")
        article = review_with_claude(transcript, draft, verbose=args.verbose)
        with open(article_file, "w", encoding="utf-8") as f:
            f.write(article)
        print(f"✓ Article saved to {article_file}")

    # Step 4: Append to episode file
    if not args.no_append:
        progress("Appending to episode file...")
        episode_file = find_episode_file(ep_num)
        if episode_file:
            append_article_to_episode(episode_file, article)
        else:
            print(f"⚠ Episode file not found for episode {ep_num}")
            print(f"  Article saved to {article_file} — append manually.")

    print(f"\n{'='*60}")
    print(f"Article complete for episode {ep_num}")
    print(f"{'='*60}")

    # Step 5: Update Podbean description
    progress("Updating Podbean episode description...")
    client_id = os.environ.get("PODBEAN_CLIENT_ID")
    client_secret = os.environ.get("PODBEAN_CLIENT_SECRET")
    if client_id and client_secret:
        auth_token = get_podbean_auth_token(client_id, client_secret)
        pb_episode = find_podbean_episode(auth_token, ep_num)
        existing_content = pb_episode.get("content", "") if pb_episode else ""
        update_podbean_description(auth_token, ep_num, article, existing_content, verbose=args.verbose)
    else:
        print("⚠ PODBEAN_CLIENT_ID/SECRET not set, skipping Podbean update")

    print(f"\n{'='*60}")
    print(f"All done for episode {ep_num}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
