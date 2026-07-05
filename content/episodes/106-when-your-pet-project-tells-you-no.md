---
title: "#106 - When Your Pet Project Tells You No"
date: 2026-07-06T12:00:00+01:00
lastmod: 2026-07-06T12:00:00+01:00
episode: 106
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/106/"
---

This is a lighter summer episode about building things for yourself. The hosts talk personal projects, fitness data, AI agents, and the honest gap between having a smart plan and doing the work.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean szr9r-1b05601-pb "DEVSECOPS Talks #106 - When Your Pet Project Tells You No"  >}}

---

<!-- Video -->

## Summary {#summary}

Summer break means free time, and free time means pet projects. In this lighter episode, Andrey walks Mattias and Paulina through the AI training coach he's spent a month building out of his own body — Garmin activities routed through Strava's API, a Renpho scale's body composition, VO2 max and ventilatory-threshold stress tests, blood work, even HRV files he still has to export by hand. The engineering is the interesting part: he applies the same agentic patterns he works with elsewhere — structure everything as JSON, give the model a table of contents, and dispatch sub-agents so the main session doesn't drown in context. The takes are pointed: Strava's own AI is so shallow it congratulated a rider for a "great bike ride without helmet"; every commercial coaching app is built around selling you your first marathon, which is exactly the customer Andrey isn't; and turning 40 means the plan is now all about injury prevention and telling him *no* when he has a "stupid idea." The honest catch, raised by a co-host: a generated plan still can't make you do the work — some people need a human who'll be disappointed in them.

## Key Topics {#key-topics}

### It all comes down to data and APIs {#data-pipeline}

Andrey's starting point is blunt: "everything boils down to data and APIs." His Garmin watch is the primary recording device, but as of mid-2026 Garmin doesn't hand out a free health API — so the data takes a longer road. The watch syncs to **Strava** (the social network for sporty people), and Strava *does* let you build OAuth apps against its V3 API. Two separate costs sit on that path, and it's worth keeping them apart: Andrey pays for a Strava subscription — "it's like 50 euro a year," which he considers a fair price — and that subscription is also what unlocks Strava's own AI features for him. Developer access to the Strava API is a distinct thing with its own terms. Either way, the payoff for Andrey is that he pulls the raw activity files down through the API and *owns his own data* rather than renting a view of it.

Not everything flows through that pipe. Garmin's wellness metrics — HRV and the rest — never make it to Strava, so for now Andrey manually exports them, and a purpose-built agent "skill" knows to expect a zip file landing in the Downloads folder and picks it up from there. Body composition from a **Renpho** scale is another source he pulls in — he described it as an easy API/OAuth-style integration — and he manually feeds in the things that have no API at all: stress-test results (VO2 max, ventilatory threshold) and blood tests. Assembling all of it gives a genuinely comprehensive picture of his health, which is what makes real goal-setting possible.

### Structuring health data for an LLM {#wiki-llm}

The build reads like a masterclass in agent context engineering. Andrey structures everything as JSON with a table of contents "so the models can find things quickly," and leans on what he calls the recursive-language-model idea: instead of stuffing every file into one prompt, the system dispatches sub-agents to extract only what's needed "so the main session is not being polluted by the unnecessary context." Around all of it sit a pile of Python scripts that simplify extraction and persist state — the unglamorous plumbing that, as he notes, "was easy" compared to the design decisions.

### Why the off-the-shelf apps don't fit {#off-the-shelf}

There are plenty of AI-enabled training apps already — so why build your own? Because, Andrey argues, they're all structured around a *goal*: sign up for your first marathon, your first 5K, your first 10K. That's where the money is, and that's who those apps are optimized for — people making an emotional purchase around a single race. "I don't give a damn about marathons, I did too many of them," he says; he's after long-term goals, and none of the apps focus on that.

He's also unimpressed with the AI he's already paying for. Strava's assistant, gated behind the paid tier, seems to run a small model that just rephrases your activity description with "no thinking whatsoever." His favorite example: a rider wrote that he'd forgotten his helmet and had to turn back home — and the AI cheerfully summarized it as a "great bike ride without helmet."

### What the agent actually does {#what-the-agent-does}

The agent's main job is planning the week and balancing everything against real constraints. Andrey tracks a deliberately mixed load — running and trail running, stationary biking as a no-impact option, open-water swimming — and wants the plan to account for the days he *can't* run. The day of recording he'd had shock-wave therapy on a knee tendon with a small tear, which means no tendon loading today or tomorrow, something easy on Wednesday, and every downstream session reshuffled around that. Where does strength training go relative to a hard interval — before, or after? That balancing act, across his life, his injuries (he's working with physios), and his ambitions, is what he wants the system to own.

It also nags. When he gets too stationary — a day on the indoor bike often means fewer steps — he wants something to yell at him to hit his step count, log his sleep, and do his foam rolling for injury prevention. A co-host who's picked up back problems from years of desk work connected with the theme: sitting, cycling, running, and swimming are all "closed position," and no coach had ever flagged that trade-off for them.

### Tweaking the system: the foam-rolling dedup {#tweaking}

The system is still evolving, and Andrey is candid about the fiddly parts. Garmin has no activity type for foam rolling, so his workaround is to log it under Pilates and rename it — but then the same session shows up twice and has to be de-duplicated. What started as deduping on activity *name and type* had to be reworked to dedupe on the activity *ID* instead. It's the kind of small, constant tweaking that comes with owning your own tool — and a month in, he says he really likes the results.

### The limits: discipline still has to come from you {#discipline}

For all the automation, Andrey is clear the plan still relies on self-discipline — and a co-host pushed back that this is exactly where generated plans fall down. Having trained under a coach who checked up on them since the age of four or five, they argued some people simply need a *human*: someone who'll shout, and someone who'll be disappointed if the work isn't done. A plan on a screen is too easy to ignore.

Andrey's own answer is that he's a self-starter who stays on track, so what he actually needs from the system is two things: an initial plan with the right *volume*, and *pushback*. The morning of his therapy, after a hard race weekend, he'd wanted to squeeze in a quality session of strides — and the system talked him down: he'd already ramped hard for two weeks and run a 10K trail race with 800 metres of climbing (and just as much pounding on the descent), so the call was to let the tendon heal and slot the quality work later in the week if his recovery held. Left to himself, that's the impulsive decision the coach exists to catch.

## Highlights {#highlights}

- **Andrey on why he owns his data:** "Everything boils down to data and APIs." Garmin won't give him a free API, so he routes his watch through Strava's OAuth API and pulls the raw files down himself — because a training coach you build is only as good as the data you actually control. A clean look at the plumbing behind a personal health project. 🎧

- **Andrey on the state of fitness AI:** A rider logged that he forgot his helmet and had to go home — and Strava's AI summarized it as a "great bike ride without helmet." "No thinking whatsoever," Andrey says. If you've wondered whether the AI features bolted onto your favorite apps are real, this one's for you. 🎧

- **Andrey on why he built his own:** "I don't give a damn about marathons — I did too many of them." Every commercial coaching app is built to sell you your first race, because that's where the emotional purchase is. His goal is the opposite: staying consistent and injury-free for the long haul. Tune in for the case against goal-shaped fitness apps. 🎧

- **Andrey on turning 40:** "Now I cannot just go with any kind of training — consistency and injury prevention is the key." The training a 25-year-old gets away with stops being forgiving. Hear how he re-architected his week around recovery instead of PBs. 🎧

- **Andrey on what he really wants from the agent:** "It's kind of balancing the recovery and my stupid ideas." He's a self-starter — what he needs isn't motivation, it's an initial plan and something to push back when he wants to cram a hard session in the morning of knee therapy, right after a hard race weekend. Give it a listen. 🎧

- **A co-host on the limits of a generated plan:** "I still need a human who can shout to me and someone who's going to check if I've done it." A plan on a screen is easy to ignore — some people, trained since childhood, need disappointment on the other end. The honest counterpoint to the whole build-it-yourself dream. 🎧

## Resources {#resources}

- [Strava API V3 — Authentication docs](https://developers.strava.com/docs/authentication/) — The OAuth flow Andrey uses to pull his Garmin-synced activity files out of Strava and own the data. Requires registering an app; note that developer API access and a personal Strava subscription (which is what unlocks Strava's AI features) are billed separately.

- [Garmin Connect Developer Program — Health API](https://developer.garmin.com/gc-developer-program/health-api/) — Garmin's official route to HRV, sleep, steps, and activity data. Note *why* Andrey goes around it: commercial use requires a license fee and access is not free self-serve — hence the Strava workaround and the manual HRV exports.

- [renpho-api on PyPI](https://pypi.org/project/renpho-api/) — An unofficial Python client for pulling body-composition data (weight, body fat, muscle mass, and more) from Renpho smart scales — the kind of easy API source Andrey folds into his pipeline. Like the other community Renpho clients, it authenticates with your account credentials/token rather than a documented public OAuth API.

- [Recursive Language Models — Alex L. Zhang](https://alexzhang13.github.io/blog/2025/rlm/) — The context-management idea Andrey applies: have the model write code to dispatch sub-agents over slices of data so only the extracted results — not the whole document — ever enter the main context window.

- [Ventilatory threshold estimation from HRV — Kubios](https://www.kubios.com/blog/ventilatory-threshold-estimation-based-on-hrv/) — Background on the VO2 max, ventilatory-threshold, and HRV metrics Andrey feeds into his system, and how HRV can approximate training-zone boundaries non-invasively.

- [Andrey Devyatkin](https://andreydevyatkin.com) and [Boris](https://www.getboris.ai/) — The host's professional work in agentic AI and DevOps automation — a related line of agentic tooling, mentioned here for context rather than because it shares this project's internals.

- [Episode #104 — When AI Coding Gets 10x More Expensive](/episodes/104-when-ai-coding-gets-10x-more-expensive/) — A companion take on living with AI agents day to day: the cost, the tooling, and where the productivity story holds up.
