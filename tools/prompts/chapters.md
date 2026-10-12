{{CONTEXT}}

You propose YouTube chapters for a DevSecOps Talks episode.

On stdin: the episode's corrected transcript as timestamped speaker turns,
`[MM:SS] [Speaker Name]: text` lines in full. Timestamps are from the start of
the recording. The title and the article are written after the chapters, so
the chapters are the episode's first outline.

Rules:
- Return 5 to 8 chapters, one per line, formatted exactly `MM:SS - Label`
  (use `H:MM:SS` past one hour)
- The first chapter is `00:00`, and timestamps ascend, at least 10 seconds apart
- Place each chapter at the turn where that topic actually starts
- Labels are viewer-facing and specific, using the real term: "Repository
  renames break OIDC trust", not "Discussion" or "Part 2". The first label names
  the opening topic, not just "Intro"
- Labels under 50 characters, short dashes only, correct name spellings
- No extra commentary, just the chapter lines
