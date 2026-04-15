#!/usr/bin/env python3
"""
Write progress marker files under tools/out/ so reruns skip steps (e.g. cached YouTube embed).

Example:

  uv run python seed_progress_markers.py \\
    --episode 97 \\
    --youtube-embed-url "https://www.youtube.com/embed/VIDEO_ID"

Or use --stem episode097 to match tools/out/episode097-* checkpoint files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
OUT_DIR = TOOLS_DIR / "out"


def main() -> None:
    p = argparse.ArgumentParser(description="Create out/ progress marker files for a pipeline run")
    p.add_argument(
        "--stem",
        default=None,
        help="Checkpoint basename without suffix (e.g. episode097). Mutually exclusive with --episode.",
    )
    p.add_argument(
        "--episode",
        type=int,
        default=None,
        help="Episode number; writes episodeNNN-youtube-url.txt (same as podbean.py out/ files).",
    )
    p.add_argument(
        "--youtube-embed-url",
        help="YouTube iframe URL (writes {stem}-youtube-url.txt)",
    )
    args = p.parse_args()

    if not args.youtube_embed_url:
        p.error("Specify --youtube-embed-url")

    if args.episode is not None and args.stem is not None:
        p.error("Use either --episode or --stem, not both")
    if args.episode is None and args.stem is None:
        p.error("Specify --episode N or --stem episodeNNN")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.episode is not None:
        stem = f"episode{args.episode:03d}"
    else:
        stem = args.stem

    path = OUT_DIR / f"{stem}-youtube-url.txt"
    path.write_text(args.youtube_embed_url.strip() + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
