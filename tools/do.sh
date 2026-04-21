#!/usr/bin/env bash
set -euo pipefail

# Warm up 1Password auth (optional; comment out if not using op)
op whoami

if ! command -v uv &>/dev/null; then
  echo "uv not found. Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv sync

mv ~/Downloads/*.mp3 raw/
mv ~/Downloads/*.mp4 raw/

op run --env-file="./.env" -- uv run python3 -u podbean.py "$@"