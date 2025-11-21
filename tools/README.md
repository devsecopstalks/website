## Automated Podcast Publishing with AI

This tool streamlines the entire podcast publishing workflow:
1. **Transcribe** audio using OpenAI Whisper API
2. **Generate** title and description options using ChatGPT
3. **Select** your preferred title and description (or edit them)
4. **Upload** to Podbean and create episode markdown

### Prerequisites

Set required environment variables:
```bash
export OPENAI_API_KEY=your_openai_api_key
export PODBEAN_CLIENT_ID=your_podbean_client_id
export PODBEAN_CLIENT_SECRET=your_podbean_client_secret
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
   - Uploads audio to Podbean
   - Creates episode draft
   - Generates markdown file in `content/episodes/`

### Advanced Options

- `-f, --filename` - Path to audio file (mp3)
- `-v, --verbose` - Print verbose output
- `-s, --scan` - Scan current directory for mp3/mp4 files
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