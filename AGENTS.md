# Agent / automation notes

There is no separate demo documentation tree in this repository. Authoritative documentation for the podcast publishing toolchain lives in [`tools/README.md`](tools/README.md).

## Tools layout

- **`tools/podbean.py`** — Main entry: `raw/` → `out/episodeNNN-*` checkpoints (NNN from Podbean) → Podbean → optional YouTube → `content/episodes/`.
- **`tools/episode_pipeline.py`** — Claude + Codex review loop and interactive Codex title/description picks.
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
