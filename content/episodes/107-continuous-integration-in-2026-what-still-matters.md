---
title: "#107 - Continuous Integration in 2026: What Still Matters"
date: 2026-07-13T12:00:00+01:00
lastmod: 2026-07-13T12:00:00+01:00
episode: 107
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/107/"
---

CI changed how teams integrate code, but its core promise remains the same: integrate often and keep the mainline green. Andrey and Paulina trace its history and examine how Git, merge queues, and modern pipelines changed the mechanics.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean u58mt-1b0d40d-pb "DEVSECOPS Talks #107 - Continuous Integration in 2026: What Still Matters"  >}}

---

<!-- Video -->

## Summary {#summary}

Continuous integration is old enough to feel obvious — which is exactly why the hosts revisit it for anyone who inherited the practice without ever seeing the pain it solved. Andrey tells the story of the "nightly build" era at Ericsson, where a colleague came in at dawn to tell developers what they'd broken overnight, and traces how CI emerged to keep integration frequent and the mainline permanently green. Andrey and Paulina push on the balance nobody talks about: run too little and you ship breakage, run everything on every change and a one-line fix waits hours. The genuinely new part is the 2026 twist — Andrey describes wiring an AI reviewer into GitHub Actions plus a local coding agent that argues back with it on the same pull request, though he's blunt that no automation saves you from the developer who vanishes for a month and drops a 30,000-line pull request (a review slog Paulina knows first-hand) on a human.

## Key Topics {#key-topics}

### Why CI exists: the nightly-build world before it {#why-ci}

The hosts start where a lot of newer engineers don't have context: what came *before* continuous integration. Andrey has "seen things" — tooling that predates Jenkins, and Hudson, later renamed Jenkins, back in its mid-2000s early days, when it was a genuine upgrade rather than legacy baggage.

The problem CI solved was **integration happening too late**. Teams piled changes onto the mainline all day, and a build server chewed through them overnight. Andrey's story: at Ericsson, a colleague named Christian came in very early every morning, checked the daily builds, and warned developers *before* they pulled that something was broken — so the team could hold on to a known-good baseline to test against. Problems were discovered post-factum, feedback to developers was slow, and the whole organization moved at the speed of that nightly cycle.

Continuous integration flipped it. The practice is defined by **integrating frequently — at least daily — and verifying every integration with an automated build and tests**, so integration errors surface immediately instead of the morning after. How you *enforce* that has evolved; protected-branch checks on a pull request are one modern workflow, but the core idea is frequent integration, not any single gating mechanism.

CI is fundamentally a multi-person practice — it exists because several people push changes that have to work together without breaking each other's work. Andrey's qualification: if you work alone, you technically don't *need* it, since you're integrating on your own all the time — but a centralized server running automated verification is still useful, because it catches the things you miss.

### Git changed the mechanics {#git}

Andrey walks through a piece of history that's easy to miss. In older version-control systems, where branching was often expensive, one common approach was simply to build every incoming change to find problems sooner. Git's lightweight branches — and the hosted forges built around them — changed that: you could receive a change into a central place *without* it touching the mainline everyone works on, run the same build and tests you'd run on main, confirm it's buildable and green, and only then merge.

That underpins a common modern workflow: the mainline stays stable and green, so anyone who checks out the repo can build, run tests, and start their feature immediately — instead of first cleaning up after whoever came before them. A change does not reach mainline until the required checks pass. As the hosts noted, developers can get creative about skipping pipelines — but enforcing that gate covers the 90% of cases that matter.

### The balance nobody gets right: fast feedback vs. thorough testing {#balance}

Once main is reliably green, you can layer heavier testing on top — you already know the small things work. Historically that spawned the same nightly (or even weekly) pattern one level up: long-running test queues, something breaks, someone has to bisect which change did it and file a report, and by then nobody remembers what they did. So the pattern became: run as much testing as physically possible on *every* change, so feedback reaches the developer while the context is fresh — fix trivial breakage to unblock main, or revert to hold the quality line.

But Andrey and Paulina are blunt that this is a tradeoff, not a maximize-everything problem:

- Test too little and breakage slips through.
- Test *everything on everything* and a small change waits hours for tests that don't even apply to it.

The practical split: run build, unit tests, linting, and static analysis on the pull request for fast feedback; push expensive integration and QA testing later — ideally still per-change, but constrained by reality. Andrey's example: testing on **custom hardware or physical phones** limits you to how many devices you have and how well flashing and loading is automated. Paulina adds that the right shape depends entirely on what you're building — mono-repos, multi-repo systems that integrate into a larger deployable, and complex topologies all change the answer.

### One server or many: how CI/CD tooling consolidated {#tooling}

CI didn't always live where your code did. The hosts trace the tooling arc: it started with a separate CI/CD server alongside a separate version-control system — Build Forge, Jenkins, TeamCity, CircleCI — and in bigger or more legacy organizations that split persists, with a dedicated CI instance and separate CD instances (sometimes one for non-production and one for production). Jenkins still shows up where teams want a centralized, self-hosted setup or don't want to pay for GitHub Enterprise. The modern pattern, though, is to combine the version-control server and the CI/CD server into one thing — GitHub being the obvious example — so developers don't jump between systems to see how a change is building and integrating. Ownership shifts too: the CI part tends to be more distributed and team-owned, versus a central team that owns the pipelines. Andrey notes one GitHub Actions advantage: Jenkins commonly centered automation on a single Jenkinsfile, while GitHub Actions natively organizes multiple workflow files — so a central team can still build the mainline CI/CD criteria as reusable workflows that teams pull in, then extend past the merge.

### Merge queues, regulated fields, and higher risk profiles {#merge-queues}

The hosts touch on **merge queues** — serializing merges so the mainline is validated in the exact order changes land. They're rare in the wild; Paulina hasn't seen them much. Andrey associates them with higher-risk profiles: hardware testing, or regulated domains like medical devices (FDA-regulated software). Paulina, who worked on a medical-device-regulated team, adds a nuance: getting a change *merged* wasn't the hard part — it was the long, paperwork-heavy approval process to actually *release* to devices that made things slow.

### The 2026 twist: two AIs arguing on your pull request {#ai-review}

This is where the "revisited" earns its keep. Andrey describes a pattern FivexL is using now: install a coding-agent CLI onto a GitHub Actions runner and have it run an automated review on every pull request. FivexL's open-source [`shared-workflows`](https://github.com/fivexl/shared-workflows) repo is a working example — it reads the diff, picks relevant review dimensions, posts inline comments, and uses **AWS Bedrock** to serve the model so there's no third-party API key and the data stays inside AWS.

The clever part is the loop. On the developer's side, a *local* coding agent runs a skill: open the PR, wait for builds, fix the build if it fails, and when the AI reviewer leaves inline comments, **debate them** and converge on the best outcome. Two AIs feeding each other comments and iterating — so by the time a human looks, there's far less to do. Andrey is careful: the models still miss things constantly, even the best ones, and they can head in the wrong direction, so the human stays in the loop. But it's a strong feedback loop built on infrastructure you already have.

Paulina extends it: run several specialized reviewers — one for testing, one for security — each driven by repository guidelines that encode how you want code structured (reusable functions, updated docs, test coverage, security checks). And she names the real cost from experience: adding ~30,000–40,000 lines in one place meant round after round of review, where each fix introduced something else, and reviewing consumed far more time than generating. Andrey's counter-lever: interview the AI *before* it writes code — align on requirements up front and you spend less time in review afterward. Though, as Paulina notes, that only works when requirements are specific, which is harder when the business side is involved.

### Small changes still win {#small-changes}

Andrey credits Paulina with the point that ties it together: keep changes **small**. Small, incremental changes are easy to review, easy to integrate, and make failures obvious. A 30,000-line pull request isn't humanly reviewable — and even the tools strain, with GitHub and its review UI getting painful past a certain size. And it's not just an AI problem: Andrey points at the human who vanishes for a month and dumps a giant merge — "look, I've been busy" — as the same antipattern. Split the work, deliver it in small pieces.

## Highlights {#highlights}

- **Andrey on the world before CI:** At Ericsson, a colleague named Christian came in at dawn every day to check the nightly build and warn developers what they'd broken before they pulled. "People will pile up stuff on the main branch and then machinery will process that during the night" — and problems surfaced the morning after. That daily ritual is exactly what continuous integration was invented to kill. Listen to episode #107 for how the practice actually emerged.

- **Andrey on protected-branch gating:** Enforcing that a change can't reach mainline until required checks pass is one modern way to keep CI's promise — a protected-branch guarantee layered on top of the practice, not CI itself. The point isn't ceremony — it's that anyone who checks out the repo can build and test immediately, instead of first fixing whatever the last person left broken. Catch the episode for why the green mainline is the whole game.

- **Paulina on the over-testing trap:** You can have too little testing — or so much that a tiny change waits hours for tests that don't even apply to it. "You also shouldn't run everything on everything." The balance depends entirely on how your system is structured. Tune in for how the hosts think about drawing that line.

- **Andrey on two AIs on one pull request:** An AI reviewer runs in GitHub Actions and leaves inline comments; a local coding agent then *debates those comments* and converges on a fix — "two AI working together against each other." The human reviews what's left. Listen for how FivexL wired this on top of AWS Bedrock with no external API keys.

- **Andrey on disappearing developers:** A 30,000-line pull request isn't humanly reviewable — and it's not only AI that does it. "There are humans who will just disappear for a month and merge this like, 'look, look, I've been busy.'" Small, incremental changes aren't a nicety; they're what makes review and integration possible at all. Catch the full episode for why this best practice matters more, not less, in the AI era.

## Resources {#resources}

- [Continuous Integration — Martin Fowler](https://martinfowler.com/articles/continuousIntegration.html) — The canonical essay defining CI: integrate at least daily, verify every integration with an automated build and tests. Andrey's recommended read; substantially revised by Fowler to reflect two decades of change.

- [Continuous Delivery (Jez Humble & David Farley)](https://martinfowler.com/books/continuousDelivery.html) — The Jolt-award-winning book the hosts point to for the CD side, introducing the "deployment pipeline" as the automated backbone of build, test, and deploy. (Andrey couldn't place Farley's last name on the mic — it's David Farley.)

- [FivexL `shared-workflows` (GitHub)](https://github.com/fivexl/shared-workflows) — FivexL's open-source reusable GitHub Actions workflows, including the AI code-review reusable workflow Andrey describes: it reads the PR diff, picks relevant review dimensions, and runs models via Amazon Bedrock with OIDC-based credentials (no long-lived AWS keys).

- [Managing pull request merges with merge queue — GitHub Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) — Official docs on the merge-queue mechanism the hosts discuss for keeping a strictly validated mainline under high change volume.

- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — Managed access to foundation models on AWS; the backend FivexL uses so review workflows consume models without third-party API keys and keep data inside AWS.

- [Episode #61 — GitHub Actions and the Evolution of CI/CD](/episodes/061-github-actions-and-evolution-of-ci-cd/) — Earlier DevSecOps Talks episode tracing the tooling shift from standalone CI servers (Jenkins, TeamCity, CircleCI) toward version-control-integrated pipelines.

- [Episode #101 — Infrastructure as Code in 2026](/episodes/101-infrastructure-as-code-in-2026-still-essential-or-already-changing-/) — Companion "revisited for 2026" episode covering the GitOps-vs-CI question and how AI is reshaping delivery practices.
