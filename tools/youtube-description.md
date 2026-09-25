# YouTube title and description

Rules for the YouTube upload. Third person, with the naming rules from
[`podcast-context.md`](podcast-context.md). The article rules in
[`blog-tone-of-voice.md`](blog-tone-of-voice.md) do not apply here.

## Title

The upload title is `<youtube_title> - DevSecOps Talks #NN`. The hook comes
first because mobile truncates around 60 characters.

- `youtube_title` is a question, or a claim that answers one, with the payoff
  attached. 40 to 70 characters, no episode number.
- Write it for someone scrolling, separately from the episode title. If the
  episode title is genuinely the strongest hook, use it.
- Recognizable keyword early: AWS, GitHub Actions, Kubernetes, Terraform, OIDC.
- Name any guest when it fits; the episode title already carries the name.
- No clickbait the episode does not deliver, no ALL CAPS, no emoji.

## Description

200 to 350 words of prose above the links. Only the first 100 to 150
characters show above "Show more", so open with the problem in the viewer's own
words, never with the show name or "In this episode".

Assembled by `build_youtube_description()` in
[`episode_metadata.py`](episode_metadata.py), in this order:

1. **Hook**, two or three sentences: the problem, then what the episode does
   about it.
2. **What you will learn in this episode:** three or four bullets, 6 to 14
   words each, specific to this episode.
3. **Who and framing**, one sentence naming the hosts present and any guest by
   full name.
4. **Substance**, one paragraph explaining the central idea in the episode's
   real vocabulary. This is the main search surface.
5. **Comment prompt**, one episode-specific question tied to a real choice or
   disagreement. Skipped when there is none; never "let us know what you think".
6. **Chapters** (`Timestamps:` then `MM:SS - Label` lines). YouTube only turns
   chapters on with at least three, the first at `00:00`, ascending, each at
   least 10 seconds long. Five to eight for a 30 minute episode. Labels name the
   real term ("Repository renames break OIDC trust"), not "Discussion".
7. **Links**: episode page, website, LinkedIn, guest profiles, subscribe.
8. **Hashtags**: exactly five, on one line.

## Chapters

A hand-written `out/episodeNNN-chapters.txt` always wins. Otherwise the pipeline
proposes chapters from the timestamped turns of the local transcript and asks
for approval, saving the result to `out/episodeNNN-chapters-generated.txt`.
Without timestamped turns (OpenAI backend, `--transcript`) chapters are omitted
with a notice. Chapters assume the MP3 and MP4 share a timeline, as Riverside
exports do.

## Hashtags

Exactly five, filled in order:

| Slot | Value |
|---|---|
| 1 | `#DevSecOps` |
| 2 | `#DevOps` |
| 3 | The episode's strongest concept tag (`#CloudSecurity`, `#SupplyChainSecurity`, `#PlatformEngineering`) |
| 4 | The named tool or service with real airtime (`#GitHubActions`, `#AWS`, `#Kubernetes`, `#Terraform`) |
| 5 | `#DevSecOpsTalks` |

Only tag terms that were said on air and got real airtime. No `#AI` or `#tech`
on their own, no spaces, no duplicates. The builder forces slots 1 and 5 and
fills gaps from the house tags.

## Rules of thumb

- Every claim has to be in the episode.
- Plain text only; YouTube does not render Markdown.
- Full `https://` URLs.
- Short dashes only.
