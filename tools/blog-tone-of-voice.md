# Tone of voice: DevSecOps Talks episode articles

How the article on each `content/episodes/NNN-*.md` page should sound and be
built. Host names, bios and spellings live in
[`podcast-context.md`](podcast-context.md). Anti-hype phrasing and accuracy rules
live in [`writing-style.md`](writing-style.md). This file covers voice, framing
and structure, and wins where the three disagree about an article.

## Non-negotiables

- **Short dashes only.** No em dashes anywhere, Resources included. Use a
  comma, a colon, or a new sentence instead.
- **Correct name spellings.** The transcript is machine-generated and misspells
  names ("Matthias", "Andre", "devsekovs"). Always use the spellings in
  `podcast-context.md`.
- No absolute claims ("always", "never", "perfectly") unless quoting someone or
  citing evidence.
- Nothing invented. Every claim comes from the transcript, the guest context,
  `podcast-context.md`, or a linked primary source.
- Audience: engineers and leads who ship and secure software on cloud-native
  teams. Curious and skeptical, not beginners.

## Framing

- **An article, not an episode recap.** No "in this episode", no "the hosts
  discuss", no roll call of who was on the call. Make the claim directly.
- **Voice is first person plural.** "We pin actions by SHA", "we have seen
  accounts get blocked over this". The byline is DevSecOps Talks, and "we" is
  the show.
- **No host attributions, with one exception.** Not "Andrey argues", not
  "Mattias explains". When the hosts genuinely disagree, name who holds which
  view, because the disagreement is the content: "Mattias pins every action by
  SHA. Andrey thinks that just moves the risk to Dependabot." Use it only for
  real disagreements, not to credit ordinary points.
- **Introduce a guest once.** Full name and the credentials that make them
  worth hearing on this topic, in the problem section. After that, their
  experience is part of "we" unless they disagree with the hosts, which is the
  same exception as above.
- **Open with the problem, plainly.** The reader must know what and why inside
  the first two paragraphs, in concrete terms they recognise from their own
  week. Never open on vendor release news.
- **Order the piece by argument**, not by the order topics came up on air:
  problem, then where it bites, then what to do, then news or market context at
  the back.
- **Keep host experience and outside research apart.** "We saw this at a
  client" is host experience from the transcript. "GitHub's changelog says" is
  research, and it gets a link. Never present research as something the hosts
  said, or the other way round.

## Voice

The register comes from how the hosts actually talk. Read the transcript before
writing.

- Short declaratives. Break long sentences in two.
- Contractions throughout: don't, doesn't, isn't, you're.
- Address the reader as "you", and use their objects: your pipeline, your IAM
  roles, your cluster.
- Set up the objection, then answer it flatly.
- Blunt verdicts are welcome when the hosts gave them.
- Keep the hedges where the hosts hedged: "I would say", "as far as we could
  tell". Hedging reads as honest.
- Concrete over abstract: the real number, the real error message, the real
  file name.
- Credit a tool or vendor properly before disagreeing with it.

## Tells to avoid

These make a post read as machine-written:

- Essayistic scaffolding: "It is worth noting that", "which is worth saying out
  loud".
- Meta-writing about the article: "What follows is", "as we will see".
- Balanced summary sentences that commit to nothing, and paragraphs that restate
  the previous one.
- "Not X, but Y" symmetry more than once a page.
- References to material that was cut.
- Stock cadence: "pushes back", "doubles down", "dives deep", "leverages",
  "game-changing", "in today's landscape".

## Length

| Limit | Words |
|---|---|
| Target | 2,500 to 3,500 |
| Hard cap | 4,000 |
| Any one `##` section | 450 |
| Common questions section | 320 |

Cut length by dropping whole sections, not by shortening every paragraph. A
topic that cannot earn 300 words of transferable argument is a sentence
somewhere else. Cut first: setup details nobody can reuse, a quote followed by a
paragraph restating it, anecdotes illustrating a point already made. Keep
verbatim quotes to about five, in `{{< key-point >}}` callouts where the
wording earns it.

## Required structure

The page adds the teaser, the table of contents and the players above the
article, so the article starts at the problem section. In order; optional
sections are dropped when there is nothing real to put in them, never padded.

| # | Section | Required | What it has to do |
|---|---|---|---|
| 1 | Problem section | yes | A `##` heading that names the problem. What the post is about and why it matters, two or three paragraphs. Introduces any guest. |
| 2 | Topic sections | yes, 4 to 8 | One idea each, ordered by argument. Plain subject-first `##` heading, a one-line `####` question, the answer in the sentence directly below, then the evidence. |
| 3 | News or market context | optional | Only if the episode hangs off a release. At the back, with a sentence on why it matters to the argument. |
| 4 | Key numbers | optional | Two-column figure and source table, when the post carries three or more figures worth comparing. |
| 5 | What this means for teams | yes | Closes on the reader, not the show. Ends with three or four concrete things to do this week. |
| 6 | Common questions | yes, exactly 3 | `## Common questions, answered {#faq}`. See below. |
| 7 | Related episodes | yes | `## Related episodes {#related-episodes}`: prior DevSecOps Talks episodes this one builds on, linked, one line of context each. |
| 8 | Resources | yes | `## Resources {#resources}`: 3 to 8 primary sources, each with one line on what it settles. Include relevant guest links. |

There is no Summary section and no Highlights section: the teaser above the
article does the summary's job, and social copy is written separately.

### Common questions

The page turns this section into `FAQPage` structured data, so its shape is
fixed:

- The heading is exactly `## Common questions, answered {#faq}`. The `{#faq}`
  anchor is what the page looks for, and the section ends at the next `##`.
- Exactly three entries, each `### Question? {#faq-short-slug}` with the answer
  in the paragraphs directly below.
- Ask in the reader's words, the way someone types it into a search box, and
  prefer the fix over the topic: "How do I fix AWS role assumption after
  renaming a GitHub repository?"
- The first sentence of the answer is the fix, because that sentence gets
  quoted.
- No question may restate a `####` question from the body.
- Each answer stands alone, without leaning on the previous section, and only
  restates what the post already says.

### Inside the topic sections

- **A transition sentence opens each section** and carries the argument on from
  the previous one.
- **`{{< key-point >}}` callouts** on the load-bearing lines, roughly one per
  section, never two in a row. Put `{{< key-point >}}One or two sentences.{{< /key-point >}}`
  on a line of its own, not inside a paragraph.
- **`<mark>` sparingly** on a key phrase.
- **Backticks on every literal string** the reader would type, grep for or
  paste: config keys, file paths, environment variables, commands, flags.

### Heading anchors

Every `##` and `###` ends with an explicit `{#kebab-case-id}`: a space, then
`{#`, a short lowercase ASCII id with digits and hyphens only, then `}`. Ids are
unique within the article and stay stable if the heading is later reworded,
because other pages link to them. `####` questions need no id.

## Sourcing

- Every external claim gets a primary source, the vendor's own page where
  possible, linked inline.
- Say what a source does not settle.
- Correct a mistaken intuition without scoring points off anyone.
- Do not repeat the same figure more than about three times across the page.

## Pre-publish checklist

- [ ] 2,500 to 3,500 words, under 4,000, no `##` section over 450.
- [ ] No em dashes anywhere.
- [ ] Names spelled as in `podcast-context.md`.
- [ ] No "in this episode", no host attributions except named disagreements.
- [ ] Guest introduced once, by full name and credentials, in the problem
      section.
- [ ] The first two paragraphs state the problem and why it matters.
- [ ] Every `##` and `###` has a unique anchor id.
- [ ] Every `####` question is answered in the sentence right below it.
- [ ] Exactly three common questions under `{#faq}`.
- [ ] Every external claim has a primary source linked inline, and research is
      not presented as host experience.
