## DevSecOps Talks — podcast publish pipeline

End-to-end flow: drop an MP3 in `raw/`, run `./do.sh` (or `uv run python podbean.py`), transcribe with OpenAI, generate a long-form episode article with **Claude Code** (draft + revisions) and **Codex** (adversarial review until `GOOD_TO_GO`), pick title and short teaser with **Codex**, upload audio to **Podbean**, optionally upload video to **YouTube** via [upload-post.com](https://upload-post.com), and write `content/episodes/NNN-slug.md`.

Checkpoint files live under `out/{mp3-stem}-*` so you can resume after interruptions.

### Prerequisites

CLI tools:

- [uv](https://docs.astral.sh/uv/) — Python dependencies
- [ffmpeg](https://ffmpeg.org/) + ffprobe — audio chunking for transcription
- [claude](https://docs.anthropic.com/en/docs/claude-code) — Claude Code (draft + revise)
- [codex](https://github.com/openai/codex) — Codex CLI (review, titles, descriptions)
- [op](https://developer.1password.com/docs/cli/) — optional; `do.sh` uses it when `.env` is present

Environment variables (often injected via 1Password `op run --env-file=./.env`):

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Transcription |
| `PODBEAN_CLIENT_ID` / `PODBEAN_CLIENT_SECRET` | Podbean API |
| `UPLOAD_POST_API_KEY` / `UPLOAD_POST_USER` | YouTube upload via upload-post (optional) |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` / `R2_PUBLIC_URL` | Optional: stage large local MP4 on Cloudflare R2 so upload-post fetches by HTTPS URL |
| `YOUTUBE_VIDEO_R2_THRESHOLD_MB` | Optional; default `400` — local videos at or above this size use R2 staging when R2 is configured |

### Setup

```bash
cd tools
uv sync
```

### Layout

```
tools/
├── raw/              # put episode .mp3 here (and optional same-stem .md show notes, .mp4 video)
├── out/              # episodeNNN-* checkpoints (transcript, drafts, reviews, title/teaser, youtube-url)
├── prompts/          # draft.md, review.md, revise.md, titles.md, descriptions.md (+ podcast-context.md)
├── podbean.py        # main entrypoint
├── episode_pipeline.py
├── youtube.py
├── r2_staging.py
├── seed_progress_markers.py
└── do.sh
```

### Basic usage

```bash
cd tools
# Copy or symlink your recording
cp ~/Downloads/episode.mp3 raw/

./do.sh
# or: op run --env-file="./.env" -- uv run python podbean.py -v
```

If there is exactly one `raw/*.mp3`, it is chosen automatically. If there are several, pass `-f path/to/file.mp3` or use `--scan` to process all MP3s in `raw/`.

### Companion files in `raw/`

- **Show notes:** any `{same-stem}*.md` next to the MP3 is passed into draft/revise prompts as SHOW NOTES.
- **Video:** `{same-stem}*.mp4` (or `.mov`/`.mkv`) is used for YouTube when upload-post credentials are set.

### YouTube and large MP4s

Direct multipart uploads to upload-post can hit **499/504** on very large files. Options:

1. **R2 staging (recommended when configured):** local files at or above `YOUTUBE_VIDEO_R2_THRESHOLD_MB` (default 400) are uploaded to `podcast/youtube-staging/{episode}-{id}.mp4`, the public HTTPS URL is sent to upload-post, then the object is deleted. Requires a **public GET** URL for the bucket path (`R2_PUBLIC_URL`).
2. **Force R2 for any size:** `--youtube-via-r2`
3. **Disable R2:** `--youtube-no-r2-staging`
4. **Manual URL:** `--youtube-video-url 'https://…/episode.mp4'` or env `UPLOAD_POST_VIDEO_URL`
5. **Skip upload:** `--youtube 'https://www.youtube.com/embed/VIDEO_ID'` or `--skip-youtube-upload`

A successful embed URL is cached in `out/episodeNNN-youtube-url.txt` for reruns. You can also create that file with `seed_progress_markers.py` (`--episode N` or `--stem episodeNNN`).

### Participants (Hugo front matter)

By default, new episode pages get `participants: ["Paulina", "Mattias", "Andrey"]`. Override with:

```bash
uv run podbean.py -f raw/ep.mp3 --participants "Paulina,Mattias,Andrey,Guest Name"
```

### Resumability

Outputs are under `out/episodeNNN-*` (NNN = next Podbean episode number queried at run start). Re-running reuses existing transcript, draft/review checkpoints, final article, and cached title/description when those files exist. Delete a checkpoint file to force that step to run again. Older runs may have used long MP3-stem names under `out/`; new runs use the `episodeNNN` prefix only.

### `article.py` (legacy)

`article.py` is an older workflow (GPT draft, single Claude pass, episode-number-based filenames in the working directory). Prefer `podbean.py` + `raw/`/`out/` for new episodes. See the script docstring for details.

### Examples

```bash
uv run podbean.py -f raw/my-show.mp3 -v
uv run podbean.py --scan --draft-only          # stop after out/{stem}-article.md
uv run podbean.py -f raw/ep.mp3 --skip-transcription --title "Fixed Title" --description "Short teaser"
uv run podbean.py -f raw/ep.mp3 --youtube-via-r2 --video raw/ep.mp4
```

### YouTube description text

The upload uses **plain text** with each important **URL on its own line**, so the YouTube app is less likely to show long links with a `…` in the middle. (Some YouTube clients still shorten link *display*; tap or “Copy” to see the full URL.) The exact text sent to upload-post is also written to `out/episodeNNN-youtube-description.txt` for review.

### Tests

Pure helpers (URL/embed parsing, slug helpers, numbered-list parsing) are covered by stdlib `unittest`:

```bash
cd tools && uv run python -m unittest discover -s tests -v
```

There is no separate **demo** documentation directory in this repo; use this README and [`AGENTS.md`](../AGENTS.md) for agent/automation expectations.
