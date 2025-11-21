#!/usr/bin/env python3

source env/bin/activate

# this is to warm up 1password and make sure that the auth is there before
# we proceed
op whoami

mv ~/Downloads/*.mp3 .
mv ~/Downloads/*.mp4 .

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv sync

op run --env-file="./.env" -- python3 podbean.py -v --scan