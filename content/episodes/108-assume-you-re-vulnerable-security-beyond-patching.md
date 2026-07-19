---
title: "#108 - Assume You’re Vulnerable: Security Beyond Patching"
date: 2026-07-20T12:00:00+01:00
lastmod: 2026-07-20T12:00:00+01:00
episode: 108
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/108/"
---

Are AI tools making software safer, or creating an endless patching treadmill? Mattias, Andrey, and Paulina discuss Dependabot, human review, and why teams should assume their software is already vulnerable.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean mpgie-1b16454-pb "DEVSECOPS Talks #108 - Assume You’re Vulnerable: Security Beyond Patching"  >}}

---

<!-- Video -->

## Summary {#summary}

The AI boom has cracked security open from both sides at once, and the hosts — Mattias, Andrey, and Paulina — spend a (deliberately short, Sweden-is-30-degrees) episode on what practitioners should actually do about it. LLMs are driving a flood of dependency patches while getting frighteningly good at scanning your public webpages and code for the API keys you thought you'd hidden. Andrey's core move: stop chasing patches as if clean code means safe, and instead **assume your software is already vulnerable** and architect so a break-in finds nothing to work with. Mattias floats the episode's spiciest take — maybe ransomware is the only thing keeping everyone's security honest — before a Swedish government agency's summer-vacation tips (leave a dirty coffee cup out!) turn into a lesson in why broadcasting your defenses is a bad idea.

## Key Topics {#key-topics}

### The patching wave: does it ever stop? {#patching-wave}

Mattias opens with the pattern everyone's feeling: LLMs are surfacing vulnerabilities at scale, and the result is a relentless wave of security patches across nearly every tool. He points at the social-media grumbling — why does everyone ship security patches but some vendors seem to lag, are they even running the same tooling? — as a symptom of how fast the baseline has shifted. The open question the hosts keep returning to: is this a finite backlog being cleared, or a permanent new state where we produce ever more (and not more secure) code and just keep patching forever? It's the same tension explored in [episode #102](/episodes/102-the-90-day-patch-window-is-dead/) on the collapsing patch window and the [January security roundup](/episodes/091-january-security-roundup-cvss-10-in-n8n-self-hosted-ai-scares-and-nonstop-patching/).

Paulina adds a dimension the tooling conversation often misses: the number of *people* building and prototyping has exploded, many without a software background or any sense of what to ask an LLM to check from a security angle. More builders, more code, no matching increase in security literacy.

### Dependabot, automation, and trust {#dependabot}

Dependency scanning (Dependabot and friends) isn't new, but the hosts note usage is climbing as incidents force more frequent patching — and the more often you patch, the more you want it automated. The catch is trust. Paulina recounts an update where every test passed and the app ran fine, but the update itself was wrong, forcing a rollback until a follow-up patch fixed it. The lesson: automate the PRs and tests, but keep a human in the loop before auto-applying fixes.

There's a balance on *how fast* to move, too. Mattias notes some teams deliberately wait days or a week before jumping to the latest release — a supply-chain buffer, so if a malicious version ships, the community catches it first. Paulina brings the old Docker interview wisdom: never blindly run `latest`, pin your versions. And Mattias flags Dependabot's real blind spot — **it only sees the version number, not the context of how you run the app**. Worth being precise here: Dependabot's own behavior is driven by your manifests and a [`dependabot.yml`](https://docs.github.com/en/code-security/concepts/supply-chain-security/about-the-dependabot-yml-file) config, not by free-form context written into the repo. So the practical fix for the blind spot is grounding the decision yourself — tune the config, gate updates behind CI that reflects how you actually deploy, and keep a human reviewing before merge (an AI code-reviewer bot, separate from Dependabot, is where the "read the repo context" idea actually applies).

### Assume you're vulnerable, then architect around it {#assume-vulnerable}

This is Andrey's central argument. Chasing every patch quietly assumes your software is trustworthy — so you build as if it is. Flip the mental model: assume there *will* be a vulnerability (in a package, or introduced by your own developers), and design so a break-in is contained. Concretely:

- **Run scratch / minimal images.** Pick languages that support it (Go, memory-safe, self-contained binaries) so a compromised container is nearly empty — nothing to live off the land, no shell to drop into.
- **Segment your network.** Newer EU rules push this: the cybersecurity technical requirements in [Regulation 2024/2690](https://eur-lex.europa.eu/eli/reg_impl/2024/2690/oj/eng) — which apply to specified digital, ICT, online, and trust-service entities under NIS2 — call for network segmentation, so default-deny between zones and only open what's truly necessary.
- **Minimize what faces the internet.** Only expose something if you *really, really* have to — and when you do, isolate it on its own network with minimal connectivity to other zones.

Patching still matters, Andrey stresses — but security comes in layers, and the layers beyond patching are where attention pays off most.

### The other side of the coin: the network attack {#network-attack}

Mattias takes the external view: you run services on the internet, and LLMs now make it much easier for attackers to scan a webpage or codebase, find vulnerabilities, and dig out secrets that obfuscation used to hide. The defensive stack the hosts run through:

- **Put public web applications behind a WAF** — a WAF inspects HTTP(S) traffic for bad patterns, so it belongs in front of your internet-facing web apps ([AWS documentation](https://docs.aws.amazon.com/waf/latest/developerguide/how-aws-waf-works.html)); it isn't a blanket control for every exposed service (non-HTTP protocols need their own protections).
- **Intrusion detection and canary tokens** in your containers — when someone accesses or triggers a planted token, it raises an alert.
- **No-shell containers** — if an attacker can't drop into bash, they're badly hampered; tools exist to watch container calls for unusual patterns.
- **Log and monitor egress**, especially external DNS — egress and DNS monitoring catch many command-and-control and exfiltration paths (a compromised shell often calls back out), even if not every compromise phones home.

### No breach epidemic (yet), and where the real risk sits {#breach-reality}

Despite the hype around frontier models (the hosts mention [GPT-5.6](https://openai.com/index/gpt-5-6/) being called comparable to [Claude Fable 5](https://www.anthropic.com/news/claude-fable-5-mythos-5) — "not my experience really," Andrey notes), there's no wave of headline breaches. Nobody's being hacked left and right in the general news. Where Mattias *would* worry: big network appliances like Cisco-based firewalls — hard to swap out, and when an exploit drops it hits the whole internet, so lock down admin access to internal-only and monitor closely. Andrey's related point: the old "small team saves money on-prem" argument is weakening. With this much security to do, you're safer on a big cloud provider that patches the underlying infrastructure for you — a small startup on AWS gets the same underlying security as Netflix.

### Ransomware and the real attack vector {#ransomware}

The budget question resurfaces — CISOs perennially begging for more — against the backdrop of years of ongoing ransomware. Mattias offers the episode's spiciest take: maybe ransomware is the one force actually keeping everyone's security current, since the alternative (leak the data, shrug off a token EU fine) is worse. "You pay your security people or you pay the bad guys — you pay anyway." Andrey grounds it by emphasizing that ransomware historically wasn't so much about your software or perimeter as about **compromised credentials** — sold by outsiders, or by insiders cashing in their own access. Worth noting it's not the whole picture — Mandiant's 2025 investigations put vulnerability exploitation as the leading initial-access vector, ahead of web compromise, stolen credentials, and brute force ([Google Threat Intelligence](https://cloud.google.com/blog/topics/threat-intelligence/ransomware-ttps-shifting-threat-landscape)) — so credentials are one major door among several.

### Bonus: securing the (physical) house {#summer-security}

To close, Andrey relays a Swedish agency's public-radio guidance on securing your home during summer vacation: leave an unfinished coffee cup visible from the window, skip the deep pre-departure clean, leave a little mess so it looks lived-in. His wry point — broadcasting your defenses on public radio means the burglars are listening too. The hosts pivot to better ideas: swap houses with friends, or do pet-/dog-sitting stays so someone's living there — a built-in alarm plus a dog.

## Highlights {#highlights}

- **Andrey on flipping the mental model:** "Assume the software you're running is vulnerable." Chasing every patch secretly assumes your code is trustworthy — so you build like it is. Flip it: expect a break-in, and architect so the intruder finds an empty scratch container on a segmented network with nowhere to go. Security comes in layers, and patching is only the first one. Listen for the full layered playbook.

- **Mattias with the take of the episode:** "You pay your security people, or you pay the bad guys — you pay anyway." Only half-joking, he argues ransomware might be the only thing actually keeping everyone's security honest, since a leaked-data-plus-tiny-fine outcome is worse. Tune in for the full (slightly heretical) argument — and Andrey's reminder that compromised credentials are one of the biggest doors in, even if they're not the only one.

- **Mattias on Dependabot's blind spot:** "It only sees the version — it doesn't have the context where you're running your application." Dependabot runs off your manifests and `dependabot.yml`, so the fix is grounding updates in CI and human review that reflect how you actually deploy — not expecting the bot to read your intentions. A small process change with outsized payoff for anyone drowning in dependency PRs. Hear how the hosts tune it in the full episode.

- **Mattias on the appliances that keep him up at night:** Big Cisco-based firewalls are hard to swap out, and when an exploit drops it hits the whole internet at once. His advice: lock admin access down to internal-only and monitor those boxes closely. Listen for the full external-attack rundown.

- **Andrey on cloud vs. on-prem in 2026:** A small startup on AWS gets the same underlying infrastructure security as Netflix. The old "run on-prem to save money" argument gets weaker every time the security workload grows — a big provider has your back on the layers you shouldn't be patching yourself. Catch the nuance in the episode.

- **The summer-house paradox:** A Swedish agency told the public — on the radio — to leave a dirty coffee cup by the window and skip the pre-vacation clean so burglars think you're home. Andrey's deadpan question: how useful is a defense tip when the burglars are listening too? A perfect small lesson in not broadcasting your controls. Listen for the better idea (swap houses, or get a dog-sitter who doubles as an alarm).

## Resources {#resources}

- [About Dependabot security updates — GitHub Docs](https://docs.github.com/en/code-security/concepts/supply-chain-security/about-dependabot-security-updates) — Official reference on how Dependabot raises security-update PRs, including grouping, compatibility scores, and how to deactivate updates; directly relevant to the automation-with-a-human-in-the-loop discussion.

- [About the `dependabot.yml` file — GitHub Docs](https://docs.github.com/en/code-security/concepts/supply-chain-security/about-the-dependabot-yml-file) — The actual configuration surface behind Dependabot's behavior, for grounding updates the supported way rather than expecting the bot to read free-form repo context.

- [Canarytokens.org](https://canarytokens.org/) — Free tool for generating tripwire tokens that alert the moment they're accessed. The canary-token-in-your-container tactic Mattias describes for spotting an intruder.

- [How to Choose Between Scratch and Distroless Base Images](https://oneuptime.com/blog/post/2026-02-08-how-to-choose-between-scratch-and-distroless-base-images/view) — Practical comparison of minimal container images and why removing the shell and package manager shrinks attack surface — the backbone of Andrey's "empty container, nothing to live off" argument.

- [Minimal / distroless images — Docker Docs](https://docs.docker.com/dhi/core-concepts/distroless/) — Docker's own guidance on distroless images for apps that still need a language runtime, complementing the scratch-image approach for non-Go stacks.

- [Commission Implementing Regulation (EU) 2024/2690 — EUR-Lex](https://eur-lex.europa.eu/eli/reg_impl/2024/2690/oj/eng) — The EU implementing regulation setting cybersecurity technical requirements (including network segmentation) for specified digital, ICT, online, and trust-service entities under NIS2 — the accurate scope behind the segmentation layer the hosts stress.

- [Episode #102 — The 90-Day Patch Window Is Dead](/episodes/102-the-90-day-patch-window-is-dead/) — The deeper dive into LLM-driven vulnerability discovery and why shipping vulnerable code is getting more expensive, which sets up this episode's "does the patching wave ever stop?" question.

- [Episode #97 — Shift Left, Get Hacked: Supply Chain Attacks Hit Devs](/episodes/097-shift-left-get-hacked-supply-chain-attacks-hit-devs/) — Background on the supply-chain risk behind the hosts' advice to wait before jumping to the latest release.
