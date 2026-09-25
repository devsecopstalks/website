#!/usr/bin/env bash
set -euo pipefail

# The .env secrets live in this account; naming it skips op's account picker.
OP_ACCOUNT="${OP_ACCOUNT:-family-beavers.1password.com}"
export OP_ACCOUNT

# Warm up 1Password auth (optional; comment out if not using op)
op signin --account "$OP_ACCOUNT"

if ! command -v uv &>/dev/null; then
  echo "uv not found. Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv sync

# FluidAudio (local transcription: Parakeet ASR + VBx diarization) has no Homebrew
# formula, so it is built from source at a pinned commit into a dir this script
# owns (marked by .managed-build). transcribe_local.py reads the same dir.
FLUIDAUDIO_REPO="https://github.com/FluidInference/FluidAudio.git"
FLUIDAUDIO_COMMIT="667181a368da13b3a9178e310414e9dcbe8f23ce"
FLUIDAUDIO_DIR="${FLUIDAUDIO_DIR:-$HOME/.cache/fluidaudio/devsecopstalks}"

ensure_fluidaudio() {
  # Same parsing as podbean.py's transcribe_backend().
  local backend
  backend=$(printf '%s' "${TRANSCRIBE_BACKEND:-local}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
  backend="${backend:-local}"
  if [ "$backend" = "openai" ]; then
    echo "TRANSCRIBE_BACKEND=openai — skipping FluidAudio build."
    return 0
  fi
  if [ "$backend" != "local" ]; then
    echo "Error: TRANSCRIBE_BACKEND must be 'local' or 'openai', got '${TRANSCRIBE_BACKEND}'."
    exit 1
  fi
  if [ -n "${FLUIDAUDIO_CLI:-}" ]; then
    echo "FLUIDAUDIO_CLI set — skipping FluidAudio build."
    return 0
  fi

  local cli="$FLUIDAUDIO_DIR/.build/release/fluidaudiocli"
  local stamp="$FLUIDAUDIO_DIR/.build/.built-commit"

  if [ -x "$cli" ] && [ "$(cat "$stamp" 2>/dev/null)" = "$FLUIDAUDIO_COMMIT" ]; then
    return 0
  fi

  if ! command -v swift &>/dev/null; then
    echo "Error: swift not found. FluidAudio needs Swift 6.0+ (install Xcode or the Swift toolchain)."
    exit 1
  fi
  # /usr/bin/swift on macOS is an xcrun shim that exists even with no toolchain,
  # so an unparseable version means "no usable Swift", not "assume it is fine".
  local swift_major
  swift_major=$(swift --version 2>&1 | sed -n 's/.*Swift version \([0-9]*\).*/\1/p' | head -1 || true)
  if [ -z "$swift_major" ]; then
    echo "Error: could not determine the Swift version. FluidAudio needs Swift 6.0+."
    echo "  'swift --version' said: $(swift --version 2>&1 | head -1 || true)"
    echo "  Install Xcode (and run 'xcode-select --install') or the Swift toolchain."
    exit 1
  fi
  if [ "$swift_major" -lt 6 ]; then
    echo "Error: FluidAudio needs Swift 6.0+, found $(swift --version 2>&1 | head -1)."
    exit 1
  fi

  echo "Building FluidAudio @ ${FLUIDAUDIO_COMMIT:0:12} (first build takes several minutes)..."

  # The steps below rewrite origin and force-checkout a detached HEAD, so never
  # touch a non-empty directory this script did not create (no marker).
  local marker="$FLUIDAUDIO_DIR/.managed-build"
  if [ -e "$FLUIDAUDIO_DIR" ] && [ ! -e "$marker" ]; then
    if [ -n "$(ls -A "$FLUIDAUDIO_DIR" 2>/dev/null)" ]; then
      echo "Error: $FLUIDAUDIO_DIR already exists and was not created by do.sh."
      echo "  Refusing to rewrite its remote and force-checkout over it."
      echo "  Point FLUIDAUDIO_DIR at a new path, set FLUIDAUDIO_CLI to an"
      echo "  already-built fluidaudiocli, or remove the directory."
      exit 1
    fi
  fi

  mkdir -p "$FLUIDAUDIO_DIR"
  touch "$marker"
  if [ ! -d "$FLUIDAUDIO_DIR/.git" ]; then
    git -C "$FLUIDAUDIO_DIR" init -q
  fi
  # Recover from an interrupted first run (a .git with no origin) and from a
  # dir that was previously pointed at some other remote.
  git -C "$FLUIDAUDIO_DIR" remote add origin "$FLUIDAUDIO_REPO" 2>/dev/null \
    || git -C "$FLUIDAUDIO_DIR" remote set-url origin "$FLUIDAUDIO_REPO"

  # Never discard work left behind in the cache dir. The marker is expected to
  # show up as untracked; `|| true` because grep -v exits 1 on a clean tree.
  local dirty
  dirty=$(git -C "$FLUIDAUDIO_DIR" status --porcelain 2>/dev/null \
    | grep -v '^?? \.managed-build$' || true)
  if [ -n "$dirty" ]; then
    echo "Error: $FLUIDAUDIO_DIR has uncommitted changes; refusing to overwrite it."
    echo "  Commit or stash them, or point FLUIDAUDIO_DIR elsewhere, or set"
    echo "  FLUIDAUDIO_CLI to an already-built fluidaudiocli to skip this build."
    exit 1
  fi

  git -C "$FLUIDAUDIO_DIR" fetch --depth 1 -q origin "$FLUIDAUDIO_COMMIT" || {
    echo "Error: could not fetch FluidAudio commit $FLUIDAUDIO_COMMIT from $FLUIDAUDIO_REPO."
    echo "  If $FLUIDAUDIO_DIR is in a bad state, remove it and re-run."
    exit 1
  }
  git -C "$FLUIDAUDIO_DIR" checkout -q --force FETCH_HEAD

  (cd "$FLUIDAUDIO_DIR" && swift build -c release --product fluidaudiocli) || {
    echo "Error: FluidAudio build failed."
    exit 1
  }
  [ -x "$cli" ] || { echo "Error: build finished but $cli is missing."; exit 1; }
  echo "$FLUIDAUDIO_COMMIT" > "$stamp"
  echo "✓ FluidAudio built: $cli"
  echo "  Models (~685 MB) download to ~/Library/Application Support/FluidAudio/ on first run."
}

# --transcript / --skip-transcription runs never transcribe, so they need no build.
needs_fluidaudio=1
for arg in "$@"; do
  case "$arg" in
    -t|-t?*|--transcript|--transcript=*|--skip-transcription) needs_fluidaudio=0 ;;
  esac
done
if [ "$needs_fluidaudio" = 1 ]; then
  ensure_fluidaudio
else
  echo "Transcript given or transcription skipped — skipping FluidAudio build."
fi

# Staging of ~/Downloads/*.{mp3,mp4} into raw/ now happens inside podbean.py
# (see stage_downloads_to_raw): re-run-safe and prompts when raw/ already holds files.

# --no-masking: otherwise op conceals stdout/stderr substrings that match injected
# secrets (e.g. “DevSecOps …” in title options). Alternative: export OP_RUN_NO_MASKING=1.
op run --no-masking --env-file="./.env" -- uv run python3 -u podbean.py "$@"
