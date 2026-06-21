---
title: "#104 - When AI Coding Gets 10x More Expensive"
date: 2026-06-22T11:05:55+01:00
lastmod: 2026-06-22T11:05:55+01:00
episode: 104
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/104/"
---

Is flat-rate AI coding coming to an end? Mattias, Paulina, and Andrey discuss Copilot’s token billing, runaway API costs, and why an expensive model can sometimes be the cheaper choice.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean 98u8f-1af3e9d-pb "DEVSECOPS Talks #104 - When AI Coding Gets 10x More Expensive"  >}}

---

<!-- Video -->

## Summary {#summary}

The "free lunch" era of flat-rate AI coding is ending, and the hosts are blunt about what that means for your bill. Mattias, Paulina, and Andrey dig into GitHub Copilot's June 1 switch from premium-request to token-based billing — a change Paulina says can turn a $2–3 day into a $20 one without changing how you work — and place it inside what Andrey calls "the big squeeze": the industry-wide drift from subsidized subscriptions toward raw API rates, first led by Cursor, now reaching everyone. They get practical fast: why heavier models cost proportionally more under per-token billing, how to swap a coding agent's backend to Amazon Bedrock and defend against a runaway agent billing you $5,000, why the "1 million token context window" is mostly a lie past 200k, and whether local models on Apple Silicon are a real escape hatch or just a sold-out-in-Denmark Mac mini flex. Andrey's contrarian take: sometimes paying for the expensive model is the cheap option — fewer passes, fewer tokens, faster to the answer. Plus the tool Andrey personally uses to cut token use by 50–60%.

## Key Topics {#key-topics}

### The big squeeze: from subscriptions to API rates {#big-squeeze}

Andrey frames the whole episode around a trend he's described elsewhere as "the big squeeze": providers steadily moving users off subsidized flat-rate plans toward billing that tracks real token cost. Cursor went first and "bravest" last year, shifting non-default models to straight API rates. It keeps its own in-house Composer model, and its Auto mode draws on the plan's included usage — but the moment you pin a specific model, usage is billed from the API credit pool at that model's published per-token rate. Anthropic's Claude subscriptions use windowed limits — a five-hour window plus a weekly cap — that are now harder to hit on Opus than they were. GitHub Copilot, Andrey argues, is "late to it." His prediction: the trend continues, and the heavy subsidies — including AWS Kiro's monthly renewing credits and OpenAI's aggressive offers — eventually dry up.

### Copilot's token billing and bill shock {#copilot-billing}

Paulina walks through the change that triggered the episode: as of June 1, 2026, Copilot moved from premium-request pricing to token-based usage billing. The worry isn't abstract — it's "get less for more." Under the new plans, each model is billed at its own per-token rate, so heavier models cost proportionally more tokens-for-tokens than lighter ones for the same task. (The familiar request *multipliers* Paulina cites — the newest Opus at roughly 15x a standard request, an older model around 3x — are legacy figures from the old premium-request system; after June 1 they apply only to annual subscribers who remain on request-based billing, not to the new per-token plans.) Either way the direction is the same: a session that cost $2–3 before the change can land near $20 after, if you don't adjust behavior. The takeaway the hosts keep returning to: match the model to the task, and stop reaching for the most powerful option for trivial work. This extends themes from the cost-and-lock-in conversations in earlier episodes like [#90 on Kubernetes vs. managed services](/episodes/090-k8s-vs-managed-services-cost-lock-in-and-reality/).

### Harness vs. model: bring your own backend {#harness-vs-model}

Andrey draws a distinction listeners should internalize: a coding agent is a *harness* (something running locally — Claude Code, Codex, Kiro CLI, OpenCode) plus an *LLM backend* you plug into it. You can keep the harness and swap the backend — bring your own API key, or route through Amazon Bedrock (Anthropic models), Google Vertex, Azure, or OpenRouter. Doing so means giving up subscription subsidies and paying API rates, but it buys control. He's seen teams run coding agents in CI/CD this way — they're ordinary CLI programs that install into a GitHub Actions runner and do code review through a private Bedrock role.

### Capping runaway spend on Bedrock {#cost-caps}

The flip side of API access is the scare story: a misbehaving program hammering the Converse API can run up $5,000 before anyone notices — Andrey says he's seen it happen. The defensive move is real but less direct than "set an IAM limit." IAM has no native monetary threshold. AWS Budgets can apply a deny policy to a Bedrock role once spend crosses a line, but it's a backstop, not a tripwire: Budgets refreshes spend data at least once a day, so a budget action can lag behind a fast runaway — long enough for the bill to overshoot badly before it ever fires. For enforcement that actually stops the bleeding in real time, front Bedrock with a gateway or proxy that enforces per-key, per-model token quotas (a LiteLLM-style gateway, or Bedrock behind an API layer that meters and rejects requests past a quota). Use the gateway for the hard, immediate cutoff and AWS Budgets as the slow safety net underneath it.

### The context window is mostly a lie {#context-window}

The hosts puncture the "1 million token context window" marketing. Performance degrades well before that: assume you're best under 100k, still workable from 100k–200k, and clearly degrading beyond it — at which point you're either compacting or paying to resend everything each turn. Plenty loaded at session start eats that budget: system prompts, agent MD files, and tool definitions. How much MCP costs you depends on the harness and configuration — Claude Code, for instance, now defers full MCP tool schemas by default rather than loading every definition upfront. Paulina raises the emerging pattern of namespacing/toolboxing MCPs into a tree so the agent narrows from "something in Jira" to the specific tool, rather than exposing every tool at once. Andrey notes this mirrors what Boris does internally — distilling user intent across layers before any heavy action runs.

### Optimizing passes, reviews, and "boring" work {#optimization}

Several practical levers come up. Don't run AI code review on all 10 commits when the last one (or two or three) will do — and consider tiered review: a cheap model first pass to catch obvious issues, escalating only when needed. But Andrey counters his own advice: a cheap first pass can be suboptimal, forcing extra passes; sometimes the expensive model gets you there in *fewer* tokens overall, especially when you need a result fast. Mattias raises the cultural question — do you stop letting the agent do boring commits and pushes to save tokens? The answer depends entirely on whether you're on a fully-paid employer plan (offload everything, be happier) or paying from your own pocket.

### Local models: real escape hatch or hype? {#local-models}

Local inference is the most-discussed possible exit. Apple Silicon's unified memory is well-suited to running models, and MoE architectures (Andrey references Llama 4's approach of activating only parts of the model) make decent local intelligence plausible. The metric that matters is tokens per second — loading a model into memory is useless at half a token/sec. The hosts like a hybrid future: offload heavy planning to a cloud model, run tool-calling and file edits locally. Andrey points out that harnesses already split work this way — Claude Code uses a small, fast model for some background functions. (On Bedrock, when a Haiku model isn't available, Claude Code falls back to the primary model for those background tasks rather than always offloading to Haiku; you can point it explicitly at Haiku 4.5 via the `ANTHROPIC_DEFAULT_HAIKU_MODEL` environment variable.) The reality check: a Mac mini (sold out across Denmark, per Mattias) is fine for a local assistant but won't do real coding work — you need a beefy, RAM-heavy MacBook Pro, and rising RAM prices keep local inference under question.

## Highlights {#highlights}

- **Andrey on "the big squeeze":** "Cursor was the first, the bravest — they went from requests to plain API tokens last year. Copilot is one of those coming late to it." His prediction: every coding tool drifts toward API-rate billing as the subsidies dry up. If you budgeted for flat-rate AI, this episode is your early warning — press play to hear where he thinks the squeeze lands next.

- **Paulina on Copilot bill shock:** "I compared it — if I work the same way on the new pricing, I pay around $20. Before the change, that was two or three dollars." Same work, ~10x the cost. Her fix isn't panic-capping usage — it's matching the model to the task instead of reaching for Opus on everything. Tune in for how she thinks about it.

- **Andrey on the $5,000 runaway agent:** "Imagine a program that just keeps hammering the API, burning tokens — suddenly you owe $5,000 because it misbehaved. I've seen that happen." The defense isn't a magic IAM switch, and it isn't AWS Budgets alone — Budgets only refreshes about once a day, so it can lag. The real-time guard is a gateway that enforces token quotas and rejects requests the moment you cross the line. Listen for how to wire your own backend without the bill surprise.

- **Andrey on the million-token myth:** "One million token window — that's really a lie. Performance degrades hard as soon as you go past 200k." Assume you're at your best under 100k. Everything loaded at startup eats into it. Give the episode a listen for the full crash course in context economics.

- **Andrey on when expensive is cheaper:** "Running a first pass with a stupid model gives suboptimal results — you need extra passes. Sometimes it makes sense to pay for the higher model and spend fewer tokens to get where you want." A direct shot at the assumption that the cheap model is always the frugal choice. Listen in for when he says it's worth paying up.

- **Mattias on the Mac mini that won't save you:** "Mac mini is sold out in all of Denmark." Andrey's reply: great for a local assistant, useless for real coding work — you need a beefy MacBook Pro and a lot of RAM, and RAM prices are climbing. The local-inference dream, reality-checked — tune in for the full local-vs-cloud breakdown.

- **Andrey on the tool he actually uses:** "There's RTK — Rust Token Killer. The free version is good enough, and they claim to save you 60% on token use. In my experience it's about 50–60%, which is decent." A concrete, free lever for anyone feeling the squeeze. Hit play to hear where it fits.

## Resources {#resources}

- [GitHub Copilot is moving to usage-based billing — The GitHub Blog](https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/) — The official announcement of the June 1, 2026 shift from premium requests to token-based AI Credits, including which plans are affected and what stays free (autocomplete, Next Edit suggestions).

- [Models & Pricing — Cursor Docs](https://cursor.com/docs/models-and-pricing) — How Cursor's usage-based billing works: Auto mode draws on the plan's included usage, while pinning a specific model bills from the API credit pool at that model's published per-token rate — the trend-setter Andrey references.

- [Claude Code Usage Limits explained (2026) — Morph](https://www.morphllm.com/claude-code-usage-limits) — A clear breakdown of Claude's five-hour and weekly windows, and why Opus burns the limit faster than Sonnet or Haiku — the subscription model Andrey contrasts against API-rate billing.

- [RTK — Rust Token Killer (GitHub)](https://github.com/rtk-ai/rtk) — The free, single-binary CLI proxy Andrey endorses; it compresses command output before it hits the context window, with claimed 60–90% token savings on common dev commands. See also the [project site](https://www.rtk-ai.app/).

- [Managing your costs with AWS Budgets — AWS](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) — The backstop layer for a runaway Bedrock agent: a budget threshold plus a budget action that applies a deny policy to the role. Note the limitation — Budgets refreshes spend data at least once a day, so it can lag and is not a real-time cutoff; pair it with a gateway enforcing token quotas for immediate enforcement.

- [LiteLLM — budgets & rate limits](https://docs.litellm.ai/docs/proxy/users) — Example of the gateway pattern the hosts implicitly call for: a proxy in front of Bedrock (or any provider) that meters usage and enforces per-key, per-model token quotas in real time, rejecting requests the instant a limit is hit.

- [Explore large language models on Apple silicon with MLX — Apple (WWDC25)](https://developer.apple.com/videos/play/wwdc2025/298/) — Apple's own technical walkthrough of running LLMs on Apple Silicon with MLX, covering unified memory, quantization, and the tokens-per-second and RAM trade-offs the hosts flag as the real bottleneck for local coding.

- [Episode #103 — European Cloud Sovereignty](/episodes/103-european-cloud-sovereignty-with-mark-shine-pawel-piwosz-and-filipe-berti/) — The previous episode on EU cloud providers and pay-per-token European models, which the hosts reference at the top of this one.
