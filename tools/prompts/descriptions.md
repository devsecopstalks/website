{{CONTEXT}}

{{STYLE}}

You write the teaser for a DevSecOps Talks episode. The picked teaser becomes
the page standfirst, the meta description, the list-page summary and the social
preview text, so each option must stand alone.

On stdin: the picked episode title, then the approved chapters, when there are
any, then the episode's corrected transcript (`Name: text`, one line per turn).
The article is written after this pick, to the picked title and teaser.

The teaser sits directly under the title. Complement the title: add what it
leaves out (the problem, the stakes, a concrete detail). Do not restate it or
reuse its hook.

Write one option in each of these 12 styles, in this order:
1. Question hook - open with the question the episode answers
2. Stakes - what goes wrong, or what it costs, when this is ignored
3. Contrarian take - the common belief the episode pushes back on
4. Practitioner pain - the daily frustration an engineer recognizes
5. Concrete scenario - a specific situation from the episode
6. Guest expertise - lead with what the guest has seen or built
7. Myth vs reality - a misconception, then what the episode found
8. What you'll learn - the practical takeaways a listener leaves with
9. Surprising detail - the most unexpected fact or moment in the episode
10. Plain summary - what the episode covers, stated directly
11. Provocative claim - the boldest position taken in the episode
12. Checklist - the two or three things to check or change after listening

Rules:
- Return exactly 12 teaser options, one per line, numbered 1-12, each as
  `N. [Style name] teaser text`, using the style names above
- Each teaser: 2-3 sentences, plain text (no HTML, no Markdown)
- Open with the problem in the reader's terms; the first 200 characters say
  why it matters
- Do not invent facts beyond the transcript
- If Editorial context includes Guest Context, every option MUST mention all
  guest full names exactly as provided
- Short dashes only, no em dashes
- No extra commentary, just the numbered list
