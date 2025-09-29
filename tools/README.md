## Podbean Upload

```
bash setup.sh
source env/bin/activate
export PODBEAN_CLIENT_ID=id
export PODBEAN_CLIENT_SECRET=secret
python3 podbean.py ~/Downloads/podcast63-ai\ tools.mp3
```

or

```
bash setup.sh
source env/bin/activate
# copy file into the directory and use 1password to fill
# env variables and scan directory for mp3 files
op run --env-file="./.env" -- python3 podbean.py --scan
```

## Transcribe Podcast Episodes

Transcribe podcast episodes using **local Whisper** (FREE!) and extract highlights using **GPT-5 API** (optional):

### Basic Usage (No API Key Needed for Transcription!)

```bash
bash setup.sh
source env/bin/activate
python3 transcribe.py ~/Downloads/podcast-episode.mp3
```

This will:
1. Transcribe audio locally using Whisper (completely free, no API needed)
2. Create `podcast-episode_transcript.txt` in `~/Downloads`
3. If `OPENAI_API_KEY` is set, also extract highlights with GPT-5

### With Highlights Extraction

```bash
export OPENAI_API_KEY=your_api_key_here
python3 transcribe.py ~/Downloads/podcast-episode.mp3
```

This will create two files in `~/Downloads`:
- `podcast-episode_transcript.txt` - Full transcription (via local Whisper)
- `podcast-episode_highlights.txt` - AI-extracted highlights (via GPT-5)

### Optional Flags

- `-o, --output-dir` - Specify output directory (default: ~/Downloads)
- `-v, --verbose` - Print verbose output including detected language
- `--transcript-only` - Only generate transcript, skip highlights extraction
- `-m, --model` - Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3` (default: `base`)

### Model Size Guide

- **tiny** - Fastest, lowest quality (~1GB RAM)
- **base** - Good balance, recommended for most use cases (~1GB RAM) - DEFAULT
- **small** - Better quality (~2GB RAM)
- **medium** - High quality (~5GB RAM)
- **large-v2/large-v3** - Best quality (~10GB RAM)

### Examples

Transcribe with larger model for better quality:
```bash
python3 transcribe.py ~/Downloads/episode.mp3 -m medium -v
```

Transcribe only, skip highlights (no API key needed):
```bash
python3 transcribe.py ~/Downloads/episode.mp3 --transcript-only
```

Custom output directory with verbose output:
```bash
python3 transcribe.py ~/Downloads/episode.mp3 -o ~/Documents/transcripts -v
```