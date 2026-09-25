# Podcast show notes

Rules for the Podbean episode description, which Apple Podcasts and Spotify
show next to the player. A listener surface: third person, hosts and guests by
full name, naming rules from [`podcast-context.md`](podcast-context.md).

## Shape

Built by `build_podbean_show_notes()` in [`episode_metadata.py`](episode_metadata.py):

1. **Hook**, one or two sentences: the problem in the listener's terms.
2. **Who and what**, one sentence: the hosts present, any guest, the topics.
3. **What you will learn**, three to five bullets, one line each.
4. **Episode page link**, plus the LinkedIn discussion link.

Under roughly 200 words. Apps truncate the visible block, so everything that
earns a listen goes early.

## Formatting

Podcast apps collapse plain newlines, so the notes are HTML limited to the
subset Apple and Spotify render: `<p>`, `<strong>`, `<ul>`, `<li>`, `<a href>`.
No Markdown, headings, styles or images.

## Rules of thumb

- Write for someone deciding whether to press play.
- Every claim has to be in the episode.
- Short dashes only.
- Show notes are set when the Podbean episode is created. Resuming an existing
  episode does not rewrite them.
