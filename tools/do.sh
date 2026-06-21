#!/usr/bin/env bash
set -euo pipefail

# Warm up 1Password auth (optional; comment out if not using op)
op signin

if ! command -v uv &>/dev/null; then
  echo "uv not found. Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv sync

# Staging of ~/Downloads/*.{mp3,mp4} into raw/ now happens inside podbean.py
# (see stage_downloads_to_raw): re-run-safe and prompts when raw/ already holds files.

# --no-masking: otherwise op conceals stdout/stderr substrings that match injected
# secrets (e.g. “DevSecOps …” in title options). Alternative: export OP_RUN_NO_MASKING=1.
op run --no-masking --env-file="./.env" -- uv run python3 -u podbean.py "$@"
