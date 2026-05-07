# DevSecOps Talks — writing style (articles & podcast copy)

## Show identity

- **Podcast:** DevSecOps Talks (`devsecops.fm`).
- **Hosts:** Andrey, Paulina, and Mattias (when mentioning hosts by name, use these spellings).
- **Audience:** DevSecOps practitioners — engineers and leaders who ship and secure software; assume curiosity and skepticism, not beginners-only fluff.

## Tone

- **Plain language:** short sentences, concrete examples. Prefer clarity over rhetorical flourish.
- **Podcast descriptions / teasers:** keep them **short**. Prefer **questions** over long declarative paragraphs where it fits.
- **Avoid** filler praise and hype adjectives. Do **not** use words such as: **delve**, **engaging**, **enlightening**, “warmly welcome”, “thrilled to announce”, or similar stock-podcast phrasing.

## Article structure (markdown)

Use this section order unless the transcript truly cannot support one of them:

1. **Summary** — first section heading must use an explicit anchor id (see below).
2. **Key Topics**
3. **Highlights**
4. **Resources**

### Heading anchors (required for new drafts)

Hugo can expose IDs on headings using attributes on the **heading line**:

- First heading line must be: `## Summary {#summary}` (not bare `## Summary`).
- Every major `##` or `###` that might be linked or cited should have a **unique** `{#slug}` — short **kebab-case** ASCII slugs (`{#key-topics}`, `{#resources}`, etc.).
- Do **not** duplicate the same `{#id}` twice in one article.

Reviewers should flag missing `{#summary}`, duplicate IDs, or headings without anchors where readers would reasonably deep-link.

## Podcast descriptions (RSS / Podbean / social)

- Describe what listeners get **without inventing** facts not grounded in the episode or article.
- You may mention recurring themes (security, platform engineering, cloud, AI in delivery) when accurate.
- Prefer straightforward wording over marketing jargon.

## Cross-checks

- Names of guests, companies, and tools must match **`podcast-context.md`** and verified references — web-search URLs before asserting versions or GA dates.
