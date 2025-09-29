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

Transcribe podcast episodes and extract highlights using OpenAI API:

```bash
bash setup.sh
source env/bin/activate
export OPENAI_API_KEY=your_api_key_here
python3 transcribe.py ~/Downloads/podcast-episode.mp3
```

This will create two files in `~/Downloads`:
- `podcast-episode_transcript.txt` - Full transcription
- `podcast-episode_highlights.txt` - Extracted highlights and key points

Optional flags:
- `-o, --output-dir` - Specify output directory (default: ~/Downloads)
- `-v, --verbose` - Print verbose output
- `--transcript-only` - Only generate transcript, skip highlights extraction

Example with custom output directory:
```bash
python3 transcribe.py ~/Downloads/episode.mp3 -o ~/Documents/transcripts -v
```