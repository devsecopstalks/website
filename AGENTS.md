# Agent / automation notes

There is no separate demo documentation tree in this repository. Authoritative documentation for the podcast publishing toolchain lives in [`tools/README.md`](tools/README.md).

## Tools layout

- **`tools/podbean.py`** — Main entry: `raw/` → `out/episodeNNN-*` checkpoints (NNN from Podbean) → Podbean → optional YouTube → `content/episodes/` → optional Buffer announcement.
- **`tools/transcribe_local.py`** — Default transcription backend (FluidAudio, built by `do.sh` at a pinned commit); `TRANSCRIBE_BACKEND=openai` selects the hosted fallback in `podbean.py`.
- **`tools/episode_pipeline.py`** — Claude + Codex review loop and interactive Codex title/description picks. Article voice and structure: `tools/blog-tone-of-voice.md`.
- **`tools/episode_metadata.py`** — YouTube chapters from timestamped turns, the structured metadata call, and the YouTube description / Podbean show notes builders.
- **`tools/buffer_announce.py`** — Buffer announcement on Andrey's LinkedIn and X, the last step of `podbean.py`; tags and channel ids in `tools/social-handles.json`.
- **`tools/article.py`** — Legacy post-publish article helper; prefer `podbean.py` for new work.

## Expectations for changes

- Preserve existing CLI flags and default behaviors unless the user explicitly requests a behavior change.
- Prefer small refactors that reduce duplication without altering outputs.
- After editing Python helpers, run unit tests:

  ```bash
  cd tools && uv run python -m unittest discover -s tests -v
  ```

## Security / ops

- These scripts are **operator tools** (local CLI), not network services. They invoke `claude` and `codex` subprocesses and read/write paths under `tools/`, `content/episodes/`, and optional Cloudflare R2. Do not log full API error bodies in shared CI logs without reviewing for sensitivity.
