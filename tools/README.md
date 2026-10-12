## DevSecOps Talks — podcast publish pipeline

Drop an MP3 (and its video) in `raw/` and run `bash do.sh`. For each episode the pipeline asks every question first: who is speaking, the corrected transcript, chapters, title, teaser, article, release time and the social announcement. Then, without further prompts, it uploads the cover to R2, the audio to **Podbean** and the video to **YouTube** via [upload-post.com](https://upload-post.com). It writes `content/episodes/NNN-slug.md` and schedules the announcement on Andrey's LinkedIn, X and Threads through **Buffer**.

Checkpoint files live under `out/episodeNNN-*` (NNN = next Podbean episode number at run start) so you can resume after interruptions. The next number is calculated from the highest existing Podbean episode number, so future scheduled episodes are included.

### Prerequisites

CLI tools, all checked before the run starts:

- [uv](https://docs.astral.sh/uv/) — Python dependencies
- [ffmpeg](https://ffmpeg.org/) + ffprobe — audio conversion for transcription
- Swift 6+ (Xcode or the Swift toolchain) — `do.sh` builds the pinned FluidAudio CLI for local transcription on every run that lacks it; its models (~685 MB) download on first run
- [claude](https://docs.anthropic.com/en/docs/claude-code) — Claude Code (guests, draft + revise, an announcement drafter)
- [codex](https://github.com/openai/codex) — Codex CLI (transcript correction, review, titles, descriptions, chapters, metadata, an announcement drafter). Every call uses `--sandbox read-only -C <repo root>` with `gpt-6-astra` by default.
- [grok](https://x.ai) — Grok CLI, logged in; the third announcement drafter. `--draft-only` runs do not need it
- [op](https://developer.1password.com/docs/cli/) — optional; `do.sh` uses it when `.env` is present

Environment variables (often injected via 1Password `op run --env-file=./.env`):

| Variable | Purpose |
|----------|---------|
| `EPISODE_SPEAKERS` | Optional; number of voices (or `auto`) to skip the speaker-count prompt |
| `FLUIDAUDIO_DIR` / `FLUIDAUDIO_CLI` | Optional; FluidAudio build dir (default `~/.cache/fluidaudio/devsecopstalks`) or an already-built `fluidaudiocli` |
| `PODBEAN_CLIENT_ID` / `PODBEAN_CLIENT_SECRET` | Podbean API |
| `CODEX_MODEL` | Optional; model for every Codex call (default `gpt-6-astra`) |
| `CODEX_TIMEOUT_S` | Optional; timeout in seconds for every Codex call (default `900`). Increase for longer articles |
| `CLAUDE_TIMEOUT_S` / `GROK_TIMEOUT_S` | Optional; Claude and Grok call timeouts (defaults `2400` and `900`) |
| `UPLOAD_POST_API_KEY` / `UPLOAD_POST_USER` | YouTube upload via upload-post; required unless the video is already uploaded or the run opts out |
| `UPLOAD_PROGRESS` | Optional; default on (`1`). Set to `0`, `false`, `no`, or `off` to silence MiB/% progress lines for R2 and upload-post multipart uploads |
| `UPLOAD_POST_CONNECT_TIMEOUT_S` / `UPLOAD_POST_READ_TIMEOUT_MULTIPART_S` / `UPLOAD_POST_READ_TIMEOUT_DEFAULT_S` | Optional timeouts for upload-post HTTP client (connect default 120s; multipart read default 4h; default GET/JSON read 600s) |
| `UPLOAD_POST_HTTP_MAX_RETRIES` / `UPLOAD_POST_HTTP_BACKOFF` / `UPLOAD_POST_HTTP_BACKOFF_MAX_S` / `UPLOAD_POST_HTTP_RETRY_STATUS` | Optional urllib3 retries for flaky networks (POST retries enabled; status list defaults include 429, 499, 502–504) |
| `UPLOAD_POST_POOL_CONNECTIONS` / `UPLOAD_POST_POOL_MAXSIZE` | Optional `requests` connection pool sizing (defaults 4) |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | Cloudflare R2 credentials for covers and large-MP4 staging; the token needs R2 Storage Read and Write |
| `R2_COVERS_BUCKET` / `R2_COVERS_PUBLIC_URL` | Required; the covers bucket and its public base URL |
| `R2_BUCKET` / `R2_PUBLIC_URL` | Large-MP4 staging bucket (default `podcast-staging`) and its public base URL |
| `R2_MAX_RETRY_ATTEMPTS` / `R2_READ_TIMEOUT_S` | Optional boto client retries/read timeout for R2 uploads |
| `R2_MULTIPART_MAX_CONCURRENCY` / `R2_MULTIPART_CHUNKSIZE_MB` | Optional multipart tuning for R2 uploads (defaults 2 concurrent parts, 32 MiB chunks, min 8 MiB) |
| `BUFFER_API_KEY` | Buffer API key for the episode announcement; required for an episode this run releases |
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
├── out/              # episodeNNN-* checkpoints (turns, corrected transcript, drafts, reviews, title/teaser, upload markers)
├── prompts/          # transcript correction/review, draft/review/revise, titles, descriptions, guests, chapters, metadata, announcement (+ *-schema.json)
├── podcast-context.md # injected into prompts as {{CONTEXT}}; its name list drives the transcript correction
├── blog-tone-of-voice.md # article voice and structure, injected as {{TONE}}
├── youtube-description.md / podcast-description.md # house rules for the YouTube and Podbean copy
├── podbean.py        # main entrypoint: step order, step input record, uploads
├── episode_pipeline.py # transcript correction, guests, article loop, title/teaser picks
├── episode_metadata.py # chapters, metadata call, YouTube description and Podbean show notes builders
├── voice_match.py    # names diarized speakers by voice print
├── host-voices.json  # the hosts' voice prints (built by build-host-voices.py)
├── build-host-voices.py
├── generate_cover.py # the episode cover, redrawn when title or guests change
├── migrate_covers_to_r2.py # one-off: moves covers from static/images/covers/ to R2
├── buffer_announce.py # Buffer announcement: drafters, quote check, approval, scheduling
├── social-handles.json # who the announcement tags, Buffer channel ids
├── transcribe_local.py # FluidAudio ASR + diarization, merged into speaker turns
├── youtube.py
├── upload_progress.py # progress lines for R2 + upload-post multipart body
├── r2_staging.py     # R2 covers and video staging
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

If there is exactly one `raw/*.mp3`, it is chosen automatically. If there are several, pass `-f path/to/file.mp3` or use `--scan` to process all MP3s in `raw/`. With `--scan` each episode runs to the end before the next one starts, so the next episode's questions come after the previous one's uploads.

### Step order

1. Editorial guidance
2. Local transcription (asks the voice count when it transcribes)
3. Voice match: confirm who each speaker label is
4. Guests: name every voice that is not a host, then confirm what research found
5. Transcript correction
6. Chapters
7. Title and teaser
8. Article (`--draft-only` stops here)
9. Metadata
10. Cover, drawn locally
11. Release time: next free Monday or now
12. Announcement: pick one of three drafts, with the cover open

Nothing below asks anything:

13. Cover to R2, audio to Podbean, video to YouTube
14. Episode page, `image:` set to the R2 cover URL
15. The approved announcement scheduled on Buffer

### Companion files in `raw/`

- **Show notes:** any `{same-stem}*.md` next to the MP3 is passed into the guest, draft and revise prompts as SHOW NOTES.
- **Video:** `{same-stem}*.mp4` (or `.mov`/`.mkv`) is uploaded to YouTube. With no video, no upload-post keys, or a video `--youtube-via-r2` cannot stage, the run stops before any question; pass `--youtube URL` or `--skip-youtube-upload` to publish without one.
- **Transcript:** a `{same-stem}*.vtt` or `{same-stem}*.txt` (for example a Riverside export), or `--transcript FILE`, is given to the transcript correction as spelling reference. It never replaces the local transcript, which is the only source with timings and voice labels. Staging from `~/Downloads` moves only transcripts named after a downloaded MP3.

### Transcription and speakers

FluidAudio's Parakeet v2 ASR and VBx diarization run over the whole file in seconds. Turns are labelled `[A]`, `[B]`, ... in `out/episodeNNN-turns.json`. The run asks how many voices the episode has each time it transcribes. Enter means auto-detect. There is no default: pinning too low merges two people into one label, which nothing downstream can undo, while auto-detect fails visibly with an extra speaker.

**Voice match.** Each label's speaker-weighted embedding is compared with the host prints in `host-voices.json`. The run shows label, best match, score and minutes. Enter accepts; `C=Mattias` or `C=guest` renames a label; a number re-diarizes pinned to that many voices (seconds, the ASR is reused). Enter is refused while a match is flagged ⚠: a score between 0.55 and 0.80, or the best host within 0.05 of the runner-up. Confirmed renames are kept in `-speakers.json` for the same diarization. The hosts heard become `hosts_present`, which decides who the announcement credits and whether it speaks as Andrey.

**Guests.** The run asks who each voice that is not a host is: a full name plus anything that helps find them (company, role, a link). The same name for two labels is one person; a host's name names that label as the host. Claude then looks up only those people, with the transcript and show notes as context, and never adds, drops or renames a guest. The run shows each guest's role and LinkedIn, X and Threads handles ("not found" means credited in plain text); Enter accepts, and a guest number plus a correction looks that guest up again. Answers are kept in `-guest-labels.json` and research in `-guests.json`; a rerun offers to reuse them, and a changed name discards the transcript correction and every later step.

**Voice prints** are built from labels confirmed by ear. They only compare with embeddings from the same model, so prints carry the FluidAudio commit. A pin bump in `do.sh` stops every run until they are rebuilt from diarizations made by the new build:

```bash
uv run python build-host-voices.py 111:S1=Mattias 112:S2=Mattias 111:S2=Paulina 112:S1=Andrey          # check minutes and the cosine matrix
uv run python build-host-voices.py 111:S1=Mattias 112:S2=Mattias 111:S2=Paulina 112:S1=Andrey --write
```

Labels here are the diarizer ids (`S1`) in `out/episodeNNN-diarization.json`. The builder refuses a diarization whose `fluidaudioCommit` stamp differs from the `do.sh` pin. Episodes 111 and 112 predate the stamp, so rebuilding from them needs `--assume-pin`. Add more sources per host as episodes come in: Paulina and Andrey have one recording each, so a noisy episode may flag them.

### Transcript correction

Codex rewrites the turns (misheard names and terms, using the name list in `podcast-context.md`; filler sounds dropped; speaker named) and a second Codex call reviews the result, up to 5 rounds. It may never paraphrase, merge, split or reattribute a turn; turn count, labels and times are checked. At the cap, `e` runs 5 more rounds and `s` keeps the transcript with the flagged turns, which the announcement cannot quote. Output: `-turns-corrected.json` and `out/episodeNNN.txt` as `Name: text` lines, read by every later step.

### Article and packaging

Chapters, then title and teaser, are built from the corrected transcript, and the article is written to them:

1. **Chapters.** A hand-written `out/episodeNNN-chapters.txt` (`MM:SS - Label` lines) wins and must pass YouTube's rules (at least 3, first `00:00`, ascending, 10 s apart) or the run stops. Otherwise Codex proposes 5-8 chapters for approval; the approved (or skipped) result is `-chapters-generated.txt`.
2. **Title and teaser.** Codex offers options; both must name every guest in full. `--title` and `--description` skip the picks.
3. **Article.** Follows `blog-tone-of-voice.md`: first person plural, no Summary or Highlights, exactly three common questions under `{#faq}` (the page turns them into FAQPage JSON-LD). Raw HTML is limited to `mark`, `figure`, `figcaption`, `img`, `br`, `sup` and `sub`, with no `on*=` handlers or `javascript:` URLs (code spans and fenced blocks are ignored); anything else stops the run before upload, listing each tag to fix in `out/episodeNNN-article.md`. A saved `-article.md` in the old Summary/Highlights format is not reused silently: the run offers to rename it and its drafts and reviews to `*.legacy` and write a new one.
4. **Metadata.** One Codex call with `prompts/metadata-schema.json` writes `-metadata.json`: subtitle, YouTube title/hook/bullets/substance/comment prompt/hashtags, and Podbean show notes. The picked title and teaser are never rewritten.
5. **Cover.** `out/episodeNNN-cover.png`, redrawn when the title or guest names change.

The page gets `description` (the teaser), `subtitle`, `readtime`, `image`, `youtube_id` and, when Podbean returns one, `audio_url`. Resuming an episode whose page already exists rewrites that file in place: filename, URL, `date`, aliases and participants stay; `title`, `lastmod` and the body change. A rewrite with no new `audio_url` or video keeps the ones already on the page. Existing Podbean episodes keep their show notes, and an already uploaded or scheduled video is not touched.

### Covers on R2

Covers live in their own bucket (`R2_COVERS_BUCKET`), because the staging bucket expires every object. They are stored under `covers/NNN-<sha12>.png` with `Cache-Control: public, max-age=31536000, immutable`. The key changes with the image, so a redrawn cover gets a new URL instead of a stale cached one. Before any upload the run reads the covers bucket's lifecycle rules and stops if one could expire `covers/` (an empty prefix or any prefix overlapping it), since published pages would lose their image. Give the covers bucket no expiry rule.

Pages from before this moved to R2 point at `/images/covers/NNN.png`. `migrate_covers_to_r2.py` uploads those files and rewrites their `image:` lines; then delete `static/images/covers/`:

```bash
op run --env-file=./.env -- uv run python3 migrate_covers_to_r2.py --dry-run   # keys and edits only
op run --env-file=./.env -- uv run python3 migrate_covers_to_r2.py
```

### YouTube and large MP4s

Direct multipart uploads to upload-post can hit **499/504** on very large files. Options:

1. **R2 staging (recommended when configured):** local files at or above `YOUTUBE_VIDEO_R2_THRESHOLD_MB` (default 400) are uploaded under keys like `podcast/youtube-staging/{NNN}-{12-hex-uuid}{.ext}` (episode index + random suffix, original extension preserved), the public HTTPS URL is sent to upload-post, then the staging object is deleted **after** a successful YouTube embed URL is saved to `out/episodeNNN-youtube-url.txt`. While staging or upload-post is in progress, the pipeline writes `out/episodeNNN-r2-youtube-staging.txt` with `url=`, `key=`, and `episode=` so a failed run can **retry without re-uploading** the MP4 to R2. If upload-post reports completion but no embed URL is returned (or YouTube failed on the platform side), the marker and R2 object are **kept** and the run **stops**. Requires a **public GET** URL for the bucket path (`R2_PUBLIC_URL`). If R2 staging is required but not configured, or the staging upload fails, the run **stops** instead of falling back to a direct multipart upload to upload-post.
2. **Force R2 for any size:** `--youtube-via-r2`
3. **Disable R2:** `--youtube-no-r2-staging`
4. **Manual URL:** `--youtube-video-url 'https://…/episode.mp4'` or env `UPLOAD_POST_VIDEO_URL`
5. **Skip upload:** `--youtube 'https://www.youtube.com/embed/VIDEO_ID'` or `--skip-youtube-upload`

A successful embed URL is cached in `out/episodeNNN-youtube-url.txt` for reruns. You can also create that file with `seed_progress_markers.py` (`--episode N` or `--stem episodeNNN`). To redo a video, delete it on YouTube and delete the marker.

### Scheduling

Every new episode offers one choice:

- Press Enter (or enter `s`) to schedule the episode for the next available Monday at **11:00 UTC**. Scheduling is the default.
- Enter `p` to publish immediately.

The next available Monday is calculated after both the current time and the latest published or scheduled Podbean episode, preserving episode order. If it is Monday before 11:00 UTC, today is eligible unless another episode already occupies that Monday. Any Monday with an existing episode is skipped, regardless of that episode's publication time.

Scheduled Podbean episodes are created with `status=future` and a future `publish_timestamp`, as specified by the [Podbean API](https://developers.podbean.com/podbean-api-docs/#api-Episode-Publish_New_Episode). The pipeline checks that Podbean returns that status and the requested time before continuing. `status=draft` only saves a draft, even when it carries a future timestamp. The upload-post YouTube video receives the same scheduled UTC datetime. upload-post returns a scheduled `job_id`, so no YouTube embed URL exists yet; that job is cached in `out/episodeNNN-youtube-scheduled.txt` to avoid duplicate submissions on reruns. If R2 staging was used, its marker and object are kept until the video has published and an embed URL is available.

There are no CLI flags for overriding publication status, date, time, or timezone. Existing Podbean episodes keep their current publication state when a run resumes and do not show the publishing prompt. A publishing run stops if the existing episode is still a draft; `--draft-only` can still regenerate its article.

**Recovering episodes created by older tooling:** those drafts are not automatically scheduled. In the Podbean dashboard, open each affected episode and use **Schedule Episode** to select a future publication time, or **Publish Now** if it is overdue and ready. Then resume locally with `--episode-number N` to reuse the existing episode and checkpoints. Future-dated drafts retain their intended queue slots until repaired. If YouTube was already scheduled, check its upload-post job separately before changing the release date; a saved YouTube job is reused and is not rescheduled by a rerun.

### Buffer announcement

Only episodes this pipeline released are announced: creating the Podbean episode writes `out/episodeNNN-announcement-eligible.json` with the release time. Regenerating an older page (no such file, e.g. #110) skips Buffer. A saved approval without that file (a run that stopped before Podbean confirmed the release) stops the run instead, asking for the release time as `{"release_at": "<ISO UTC>"}`. An announced episode needs `BUFFER_API_KEY` and the LinkedIn, X and Threads channel ids in `social-handles.json`, and each channel must be connected in Buffer. Otherwise the run stops before any question or upload; when the Threads id is missing, the message lists Buffer's Threads channels. Each channel also needs a posting slot on the target date, which is checked at the announcement step, still before any upload.

**Approval (step 12, before uploads).** Codex, Claude and Grok each draft the post in parallel, each with its own timeout. A draft that breaks a rule is retried once, then dropped; a drafter that fails is left out. The post is one body for every network: a quote or a named disagreement. A quote must match, word for word, consecutive corrected turns of one speaker: the guest's words, or a host's only when there is no guest; flagged turns are never quotable. The preview shows each candidate as posted on LinkedIn, X (post + reply with the credits and link) and Threads, every channel's due time, and opens the cover, which is attached to every post. `1`–`3` picks a draft, `r` drafts again with guidance (rejected rounds go back to the drafters), `s` skips Buffer for this episode.

The voice follows `hosts_present` from the speakers' names: first person when Andrey was there, third person with no I/we when he was not. A guest is @-tagged only when guest research confirmed that profile (`linkedin_name`, `x_handle`, `threads_handle` in `-guests.json`); otherwise they are credited in plain text. On LinkedIn the company is credited with its Page URL (`linkedin_credit`): Buffer does not resolve @-mentions of company Pages.

**Scheduling (step 15, after the page).** Timing: release date + 2 days is the earliest date (Wednesday for the Monday 11:00 UTC slot); the time is the first slot in that channel's Buffer posting schedule on or after it. **Push and deploy the page before the due time**: the posts link to it. If what would be posted no longer matches the approval (page URL, cover URL, date, handles), the approval is set aside as `-announcement.stale.json`, the run stops, and the next run asks again. A Buffer error stops the run with exit 1; a rerun posts only the channels that failed.

State in `out/`:

- `-announcement.json`: the approved posts, page URL, target date, cover URL and a fingerprint of their inputs. Changed inputs draft again.
- `-announcement-scheduled.txt`: one JSON line per created Buffer post (channel id, post id, due time, fingerprint, text), written right after each success. A channel with a line is never posted again, even when the approval changed (the run warns and names it); delete its line, after cancelling the post in Buffer, to post it again.
- `-announcement-rejected.jsonl`: rejected rounds and their guidance.
- `-announcement.md`: record of what was posted.

### Stops and reruns

Anything that cannot finish stops the run with the message, the checkpoint to fix or delete, and exit 1; nothing is skipped silently. Before the first question the run checks the CLIs above and the voice prints' FluidAudio pin. Unless `--draft-only`, it also checks R2 and its lifecycle rules, Buffer, and the upload-post keys and video. The video checks are skipped when the video is already uploaded, given with `--youtube`, or opted out. A finished upload (its marker in `out/`) needs neither its source nor its keys again.

Each local step records what it was built from in `out/episodeNNN-inputs.json`. When a step's inputs change (a re-diarization, a new guest, another title), its checkpoints and every later step's are discarded and rebuilt; unchanged steps are reused. A step with no entry counts as changed, so the first run on an episode from older tooling transcribes it again and asks again. Upload markers, the Podbean episode and the Buffer ledger are never discarded: to redo an upload, delete it remotely and delete its marker.

The draft–review loop runs up to **10** Codex review rounds (or stops early on `GOOD_TO_GO`). Older runs may have used long MP3-stem names under `out/`; new runs use the `episodeNNN` prefix only.

### Participants (Hugo front matter)

By default, new episode pages get `participants: ["Paulina", "Mattias", "Andrey"]`. Override with:

```bash
uv run podbean.py -f raw/ep.mp3 --participants "Paulina,Mattias,Andrey,Guest Name"
```

### Examples

```bash
uv run podbean.py -f raw/my-show.mp3 -v
uv run python podbean.py --scan --draft-only   # stop after out/episodeNNN-article.md (NNN from Podbean)
uv run podbean.py -f raw/ep.mp3 --skip-transcription --title "Fixed Title" --description "Short teaser"
uv run podbean.py -f raw/ep.mp3 --youtube-via-r2 --video raw/ep.mp4
uv run podbean.py -f raw/ep.mp3 --episode-number 104  # resume/reuse an existing Podbean episode
```

`--skip-transcription` reuses `out/episodeNNN-turns.json` as is, even when the recording's input record differs.

### YouTube description text

Built from `-metadata.json` and the chapters as described in `youtube-description.md`: hook, what you will learn, who and framing, substance, comment prompt, chapters, links, five hashtags. The upload title is `<youtube_title> - DevSecOps Talks #NN`. Each **URL sits on its own line**, and the **episode** link is intentionally short (`https://devsecops.fm/episodes/NNN/`), matching the page's Hugo **`aliases`** entry, so YouTube does not ellipsize it. The exact text sent to upload-post is also written to `out/episodeNNN-youtube-description.txt`, and house-style misses (hook length, chapter count, word count) are printed as warnings.

### Tests

Stdlib `unittest` covers the step order (no prompt after the first upload), the step input record, voice matching and transcript correction. It also covers chapters, metadata, the YouTube and Podbean builders, covers on R2, page writing, Podbean scheduling and resume, and the Buffer announcement (drafters, quote check, Threads, assets, ledger). Network and subprocess calls are mocked; the tests do not publish episodes:

```bash
cd tools && uv run python -m unittest discover -s tests -v
```
