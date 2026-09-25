## DevSecOps Talks — podcast publish pipeline

End-to-end flow: drop an MP3 in `raw/`, run `bash do.sh`, transcribe locally with FluidAudio (OpenAI opt-in), generate a long-form episode article with **Claude Code** (draft + revisions) and **Codex** (adversarial review until `GOOD_TO_GO`), pick title and short teaser with **Codex**, approve generated YouTube chapters, package subtitle, YouTube copy and Podbean show notes with one structured **Codex** call, render a cover image, upload audio to **Podbean**, choose between the next available Monday at 11:00 UTC or immediate publication, optionally upload video to **YouTube** via [upload-post.com](https://upload-post.com), write `content/episodes/NNN-slug.md`, and schedule an announcement on Andrey's LinkedIn and X through **Buffer**.

Checkpoint files live under `out/episodeNNN-*` (NNN = next Podbean episode number at run start) so you can resume after interruptions. The next number is calculated from the highest existing Podbean episode number, so future scheduled episodes are included.

### Prerequisites

CLI tools:

- [uv](https://docs.astral.sh/uv/) — Python dependencies
- [ffmpeg](https://ffmpeg.org/) + ffprobe — audio conversion and chunking for transcription
- Swift 6+ (Xcode or the Swift toolchain) — `do.sh` builds the pinned FluidAudio CLI for local transcription; its models (~685 MB) download on first run. Runs with `--transcript`/`-t` or `--skip-transcription` skip the build
- [claude](https://docs.anthropic.com/en/docs/claude-code) — Claude Code (draft + revise)
- [codex](https://github.com/openai/codex) — Codex CLI (review, titles, descriptions). Every call uses `--sandbox read-only -C <repo root>` with `gpt-6-astra` by default.
- [op](https://developer.1password.com/docs/cli/) — optional; `do.sh` uses it when `.env` is present

Environment variables (often injected via 1Password `op run --env-file=./.env`):

| Variable | Purpose |
|----------|---------|
| `TRANSCRIBE_BACKEND` | Optional; `local` (default, FluidAudio on Apple Silicon) or `openai` (`gpt-4o-transcribe-diarize`) |
| `OPENAI_API_KEY` | Only for `TRANSCRIBE_BACKEND=openai` |
| `EPISODE_SPEAKERS` | Optional; number of voices (or `auto`) to skip the speaker-count prompt |
| `FLUIDAUDIO_DIR` / `FLUIDAUDIO_CLI` | Optional; FluidAudio build dir (default `~/.cache/fluidaudio/devsecopstalks`) or an already-built `fluidaudiocli` |
| `PODBEAN_CLIENT_ID` / `PODBEAN_CLIENT_SECRET` | Podbean API |
| `CODEX_MODEL` | Optional; model for every Codex review, title, and description call (default `gpt-6-astra`) |
| `CODEX_TIMEOUT_S` | Optional; timeout in seconds for every Codex call (default `900`). Increase for longer articles |
| `UPLOAD_POST_API_KEY` / `UPLOAD_POST_USER` | YouTube upload via upload-post (optional) |
| `UPLOAD_PROGRESS` | Optional; default on (`1`). Set to `0`, `false`, `no`, or `off` to silence MiB/% progress lines for R2 and upload-post multipart uploads |
| `UPLOAD_POST_CONNECT_TIMEOUT_S` / `UPLOAD_POST_READ_TIMEOUT_MULTIPART_S` / `UPLOAD_POST_READ_TIMEOUT_DEFAULT_S` | Optional timeouts for upload-post HTTP client (connect default 120s; multipart read default 4h; default GET/JSON read 600s) |
| `UPLOAD_POST_HTTP_MAX_RETRIES` / `UPLOAD_POST_HTTP_BACKOFF` / `UPLOAD_POST_HTTP_BACKOFF_MAX_S` / `UPLOAD_POST_HTTP_RETRY_STATUS` | Optional urllib3 retries for flaky networks (POST retries enabled; status list defaults include 429, 499, 502–504) |
| `UPLOAD_POST_POOL_CONNECTIONS` / `UPLOAD_POST_POOL_MAXSIZE` | Optional `requests` connection pool sizing (defaults 4) |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` / `R2_PUBLIC_URL` | Optional: stage large local MP4 on Cloudflare R2 so upload-post fetches by HTTPS URL |
| `R2_MAX_RETRY_ATTEMPTS` / `R2_READ_TIMEOUT_S` | Optional boto client retries/read timeout for R2 uploads |
| `R2_MULTIPART_MAX_CONCURRENCY` / `R2_MULTIPART_CHUNKSIZE_MB` | Optional multipart tuning for R2 uploads (defaults 2 concurrent parts, 32 MiB chunks, min 8 MiB) |
| `BUFFER_API_KEY` | Optional; Buffer API key for the episode announcement. Unset skips Buffer |
| `YOUTUBE_VIDEO_R2_THRESHOLD_MB` | Optional; default `400` — local videos at or above this size use R2 staging when R2 is configured |

### Setup

```bash
cd tools
uv sync
```

### Layout

```
tools/
├── raw/              # put episode .mp3 here (and optional same-stem .md show notes, .mp4 video, .vtt/.txt transcript)
├── out/              # episodeNNN-* checkpoints (transcript, drafts, reviews, title/teaser, youtube-url)
├── prompts/          # draft/review/revise, titles, descriptions, guests, chapters, metadata, announcement (+ *-schema.json)
├── podcast-context.md # injected into prompts as {{CONTEXT}} (lives next to prompts/, not inside it)
├── blog-tone-of-voice.md # article voice and structure, injected as {{TONE}}
├── youtube-description.md / podcast-description.md # house rules for the YouTube and Podbean copy
├── podbean.py        # main entrypoint
├── episode_pipeline.py
├── episode_metadata.py # chapters, metadata call, YouTube description and Podbean show notes builders
├── generate_cover.py # static/images/covers/NNN.png for og:image
├── buffer_announce.py # Buffer announcement: quote check, approval, scheduling
├── social-handles.json # who the announcement tags, filename aliases, Buffer channel ids
├── transcribe_local.py # FluidAudio ASR + diarization, merged into speaker turns
├── youtube.py
├── upload_progress.py # progress lines for R2 + upload-post multipart body
├── r2_staging.py
├── writing-style.md  # injected into prompts as {{STYLE}}
├── seed_progress_markers.py
└── do.sh
```

### Basic usage

```bash
cd tools
# Copy or symlink your recording
cp ~/Downloads/episode.mp3 raw/

./do.sh
# Manual equivalent (note --no-masking: without it, `op run` may replace title
# text that matches a vault field with “concealed by 1Password” in stdout):
# op run --account family-beavers.1password.com --no-masking --env-file="./.env" -- uv run python podbean.py -v
```

If there is exactly one `raw/*.mp3`, it is chosen automatically. If there are several, pass `-f path/to/file.mp3` or use `--scan` to process all MP3s in `raw/`.

### Companion files in `raw/`

- **Show notes:** any `{same-stem}*.md` next to the MP3 is passed into draft/revise prompts as SHOW NOTES.
- **Video:** `{same-stem}*.mp4` (or `.mov`/`.mkv`) is used for YouTube when **`UPLOAD_POST_API_KEY`** and **`UPLOAD_POST_USER`** are set. If a companion video exists but those env vars are missing, the pipeline **warns and skips** YouTube while still publishing Podbean audio and the episode page (embed empty unless you pass `--youtube` with an embed URL).

- **Transcript:** a `{same-stem}*.vtt` or `{same-stem}*.txt` (for example a Riverside export) is merged with the machine transcript by Codex. Staging from `~/Downloads` moves only transcripts named after a downloaded MP3.

### Transcription

`TRANSCRIBE_BACKEND=local` (default) runs FluidAudio's Parakeet v2 ASR and VBx diarization over the whole file in seconds. `openai` sends 1300 s chunks to `gpt-4o-transcribe-diarize`; its speaker labels restart per chunk and it returns no word timings. Speakers are labelled `[A]`, `[B]`, ...; names are inferred downstream.

The local backend asks how many voices the episode has each time it transcribes. Enter means auto-detect. There is no default: pinning too low merges two people into one label, which nothing downstream can undo, while auto-detect fails visibly with an extra speaker.

Checkpoints:

- `out/episodeNNN-local.txt` / `-openai.txt` — machine transcript per backend, reused next run unless you type `new`.
- `out/episodeNNN.txt` — final transcript (machine, or merged with the sidecar).
- `out/episodeNNN-asr.json`, `-diarization.json`, `-turns.json` — local backend only; `-turns.json` holds timestamped speaker turns.
- `out/episodeNNN-transcript-source.json` — which backend produced the final transcript. Turns are used only when bound here to the current transcript, so a `-turns.json` left by another backend or run is ignored.

Saving a new `out/episodeNNN.txt` deletes the checkpoints built from the old one: guests, drafts, reviews, article, metadata, generated chapters and the generated announcement. Title, teaser, hand-written chapters, upload markers and the Buffer post ledger stay. To retranscribe, delete `out/episodeNNN.txt` and answer `new` (or delete the backend file).

`--transcript FILE` is saved as `out/episodeNNN.txt` when its content differs, with the same invalidation; its backend is recorded as `external`, so it has no timestamped turns. An identical file changes nothing.

### Article and packaging

The article follows `blog-tone-of-voice.md`: first person plural, no Summary or Highlights, exactly three common questions under `{#faq}` (the page turns them into FAQPage JSON-LD). Raw HTML is limited to `mark`, `figure`, `figcaption`, `img`, `br`, `sup` and `sub`, with no `on*=` handlers or `javascript:` URLs (code spans and fenced blocks are ignored); anything else stops the run before upload, listing each tag to fix in `out/episodeNNN-article.md`. A saved `-article.md` in the old Summary/Highlights format is not reused silently: the run offers to rename it and its drafts and reviews to `*.legacy` and write a new one.

After the title and teaser picks, and before anything is uploaded:

1. **Chapters.** A hand-written `out/episodeNNN-chapters.txt` (`MM:SS - Label` lines) wins and must pass YouTube's rules (at least 3, first `00:00`, ascending, 10 s apart) or the run stops. Otherwise Codex proposes 5-8 chapters from `-turns.json` for approval; the approved (or skipped) result is `-chapters-generated.txt`. With no timestamped turns (OpenAI backend, `--transcript`) chapters are omitted with a notice.
2. **Metadata.** One Codex call with `prompts/metadata-schema.json` writes `-metadata.json`: subtitle, YouTube title/hook/bullets/substance/comment prompt/hashtags, and Podbean show notes. It is regenerated when the title, teaser, article, transcript or guest context (including hosts present) changes. The picked title and teaser are never rewritten.
3. **Cover.** `static/images/covers/NNN.png`, kept if it already exists, becomes the page `image`.

A failure in any of these stops the run before Podbean or YouTube.

The page gets `description` (the teaser), `subtitle`, `readtime`, `image`, `youtube_id` and, when Podbean returns one, `audio_url`. Resuming an episode whose page already exists rewrites that file in place: filename, URL, `date`, aliases and participants stay; `title`, `lastmod` and the body change. A rewrite with no new `audio_url` or video keeps the ones already on the page. Existing Podbean episodes keep their show notes, and an already uploaded or scheduled video is not touched.

### YouTube and large MP4s

Direct multipart uploads to upload-post can hit **499/504** on very large files. Options:

1. **R2 staging (recommended when configured):** local files at or above `YOUTUBE_VIDEO_R2_THRESHOLD_MB` (default 400) are uploaded under keys like `podcast/youtube-staging/{NNN}-{12-hex-uuid}{.ext}` (episode index + random suffix, original extension preserved), the public HTTPS URL is sent to upload-post, then the staging object is deleted **after** a successful YouTube embed URL is saved to `out/episodeNNN-youtube-url.txt`. While staging or upload-post is in progress, the pipeline writes `out/episodeNNN-r2-youtube-staging.txt` with `url=`, `key=`, and `episode=` so a failed run can **retry without re-uploading** the MP4 to R2. If upload-post reports completion but no embed URL is returned (or YouTube failed on the platform side), the marker and R2 object are **kept** and the run **exits with an error**. Requires a **public GET** URL for the bucket path (`R2_PUBLIC_URL`). If R2 staging is required but not configured, or the staging upload fails, the run **exits with an error** instead of falling back to a direct multipart upload to upload-post.
2. **Force R2 for any size:** `--youtube-via-r2`
3. **Disable R2:** `--youtube-no-r2-staging`
4. **Manual URL:** `--youtube-video-url 'https://…/episode.mp4'` or env `UPLOAD_POST_VIDEO_URL`
5. **Skip upload:** `--youtube 'https://www.youtube.com/embed/VIDEO_ID'` or `--skip-youtube-upload`

A successful embed URL is cached in `out/episodeNNN-youtube-url.txt` for reruns. You can also create that file with `seed_progress_markers.py` (`--episode N` or `--stem episodeNNN`).

### Scheduling

The supported publishing workflow is interactive through `bash do.sh`. Every new episode offers one choice:

- Press Enter (or enter `s`) to schedule the episode for the next available Monday at **11:00 UTC**. Scheduling is the default.
- Enter `p` to publish immediately.

The next available Monday is calculated after both the current time and the latest published or scheduled Podbean episode, preserving episode order. If it is Monday before 11:00 UTC, today is eligible unless another episode already occupies that Monday. Any Monday with an existing episode is skipped, regardless of that episode's publication time.

Scheduled Podbean episodes are created with `status=future` and a future `publish_timestamp`, as specified by the [Podbean API](https://developers.podbean.com/podbean-api-docs/#api-Episode-Publish_New_Episode). The pipeline checks that Podbean returns that status and the requested time before continuing. `status=draft` only saves a draft, even when it carries a future timestamp. The optional upload-post YouTube video receives the same scheduled UTC datetime. upload-post returns a scheduled `job_id`, so no YouTube embed URL exists yet; that job is cached in `out/episodeNNN-youtube-scheduled.txt` to avoid duplicate submissions on reruns. If R2 staging was used, its marker and object are kept until the video has published and an embed URL is available.

There are no CLI flags for overriding publication status, date, time, or timezone. Existing Podbean episodes keep their current publication state when a run resumes and do not show the publishing prompt. A publishing run stops if the existing episode is still a draft; `--draft-only` can still regenerate its article.

**Recovering episodes created by older tooling:** those drafts are not automatically scheduled by this fix. In the Podbean dashboard, open each affected episode and use **Schedule Episode** to select a future publication time, or **Publish Now** if it is overdue and ready. Then resume locally with `--episode-number N` to reuse the existing episode and checkpoints. Future-dated drafts retain their intended queue slots until repaired. If YouTube was already scheduled, check its upload-post job separately before changing the release date; a saved YouTube job is reused and is not rescheduled by a rerun.

### Buffer announcement

The last step, after the page is written. Skipped when `BUFFER_API_KEY` is unset. It posts only to the channel ids in `social-handles.json` (Andrey's LinkedIn and X) and stops before posting anything if one of them is missing or disconnected in Buffer.

Only episodes this pipeline released are announced: creating the Podbean episode writes `out/episodeNNN-announcement-eligible.json` with the release time. Regenerating an older page (no such file, e.g. #110) skips Buffer.

1. **Who was on it.** The run shows `On this episode: ... (Andrey present|absent)`, from guest detection and host names in the Riverside filename (`paulina, matte, andrey +1`). Enter confirms; typing names corrects it. The answer is saved to `-guests.json` (`hosts_present`, `andrey_present`) and decides the voice: first person when Andrey was there, third person with no I/we when he was not.
2. **The post.** Codex writes one moment from the episode: a verbatim quote from the timestamped turns (default), a named disagreement, or, with no turns (OpenAI backend, `--transcript`), a paraphrased claim flagged `no verified quote`. The quote is checked against the turn it cites (case, punctuation and the name fixes in `podcast-context.md` ignored). The quoted person must also be who the speaker map names for that label. A failed check shows a word diff or the mismatch; `o` posts it anyway and records `quote_verified: operator`.
3. **Preview.** The LinkedIn post (text, credits with @-tags for the guest, hosts present and the DevSecOps Talks page, link on its own line, `#DevSecOps` plus at most one theme tag), the X post and its reply with the credits and link, the quote evidence (`[C] 12:34 -> Paulina Dubas`), each channel's due time and anything already scheduled. `a` schedules, `r` regenerates with guidance, `s` skips. A rule violation, or an X post or reply over 280 characters, blocks approval (also for a saved announcement): only `r` and `s` are offered.

A guest is @-tagged on LinkedIn only when guest detection confirmed their profile (`linkedin_name` in `-guests.json`); otherwise they are credited in plain text and the preview warns `not tagged on LinkedIn: <name>`.

Timing: release date + 2 days is the earliest date (Wednesday for the Monday 11:00 UTC slot); the time is the first slot in that channel's Buffer posting schedule on or after it. **Push and deploy the page before the due time**: the posts link to it.

State in `out/`:

- `-announcement-scheduled.txt`: one JSON line per created Buffer post (channel id, post id, due time, text), written right after each success and never rewritten. A channel listed there is never posted again; delete its line (after cancelling the post in Buffer) to post it again.
- `-announcement.json`: the approved copy and a fingerprint of its inputs (transcript, turns, page URL, target date, hosts, guests, handles). Any change regenerates it and asks for approval again.
- `-announcement.md`: record of what was posted.

Buffer errors never fail the run. Re-run with `--episode-number N` to retry the missing channels, also after the episode is live; the original release date is kept.

### Participants (Hugo front matter)

By default, new episode pages get `participants: ["Paulina", "Mattias", "Andrey"]`. Override with:

```bash
uv run podbean.py -f raw/ep.mp3 --participants "Paulina,Mattias,Andrey,Guest Name"
```

### Resumability

Outputs are under `out/episodeNNN-*` (NNN = next Podbean episode number calculated at run start, including already scheduled episodes). The draft–review loop runs up to **10** Codex review rounds (or stops early on `GOOD_TO_GO`). Re-running reuses existing transcript, draft/review checkpoints, final article, and cached title/description when those files exist. Delete a checkpoint file to force that step to run again; a new transcript also clears the checkpoints derived from it (see Transcription). Older runs may have used long MP3-stem names under `out/`; new runs use the `episodeNNN` prefix only.

A failed or empty Codex response stops the pipeline before publication. Timeouts report the elapsed limit without printing the prompt. Re-run to retry the failed step using the saved checkpoints; increase `CODEX_TIMEOUT_S` if needed.

### `article.py` (legacy)

`article.py` is an older workflow (GPT draft, single Claude pass, episode-number-based filenames in the working directory). Prefer `podbean.py` + `raw/`/`out/` for new episodes. See the script docstring for details.

### Examples

```bash
uv run podbean.py -f raw/my-show.mp3 -v
uv run python podbean.py --scan --draft-only   # stop after out/episodeNNN-article.md (NNN from Podbean)
uv run podbean.py -f raw/ep.mp3 --skip-transcription --title "Fixed Title" --description "Short teaser"
uv run podbean.py -f raw/ep.mp3 --youtube-via-r2 --video raw/ep.mp4
uv run podbean.py -f raw/ep.mp3 --episode-number 104  # resume/reuse an existing Podbean episode
```

### YouTube description text

Built from `-metadata.json` and the chapters as described in `youtube-description.md`: hook, what you will learn, who and framing, substance, comment prompt, chapters, links, five hashtags. The upload title is `<youtube_title> - DevSecOps Talks #NN`. Each **URL sits on its own line**, and the **episode** link is intentionally short (`https://devsecops.fm/episodes/NNN/`), matching the page's Hugo **`aliases`** entry, so YouTube does not ellipsize it. The exact text sent to upload-post is also written to `out/episodeNNN-youtube-description.txt`, and house-style misses (hook length, chapter count, word count) are printed as warnings.

### Tests

Stdlib `unittest` covers local transcript merging and backend selection, chapter validation, metadata packaging and the YouTube/Podbean builders, page writing (new and in place), URL/embed parsing, R2 staging markers, slug helpers, prompt expansion, numbered-list parsing, Codex invocation/failure handling, and Podbean scheduling/resume flows, and the Buffer announcement (quote check, voice, tags, ledger, eligibility). Network and subprocess calls are mocked; the tests do not publish episodes:

```bash
cd tools && uv run python -m unittest discover -s tests -v
```

There is no separate **demo** documentation directory in this repo; use this README and [`AGENTS.md`](../AGENTS.md) for agent/automation expectations.
