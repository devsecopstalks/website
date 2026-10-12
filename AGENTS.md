# Agent / automation notes

There is no separate demo documentation tree in this repository. Authoritative documentation for the podcast publishing toolchain lives in [`tools/README.md`](tools/README.md).

## Tools layout

- **`tools/podbean.py`** — Main entry: `raw/` → every question per episode → cover on R2, Podbean, YouTube → `content/episodes/` → Buffer announcement. Owns the step order, the step input record (`out/episodeNNN-inputs.json`) and `PipelineStop` handling. Keep every `input()` before the first upload; a test asserts it.
- **`tools/transcribe_local.py`** — Local transcription and diarization (FluidAudio, built by `do.sh` at a pinned commit); the only transcription source.
- **`tools/voice_match.py`** — Names diarized speakers from the voice prints in `tools/host-voices.json` (rebuilt with `tools/build-host-voices.py` after a FluidAudio pin bump).
- **`tools/episode_pipeline.py`** — Transcript correction loop, guest research, Claude + Codex article loop, Codex title/description picks. Article voice and structure: `tools/blog-tone-of-voice.md`.
- **`tools/episode_metadata.py`** — YouTube chapters from the corrected turns, the structured metadata call, and the YouTube description / Podbean show notes builders.
- **`tools/generate_cover.py`** / **`tools/r2_staging.py`** — Episode cover, served from R2; `tools/migrate_covers_to_r2.py` moves pre-R2 covers once.
- **`tools/buffer_announce.py`** — Buffer announcement on Andrey's LinkedIn, X and Threads: three drafters, approval before uploads, scheduling after the page; tags and channel ids in `tools/social-handles.json`.
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
