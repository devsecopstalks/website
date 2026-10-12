#!/usr/bin/env python3
"""One-off: move the episode covers from static/images/covers/ to R2.

Uploads each NNN.png under the key the pipeline uses (covers/NNN-<digest>.png),
skipping objects already there, then points the matching ``image:`` lines in
content/episodes/*.md at the public URL. Safe to re-run. Needs the R2_* variables
from tools/.env (`op run --env-file=./.env -- uv run python3 migrate_covers_to_r2.py`);
``--dry-run`` needs only R2_PUBLIC_URL and touches nothing.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import r2_staging

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
COVERS_DIR = REPO_ROOT / "static" / "images" / "covers"
EPISODES_DIR = REPO_ROOT / "content" / "episodes"

_IMAGE_LINE = re.compile(r'^image:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)


def plan_uploads(covers_dir=COVERS_DIR):
    """[(local path, site path, R2 key)] for every NNN.png cover."""
    plan = []
    for path in sorted(Path(covers_dir).glob("*.png")):
        if re.fullmatch(r"\d+", path.stem):
            key = r2_staging.cover_r2_key(int(path.stem), path.read_bytes())
            plan.append((path, f"/images/covers/{path.name}", key))
    return plan


def rewrite_images(urls, episodes_dir=EPISODES_DIR, dry_run=False):
    """Point ``image:`` lines found in ``urls`` (site path -> URL) at the URL.

    Only the front matter is searched. Returns [(page, old, new)]; ``dry_run`` writes nothing.
    """
    edits = []
    for page in sorted(Path(episodes_dir).glob("*.md")):
        text = page.read_text(encoding="utf-8")
        end = text.find("\n---", 3) if text.startswith("---") else -1
        match = _IMAGE_LINE.search(text, 0, end) if end > 0 else None
        if not match or match.group(1) not in urls:
            continue
        old, new = match.group(1), urls[match.group(1)]
        edits.append((page, old, new))
        if not dry_run:
            page.write_text(text[: match.start()] + f'image: "{new}"' + text[match.end():], encoding="utf-8")
    return edits


def migrate(dry_run=False, covers_dir=COVERS_DIR, episodes_dir=EPISODES_DIR):
    """Check the lifecycle, upload, then rewrite; returns the process exit code."""
    if not r2_staging.R2_PUBLIC_URL:
        print("Error: R2_PUBLIC_URL is not set", file=sys.stderr)
        return 1
    s3 = None
    if not dry_run:
        try:
            s3 = r2_staging.require_cover_client()
            r2_staging.check_cover_lifecycle(s3)
        except r2_staging.R2CoverError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    urls = {}
    for path, site_path, key in plan_uploads(covers_dir):
        if dry_run:
            print(f"would upload {path.name} -> {key}")
            urls[site_path] = r2_staging.r2_public_url(key)
            continue
        try:
            urls[site_path] = r2_staging.upload_cover_to_r2(str(path), int(path.stem), s3=s3)
        except r2_staging.R2CoverError as e:
            print(f"Error: {path.name}: {e}", file=sys.stderr)
            return 1

    for page, old, new in rewrite_images(urls, episodes_dir, dry_run=dry_run):
        verb = "would rewrite" if dry_run else "✓ rewrote"
        print(f"{verb} {os.path.relpath(page, REPO_ROOT)}: {old} -> {new}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print keys and edits only")
    args = parser.parse_args(argv)
    return migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
