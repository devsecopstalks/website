---
title: "#102 - The 90-Day Patch Window Is Dead with Ian Amit and Matias Madou"
date: 2026-06-04T21:15:07+01:00
lastmod: 2026-06-04T21:15:07+01:00
episode: 102
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey", "Ian Amit", "Matias Madou"]
aliases:
  - "/episodes/102/"
---

What happens when AI can turn patches into exploits in hours? The hosts discuss with Ian Amit and Matias Madou why the 90-day disclosure window is breaking, what Mythos Preview changes, and why shipping vulnerable code is becoming more expensive.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean f665k-1adf2b8-pb "DEVSECOPS Talks #102 - The 90-Day Patch Window Is Dead with Ian Amit and Matias Madou"  >}}

---

<!-- Video -->

{{< youtube nLbqoYuRrfM >}}

## Summary {#summary}

Andrey opens with a blunt observation: the 90-day responsible-disclosure window is collapsing because patch reverse-engineering — once expensive manual labor — is now something an LLM does between coffees. The hosts are joined by Ian Amit, CEO and co-founder of Gomboc AI and a longtime security leader, and Matias Madou, CTO and co-founder of Secure Code Warrior, to unpack what that means for secure software delivery. Anthropic's restricted [Mythos Preview](https://www.anthropic.com/glasswing) model is already turning up 16- and 27-year-old vulnerabilities in OpenBSD and FFmpeg, and the [IOActive whitepaper "The Security Gap in AI-Generated Code"](https://www.ioactive.com/the-security-gap-in-ai-generated-code/) found that across 27 leading AI models and AI-powered coding tools and ~20,000 samples, average security was 59% and roughly a third of generated code was fully exploitable. The hosts and their guests argue that "shift left" as practiced never really worked — and that the real fix is closing the loop earlier, inside the LLM and the vibe-coding tools themselves, while reintroducing some determinism back into a stack that has drifted too far into the non-deterministic. Along the way: who's liable when your CFO ships a Lovable app, why everyone is a builder but not everyone is a software engineer, and why "design like a car" beats iterate-on-garbage.

## Key Topics {#key-topics}

### The 90-day patch window is collapsing {#patch-window}

Andrey kicks off with the timing problem. Coordinated disclosure has historically given vendors a 90-day window because reverse-engineering a patch into a working exploit was hard, slow, manual work. That assumption no longer holds. With frontier LLMs — and especially with restricted models like Anthropic's [Mythos Preview](https://www.helpnetsecurity.com/2026/04/08/anthropic-claude-mythos-preview-identify-vulnerabilities/), which remains gated to vetted Project Glasswing partners (with access now being expanded beyond the initial group following Anthropic's June 2, 2026 announcement of ~150 additional organizations) — the time from "patch released" to "exploit constructed" is measured in hours, not months. Microsoft's Patch Tuesday cadence, designed for that older threat model, looks increasingly fragile.

The implication is uncomfortable: the operational cost of *shipping vulnerable code in the first place* is going up, because the window in which a patch is "safe enough" between release and exploitation is shrinking toward zero. Producing secure code on the way out matters more now, not less. The hosts have touched related ground in [episode #97 on supply-chain attacks](/episodes/097-shift-left-get-hacked-supply-chain-attacks-hit-devs/) and the [January 2026 roundup](/episodes/091-january-security-roundup-cvss-10-in-n8n-self-hosted-ai-scares-and-nonstop-patching/).

### A finite backlog of old bugs, or a permanent new state? {#two-schools}

Andrey lays out two schools of thought. One: there is a finite (large but finite) backlog of latent vulnerabilities sitting in 20–30 years of accumulated software, including possibly some that nation-state actors put there on purpose. LLMs are going to find them all over the next few years. Painful, but a one-off correction. The other: nothing structurally changes, because humans keep writing software, AI is trained on humans, and new vulnerability classes keep arriving as fast as old ones get cleared.

Paulina layers on the second pressure: the rate at which code is being *produced* has gone exponential, even if testing and scanning have not kept up. So the throughput of new issues to triage is also rising. The hosts agree the answer is probably "both, simultaneously" — and that the bottleneck has stopped being detection and is now the humans expected to act on the findings.

### The IOActive numbers: AI-generated code is not safe by default {#ai-code-security}

Ian Amit brings the data. [IOActive's "The Security Gap in AI-Generated Code"](https://www.ioactive.com/the-security-gap-in-ai-generated-code/) (April 2026) evaluated 27 leading AI models and AI-powered coding tools across 730 prompts, 27 languages and 219 vulnerability categories — nearly 20,000 analyzed samples. Average security score: 59%. Roughly 31.6% of generated code was fully exploitable. Simple security-flavored prompts ("write secure code") were often ineffective or counterproductive. Wrapper tools and security-aware system prompts could move the needle 25 points — but the floor is low enough that this is closing a gap, not eliminating one.

Different models also produce *different* failure shapes — each frontier model has its own characteristic weak spots. That has implications for tooling: you don't pick "the safe LLM," you pick the right LLM with the right guardrails for the workload at hand.

### Design like a car, not like a garbage iteration {#design-first}

Matias Madou pushes back on the dominant framing that AI safety in code is mostly a finding-and-fixing problem. His analogy: nobody designs a car by shipping a bad model and then iterating to a good one. You think hard about the design — including the safety features — and *then* build. Software has spent decades treating iteration over a broken baseline as the cost of doing business; AI is now amplifying that pattern instead of fixing it.

The argument is not "stop iterating." It is "if your default workflow is generate-then-scan-then-patch, you've already lost the leverage you'd have from getting more of it right by design." That requires skilled humans designing the application — choosing the right model for the language, supplying the right rules, prompting for the right properties (including authentication, which an LLM will simply omit if you don't ask). The mythical 10x developer is real, Matias Madou argues — but only for the 20% who actually know how to use these tools well.

### Everyone is a builder, not everyone is a software engineer {#builders-vs-engineers}

Mattias raises the scenario: five people spin up a training app on Lovable, forget to harden it, and start collecting sensitive data — who's responsible? The answer that lands in the room is blunt: *you are*. The platform is not going to carry your liability. Andrey then adds his own angle on the broader trend — he hopes LLM subscriptions get expensive enough to cool the "everyone is a builder" wave, because right now organizations are slowly waking up to the cost and risk of unrestricted AI coding access.

Ian Amit reframes the future workforce around that split. Everyone is a builder, but not everyone is a software engineer. The 20% of skilled developers will get sharply more productive with LLMs — they know which model to use, what rules to attach, how to prompt for the missing pieces. The other 80% — including CFOs writing Python — are builders. They will produce vastly more software in total, and a lot of it will be insecure. The job category "professional software engineer" becomes more like "architect": someone who understands front-end, back-end, security, DevOps, and which combination of LLMs and deterministic tools to compose for the problem at hand.

For context, [Wiz disclosed a critical authentication-bypass flaw in Base44](https://www.wiz.io/blog/critical-vulnerability-base44) (the Wix-acquired vibe-coding platform) in July 2025 that exposed apps built on the platform — a concrete example of the "shared infrastructure, shared risk" problem the hosts describe.

### Shift left, but actually close the loop {#real-shift-left}

Ian Amit argues "shift left" as practiced never delivered. It mostly meant security throwing findings over the wall at developers. The modern read is different: shift left means *closing the loop earlier*, ideally inside the LLM doing the building. The vibe-coding tool should ask "should this serve more than just you? does it need authentication? here is an attack class you're exposing yourself to — want me to fix it?" The detect-and-remediate cycle moves all the way into the design and generation step, not the post-hoc scan.

Andrey takes the point further: while humans are still in the loop writing code by hand, we are stuck working around the limits of human output. The deeper fix is for the LLM to push back against bad ideas instead of just being a "human pleaser." Mattias counters that humans are not going anywhere — somebody still has to specify what to build. The synthesis: humans set intent, the LLM holds the line on quality and security, and the loop is short enough that nothing escapes into production unexamined.

### Bring back some determinism {#determinism}

The closing thread: the industry has swung too far into the non-deterministic. AI's generative, creative behavior is genuinely useful, but it has to be grounded by deterministic checks — known-good module libraries, policy as code, repeatable test harnesses. Not as a replacement for the non-deterministic part, but as the rails it runs on. The hosts frame this as the pendulum correcting after over-rotating toward freeform generation. It also connects directly to last episode's [IaC themes](/episodes/101-infrastructure-as-code-in-2026-still-essential-or-already-changing-/) and Paul Stack's work on agent-native, deterministic infrastructure tooling in [episode #92](/episodes/092-from-system-initiative-to-swamp-agent-native-infra-with-paul-stack/).

## Highlights {#highlights}

- **Andrey on the death of the 90-day window:** "Reverse engineering of patches used to be hard, labor-intense work. Now it is hours. The whole responsible-disclosure clock was built on an assumption that no longer holds." Patch Tuesday was a calendar designed for a slower attacker. With LLMs in the loop, that calendar is fiction. Tune in for what this changes about how teams should think about shipping vulnerable code.

- **Ian Amit on the IOActive numbers:** "Even the best effort with the newest frontier models still produced massive amounts of vulnerabilities." Across 27 leading AI models and coding tools and 20,000 samples, the average was 59% secure — and about a third of generated code was fully exploitable. Listen for how Ian argues you should think about model selection, prompting, and guardrails as a stack — not a switch.

- **Matias Madou on building software like a car, not a garbage iteration:** "Not a single good product on planet earth is created by shipping a crappy model and iterating at the end. Why would that be different for software?" A direct shot at the find-and-fix-later default of modern AI coding. Catch the episode for what designing-first actually looks like at the prompt and tooling level.

- **Andrey on "everyone is a builder":** "I hope LLM subscriptions go up enough that we stop that insanity." Builders are not engineers. The CFO writing Python on Lovable is the new normal — and the platform is not going to absorb your liability when the data leaks. Listen for the split the hosts predict between the 20% who become 10x and the 80% who become liabilities.

- **Ian Amit on what shift left actually means now:** "Shift left used to mean throwing vulnerabilities at the developer. That's not shift left. The real shift left is closing the loop earlier — inside the LLM, before the code even reaches your IDE." A precise reframing of a tired phrase. Tune in for what the modern detect-and-remediate cycle looks like when the LLM itself is the first reviewer.

- **Andrey on getting humans out of the loop (and the pushback):** "While humans are involved, we will keep having these problems. The LLM has to push back against shitty ideas instead of being a human pleaser." Mattias and the guests push back — somebody still has to set intent. The synthesis is worth the full listen.

## Resources {#resources}

- ["The Security Gap in AI-Generated Code" — IOActive (April 2026)](https://www.ioactive.com/the-security-gap-in-ai-generated-code/) — Whitepaper evaluating 27 leading AI models and AI-powered coding tools across 730 prompts, 219 vulnerability categories, and ~20,000 samples; average security was 59% and ~31.6% of generated code was fully exploitable. The headline data Ian Amit cites.

- [Gomboc AI company page](https://www.gomboc.ai/company) — Cloud and infrastructure security company co-founded by Ian Amit. Gomboc describes its work as deterministic AI remediation for infrastructure misconfigurations.

- [Matias Madou, Ph.D. — Secure Code Warrior](https://www.securecodewarrior.com/about-us/matias-madou) — Professional profile for Matias Madou, CTO, director, and co-founder of Secure Code Warrior, with background in application security research, Fortify, Sensei Security, and developer secure-coding education.

- [Project Glasswing / Claude Mythos Preview — Anthropic](https://www.anthropic.com/glasswing) — Anthropic's restricted security-focused model program, gated to vetted Glasswing partners. Anthropic announced on June 2, 2026 that access is being expanded to approximately 150 additional organizations beyond the initial group. The model Andrey refers to as transformative for vulnerability discovery.

- ["Anthropic's new AI model finds and exploits zero-days across every major OS and browser" — Help Net Security](https://www.helpnetsecurity.com/2026/04/08/anthropic-claude-mythos-preview-identify-vulnerabilities/) — Coverage of Mythos Preview's reported capability to autonomously identify and exploit zero-days, including a 27-year-old OpenBSD TCP SACK bug and a 16-year-old FFmpeg H.264 vulnerability.

- ["Our evaluation of Claude Mythos Preview's cyber capabilities" — UK AI Security Institute](https://www.aisi.gov.uk/blog/our-evaluation-of-claude-mythos-previews-cyber-capabilities) — AISI's independent assessment, including the 73% expert-level hacking success rate cited in news coverage. Useful for grounding the "how scary is this, really" question.

- ["Critical Vulnerability in AI Vibe Coding platform Base44" — Wiz](https://www.wiz.io/blog/critical-vulnerability-base44) — Wiz Research's July 2025 disclosure of an auth-bypass flaw in Base44 (the Wix-acquired vibe-coding platform) that exposed private enterprise apps. A concrete example of the "shared infrastructure, shared risk" problem the hosts discuss.

- [Episode #101 — Infrastructure as Code in 2026](/episodes/101-infrastructure-as-code-in-2026-still-essential-or-already-changing-/) — The previous episode's discussion of determinism, agent-native IaC, and Paul Stack's Swamp pairs directly with this episode's call to re-introduce determinism into the AI-assisted dev loop.
