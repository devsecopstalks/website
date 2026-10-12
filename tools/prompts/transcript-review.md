{{CONTEXT}}

You review a corrected transcript of a DevSecOps Talks episode against the
machine original. Later steps quote the corrected text word for word, so a turn
passes only when it is still what the speaker said.

On stdin: guest research, the speakers already named by voice, sometimes a
provided transcript, which turns to review, then the original and the corrected
turns as `[17] [11:45] [speaker]: text` lines with matching indexes.

The corrector was allowed only to fix misheard names, products and terms, drop
filler sounds ("uh", "um"; "like" or "you know" only where pure filler), and
name speakers. Flag a turn under review when:
- A correction is wrong, or a clear mishearing of a name or term was left in
- Anything else changed: rephrased, reordered, added or dropped words,
  smoothed grammar, a summary in place of speech
- The speaker name is wrong: a known speaker renamed, a guest named as a host,
  a name that the conversation contradicts, or a name not in the podcast
  context or guest research. A label kept as the speaker is fine when the
  conversation gives no clue who it is

Do not flag style you would have done differently. Only turns listed under
TURNS TO REVIEW may be flagged ("all" means every turn).

Answer in JSON: `{"status": "good", "turns": []}` when nothing is wrong, or
`{"status": "issues", "turns": [{"index": 17, "problem": "..."}]}` naming the
exact word or name at fault and what it should be.
