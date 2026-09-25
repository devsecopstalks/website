---
title: "#112 - DevOps Careers: What Should You Learn Now?"
date: 2026-10-05T12:00:00+01:00
lastmod: 2026-09-25T20:36:14+01:00
episode: 112
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/112/"
description: "Is knowing one cloud platform enough when agents can fill in the syntax? This episode explores why industry knowledge, clear communication and experience with failure deserve a place in your learning plan."
subtitle: "Knowing how a service fails can matter more than knowing its manual."
readtime: "15 min read"
image: "/images/covers/112.png"
audio_url: "https://mcdn.podbean.com/mf/web/6xeewmot61umd190/112-devops-careers-what-should-you-learn-now-.mp3"
---

Is knowing one cloud platform enough when agents can fill in the syntax? This episode explores why industry knowledge, clear communication and experience with failure deserve a place in your learning plan.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

{{< whats-in-this-post >}}

<!-- Player -->

 {{<  podbean e6dcr-1b6b84e-pb "DEVSECOPS Talks #112 - DevOps Careers: What Should You Learn Now?"  >}}

---

<!-- Video -->

## Fewer companies are hiring the juniors who need this experience {#problem}

Ask a room of engineers what they should be learning right now and you get questions back instead of answers. The question has a hard edge to it, because a lot of companies have quietly stopped hiring juniors on the theory that an agent covers the work a junior used to do. People already in the job are asking their own version of it. If you have run one vendor's database for ten years and that is your expertise, does that still pay next year?

The numbers give the worry some weight without settling it. Stanford's Digital Economy Lab tracks entry-level employment against AI exposure, and its [August 2026 update](https://digitaleconomy.stanford.edu/news/canariesaug26/) puts employment for 22 to 25 year olds in the most AI-exposed occupations about 19% below where it would be if it had kept pace with same-age workers in less exposed ones. That is a relative gap measured across occupations, not a headcount of DevOps teams, and it doesn't prove what caused any single hiring freeze. It's enough to take the question seriously.

The job changed under all of us anyway. We used to write the code. Now a good part of the day goes on directing agents and judging what comes back, which is a different job, and not everyone signed up for that one. We got into this with Julien Bisconti on our sister show, [Agentic AI in DevOps](https://podcasts.apple.com/us/podcast/agentic-ai-in-devops/id1890702822), and the honest version is that some of the joy went with it: you're juggling decisions that arrive faster than you can think about them. So this isn't only a career question. What you know decides whether you can tell that the answer on your screen is wrong.

## The manuals are in the model, your incidents are not {#failure-knowledge}

Start with what the model already has, because that's the part of your knowledge that stopped being scarce.

#### Where does the model's knowledge stop?

It stops at what got written down, and what got written down about failure is general rather than yours. Documentation describes how a thing is supposed to work, there is a great deal of it, and the models are genuinely good at that part. Failure is written about too. Google's SRE book has [a whole chapter on cascading failures](https://sre.google/sre-book/addressing-cascading-failures/), down to the feedback loops that turn one overloaded server into an outage and the traffic redirection that mitigates it. What no published material carries is the conditions in your environment: your traffic shape, your data, the assumption that turns out to be wrong at three in the morning while failover is running. That isn't the kind of knowledge that's abundantly available for training. You get it from living through it.

{{< key-point >}}Expertise isn't knowing how a thing works. It's knowing how it's going to fail.{{< /key-point >}}

Certification makes the split easy to see. Study for an AWS exam and you learn how AWS wants you to think: which service fits which scenario, what the recommended pattern is. That's useful. What the exam can't tell you is how the service behaves at your scale, or that for your particular case it's the wrong fit and you'll only find that out after a year of banging your head against it.

It shows up in consulting too. Ask a consultant whether to do this or that and you hear "it depends", which drives people up the wall and is still the correct answer. What follows is an interview: they pull details out of you until the answer is determined. <mark>Knowing which details are the relevant ones is the experience.</mark> You ask about the thing you once watched fall over.

None of that saves the legwork. Fixing a permission on a database, wiring the standard integration, writing the boilerplate migration: that work is going, and being fast at it isn't a position worth defending.

## Scrutiny scales with what breaks {#risk-tiers}

If failure knowledge is the valuable part, then the amount of it you need is set by what happens when the thing fails.

#### How much should you check the agent's work?

As much as the consequences of being wrong demand, and the tiers are further apart than the discourse suggests. A hobby project is YOLO territory: vibe code it, ship it, you only live once. Internal supporting systems sit close to that, and leaning on the agent without heavy validation of the result is a reasonable trade.

Business critical is where the reading starts. You review the code, and reviewing it means understanding the domain it touches. If there's TCP handling in there, you need the protocol well enough to tell whether the agent is making things up, because it will be fluent either way.

Then there's the tier where a mistake kills someone. Life support. Traffic lights. Those systems come with obligations that have nothing to do with how good the reviewer is, and medical software is the example whose rulebook is public. The FDA's [General Principles of Software Validation](https://www.fda.gov/media/73141/download) covers medical device software and the software used to design, develop or manufacture a device, and it scales validation effort to the risk the software carries, with the testing and the traceability to match. That guidance doesn't reach traffic lights, so don't borrow its checklist for them. What carries across the tier is the shape: your team must justify its validation approach against applicable requirements and the system's risks, and an agent in the toolchain doesn't remove a line of that justification.

{{< key-point >}}The agent doesn't get more careful as the stakes rise. Everything that does has to come from you and from your process.{{< /key-point >}}

So name the tier each of your services is in before an agent has commit rights to it, and set the review rule from the consequence of that service failing rather than from how the code looks. A service holding money and a service rendering a marketing page don't need the same review, and treating them the same means one of them gets the wrong amount of attention.

## Say it in the words the literature uses {#language}

Given you're now directing rather than typing, how you say what you want turns into a technical skill.

#### Does knowing how to describe it replace knowing the subject?

No, and this is where the two of us disagreed on air. Mattias read the argument as a shift away from subject knowledge toward being able to describe and discuss it. Andrey wouldn't have it: the knowledge is still the thing, and articulation is what multiplies it rather than what replaces it.

The example we kept coming back to is Matt Pocock, who came into software from voice coaching. He taught singing, accents and Shakespeare at drama schools, taught himself JavaScript on the side, and told the [Pragmatic Engineer podcast](https://newsletter.pragmaticengineer.com/p/ai-skills-with-matt-pocock) that being able to express himself clearly is what let him stand out among engineers who knew more than he did. Gaps in knowledge were a matter of study. He's now the author of [a widely used set of agent skills](https://github.com/mattpocock/skills), including `grill-me`, which does nothing cleverer than instruct the agent to interview you relentlessly before it writes anything.

That advantage transfers directly. Models work off language, so using the industry's terms may help you get more precise results than approximating in your own words. This is not an argument for a prompt engineering course or for Toastmasters. It's an argument for going back to the classics that set the vocabulary, [Refactoring](https://martinfowler.com/books/refactoring.html) and the clean code canon among them, because that is where the shared terms come from and precise terms are what you have to steer with. We haven't established whether the models we use were trained on these particular books. What we can say is that vague descriptions get vague results.

{{< key-point >}}If you can describe what you want well, you can also ask the model to teach you back the parts you're missing.{{< /key-point >}}

The same logic is why writing the project's context down pays. Every fact that lives only in your head makes you a proxy between the agent and the work. Put it in [`AGENTS.md`](https://agents.md/) and the agent grounds itself there instead of waiting on you.

## Every answer comes back Postgres {#defaults}

Clear instructions still land in a model that has opinions of its own, and those opinions have a shape.

#### Why does the model keep picking the same stack?

Because its defaults come from its training, not from your constraints. Ask for a database and you get Postgres. You want vector search, there's [an extension](https://github.com/pgvector/pgvector) for that. You want document storage, it's already in the box: [`json` and `jsonb` columns](https://www.postgresql.org/docs/current/datatype-json.html), with `jsonb` supporting GIN indexing and containment operators, no extension required. The database story is more or less over and Postgres for everything is a defensible answer for most teams, which is exactly what makes it easy to accept without deciding anything.

House style differs between models in ways that show up within one session. Run the same grilling interview through Codex and through Claude and the questions you get are not the same questions. One heads for the enterprise-grade version and wants to settle details you don't care about, down to whether the button corners are rounded. The other takes sane defaults and doesn't overcomplicate it. Neither is wrong, and you'll prefer different ones on different days.

{{< key-point >}}A default you didn't choose is still a decision, and it came from someone else's training data.{{< /key-point >}}

This is the practical reason the knowledge question matters this quarter and not in some future one. Overriding a default requires knowing why it's wrong for you. If you can't say why this workload shouldn't sit on the default stack, you're going to ship the default stack, and the first time you find out it was a poor fit is when it's carrying traffic.

## A tool expert with no industry {#domain-over-tool}

Which brings up the thing people are actually asking when they ask what to learn: go deeper on the vendor, or wider across vendors.

#### Does going deep on one vendor still pay?

It pays when it's paired with an industry, and it's a poor bet in a vacuum. Stack two people against each other: a GCP expert who has spent years in fintech, and someone with deeper AWS knowledge who has never worked in the sector. We'd take the first one most days. Concepts carry across clouds anyway. If you understand VPCs, you understand the shape of the network on any of them, and the specifics are lookup.

Ideas transfer across industries too, just not cleanly. A ledger is a ledger, and then the transactions on it work differently depending on who's regulating them. Healthcare has one set of rules, fintech another, crypto another. Build FDA-approved medical devices and there are [criteria for cybersecurity in premarket submissions](https://www.fda.gov/medical-devices/digital-health-center-excellence/cybersecurity) you have to design for from the start. Carry the approach that worked in your last industry into that one and people will tell you it doesn't apply.

{{< key-point >}}If you're a tool expert, everything starts to look like a nail.{{< /key-point >}}

We've watched that play out as every problem getting solved with database stored procedures, which ends badly on a long enough timeline. The generalized version of the mistake is old. Twenty years ago teams compared Agile and Scrum tools against each other without first working out their own process, then inherited the workflow of whichever tool won and made their people work that way. Figure out the process that fits the people you actually have, then find a tool that supports it. Hard specialization in one tool makes that harder, so widening is the smarter default.

## What is actually inside the container {#black-box}

The other direction to widen in isn't a vendor at all.

#### What does "understand the business" mean for an infrastructure person?

It means knowing what the workloads do with data and with money, not only keeping them running. There's a standing temptation in infrastructure to treat everything above the runtime as a black box. Developers hand you containers, something runs inside them, you make sure they come up, don't fall over, and emit telemetry. That is a real job and it worked for years. It's also the exact job an agent can do now, so it's worth asking what you're adding on top of it.

What you can add is what's inside. If there's PII or PHI in that container, the network probably shouldn't look the way it looks, and segregation stops being a nice-to-have. Most digital businesses make money by processing information in some particular way, so the useful question is which processing is the one that pays, and what you could do to it that the competition can't.

{{< key-point >}}Every container gets treated the same until someone knows what's in them.{{< /key-point >}}

That knowledge changes where you sit. It puts infrastructure and security people in the room where the business decides what it's building, rather than receiving the result as tickets. Security in particular has a claim to that seat right now: there was already more work than people, the volume of vibe-coded software is rising, and models are getting better at reverse engineering and finding bugs in what already shipped. Cleaning up the legacy we have today looks like enough work for a career.

## Rebuild the SaaS and you become the vendor {#internal-vendor}

Understanding the business also tells you what not to build, which is where the current enthusiasm needs a brake.

#### Should you replace the SaaS your team pays for?

Build the small thing for yourself, and think hard before the team depends on it. The idea that SaaS is finished has serious people behind it: Satya Nadella argued on [the BG2 podcast](https://open.spotify.com/episode/640nHdVvWgOp8tYShOpXH1) that business applications are CRUD databases with business logic wrapped around them, and that the logic collapses into the agent tier. That's a claim about business applications from someone selling the agents, and it doesn't say anything about whether your team should spend next month rebuilding your issue tracker.

We'd disagree with the strong version. Rebuild every SaaS you use and you disperse your focus across all of them. What you were buying was never the CRUD, it was the maintenance and the thousand edge cases someone else already found. Internal tooling for yourself is fine and often worth it. The moment your team starts using it, you're an internal vendor with users, a support queue and a backlog.

{{< key-point >}}Implementation is more or less solved. The question left is what to implement, and where your attention goes instead.{{< /key-point >}}

So measure it against what else you could be doing. Being productive on internal tooling while the business problem sits untouched is still a choice about priorities, and it's easier to make by accident now that building the thing is cheap.

## What this means for teams {#what-this-means}

The short version: the knowledge that stays valuable is the knowledge that wasn't published, and it's worth more when it's attached to an industry rather than to a vendor. Nothing here is a reason to stop learning tools. It's a reason to stop learning only tools.

Four things worth doing this week:

- **Write down a failure you've lived through.** The wrong assumption, the symptom, what fixed it. That's the knowledge no manual carries, and in a runbook or an `AGENTS.md` it's knowledge your agents don't have to guess at.
- **Name the tier for each service you own.** Hobby, business critical, or someone gets hurt. Write the review rule that goes with each one, sized to what that failure costs, before an agent touches the repository.
- **Pick a domain to go deep in, not just a stack.** One industry's regulations and money flows, learned well enough to say which default is wrong for it.
- **Before you rebuild something you pay for, write down what you'd stop doing.** If the honest answer is the business problem you were hired for, buy the SaaS.

## Common questions, answered {#faq}

### What should a junior engineer learn to get hired in 2026? {#faq-junior-skills}

Combine three things: how systems fail, what the business actually does, and the ability to describe both clearly. Failure knowledge is the part that stayed scarce, because documentation describes how things are supposed to work and the conditions in a specific environment mostly never get written down. Domain understanding is what makes that knowledge worth something to a particular employer, since a regulated industry's constraints don't fall out of a general-purpose model. Clear articulation is the multiplier on both: it's how you get a useful answer out of an agent, and how you show a person that you knew what you were doing.

### How do I decide what to learn next when the tooling changes every month? {#faq-what-to-learn}

Choose by what your business runs on and what would hurt if it broke, not by what's trending. Concepts port between clouds, so the return on the third vendor's specifics is low compared with learning the regulations, money flows and data sensitivities of the industry you're in. One stack you know deeply plus one industry you understand is a stronger position than three clouds at surface level. The model will fill in the syntax either way.

### How do I get better results from a coding agent without a prompt engineering course? {#faq-better-prompts}

Use the industry's own terms, and write the project's constraints down where the agent reads them. Models work off language, so naming a pattern precisely may get you closer to what you meant than describing it loosely, which is a good reason to revisit the classics that set the vocabulary. Put the facts that live in your head into `AGENTS.md` so the agent grounds itself instead of asking you. And ask it to interview you before it writes: that is all the popular `grill-me` skill does.

## Related episodes {#related-episodes}

- [Episode 7, How Do We Learn](/episodes/007-how-do-we-learn/) is the pre-AI version of this conversation, on how we each kept up with the industry when reading the docs was the job.
- [Episode 32, Getting hired as an infrastructure automation person](/episodes/032-getting-hired/) covers the career side, from what to show an interviewer to which skills travel between employers.
- [Episode 100, 100 Episodes Later: What Still Matters in DevSecOps](/episodes/100-100-episodes-later-what-still-matters-in-devsecops/) is the longer audit of which fundamentals held up over six years of the show.
- [Episode 111, AI Agents: When Helpful Becomes Harmful](/episodes/111-ai-agents-when-helpful-becomes-harmful/) takes the scrutiny question from the other end: what the agent can reach when your instruction is vague.

## Resources {#resources}

- [Stanford Digital Economy Lab, canaries update, August 2026](https://digitaleconomy.stanford.edu/news/canariesaug26/) gives the entry-level employment gap in AI-exposed occupations and is careful about what it does and doesn't attribute to AI.
- [The Pragmatic Engineer, AI skills with Matt Pocock](https://newsletter.pragmaticengineer.com/p/ai-skills-with-matt-pocock) is the source for the voice coaching to software path and the argument that fundamentals matter more with agents, not less.
- [mattpocock/skills on GitHub](https://github.com/mattpocock/skills) is the skills collection itself, including `grill-me`, so you can read what these prompts actually contain.
- [AGENTS.md](https://agents.md/) is the format for the file agents read for project context, with no required fields to argue about.
- [Google SRE book, Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/) shows how much about failure is published, and by omission how much of your own system's behavior isn't.
- [PostgreSQL, JSON types](https://www.postgresql.org/docs/current/datatype-json.html#JSON-CONTAINMENT) sets out the difference between `json` and `jsonb`, and documents containment and GIN indexing for `jsonb`.
- [FDA, General Principles of Software Validation](https://www.fda.gov/media/73141/download) is the medical device case only: the manufacturer picks and justifies a validation approach scaled to risk, with testing and traceability, for device software and for software used to design, develop or manufacture a device. It says nothing about other safety critical sectors.
- [Satya Nadella on the BG2 podcast](https://open.spotify.com/episode/640nHdVvWgOp8tYShOpXH1) is the primary source for the business applications collapse claim, in his own words and at his own length.
