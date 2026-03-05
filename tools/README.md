## Automated Podcast Publishing with AI

This tool streamlines the entire podcast publishing workflow:
1. **Transcribe** audio using OpenAI Whisper API
2. **Generate** title and description options using ChatGPT
3. **Select** your preferred title and description (or edit them)
4. **Upload** to Podbean and YouTube, then create episode markdown

### Prerequisites

Set required environment variables:
```bash
export OPENAI_API_KEY=your_openai_api_key
export PODBEAN_CLIENT_ID=your_podbean_client_id
export PODBEAN_CLIENT_SECRET=your_podbean_client_secret
export UPLOAD_POST_API_KEY=your_upload_post_api_key
export UPLOAD_POST_USER=your_upload_post_username
```

### Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python package management.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync
```

### Basic Usage

**Option 1: Specify file directly**
```bash
uv run podbean.py -f ~/Downloads/podcast-episode.mp3
```

**Option 2: Scan current directory for mp3/mp4 files**
```bash
# Copy your audio file to the tools directory
uv run podbean.py --scan
```

**Option 3: Use with 1Password for secure credentials**
```bash
op run --env-file="./.env" -- uv run podbean.py --scan
```

### Workflow

When you run the script, it will:

1. **Calculate Episode Number**
   - Connects to Podbean to get the next episode number

2. **Transcribe** the audio file using OpenAI Whisper API
   - Saves transcript to `episode{number}.txt` (e.g., `episode084.txt`)

3. **Generate Options** using ChatGPT (GPT-5)
   - Creates 5 title options
   - Creates 5 description options

4. **Interactive Selection**
   - Choose from 5 title options (or enter custom/edit)
   - Press 'r' to regenerate with additional guidance (e.g., "focus more on security aspects")
   - Choose from 5 description options (or enter custom/edit)
   - Press 'r' to regenerate descriptions with additional guidance

5. **Upload & Publish**
   - Uploads audio (mp3) to Podbean and creates episode draft
   - Uploads video (mp4) to YouTube via [upload-post.com](https://upload-post.com) — skipped if no mp4 is present
   - Generates markdown file in `content/episodes/` with Podbean player and YouTube link

### Advanced Options

- `-f, --filename` - Path to audio (mp3) or video (mp4) file
- `-v, --verbose` - Print verbose output
- `-s, --scan` - Scan current directory for mp3 and mp4 files (mp3 → Podbean, mp4 → YouTube)
- `--skip-transcription` - Skip transcription (use existing transcript)
- `-t, --transcript` - Path to existing transcript file

### Examples

**Use existing transcript to save API costs:**
```bash
uv run podbean.py -f episode.mp3 --skip-transcription -t episode_transcript.txt
```

**Verbose output for debugging:**
```bash
uv run podbean.py -f episode.mp3 -v
```