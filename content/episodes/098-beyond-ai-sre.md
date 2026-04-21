---
title: "#98 - Beyond AI SRE"
date: 2026-04-21T12:46:53+01:00
lastmod: 2026-04-21T12:46:53+01:00
episode: 98
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
---

Andrey shares the thinking behind Boris and the idea of going beyond AI SRE. The conversation covers the DevOps talent shortage, the coming squeeze on AI costs, why repeatable operational tasks are a strong fit for agents, and why customer data should stay in the customer's own AWS account.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean 8qpfq-1aa42b3-pb "DEVSECOPS Talks #98 - Beyond AI SRE"  >}}

---

<!-- Video -->

{{< youtube VGmyXiptRhQ >}}

## Summary

Most tools in the emerging "AI SRE" category focus squarely on incident response — something breaks, the bot investigates. Andrey argues that is only scratching the surface: the real drain on DevOps teams is the unglamorous day-two work nobody wants to do — cost reports, health-event triage, maintenance tasks — and that is where an AI teammate should live. In this episode, Andrey and Paulina discuss why 2026 is shaping up to be the year of the "big squeeze" as AI subsidies dry up, why the DevOps talent shortage makes agentic AI a necessity rather than a luxury, and how Boris — Andrey's AI DevOps teammate — is architected to go beyond incident response while letting customers keep ownership of their own data.

## Key Topics

### The Big Squeeze: AI Economics Are Changing Fast

Andrey opens with a macro observation: while the "is AI taking over our jobs?" question persists, the economic ground beneath it is shifting. Hyperscalers are cutting workforce expecting AI-driven efficiency gains — Block eliminated over 4,000 positions in an AI-driven restructuring, as discussed in [episode #94](/episodes/094-small-tasks-big-wins-the-ai-dev-loop-at-system-initiative/) — yet actual demand for computer science professionals remains higher than ever. Everyone is a developer with a $20 subscription, but Andrey questions how long that lasts.

The core argument: AI infrastructure providers face astronomical capital expenditure. Oracle is reportedly going cash-flow negative to build out data centers. Someone has to pay for it, and the subscription model is not sustainable at current price points. Claude Code, Cursor, and similar tools have already started cutting their subscription allowances — after a few heavy sessions with a good model, the flat-rate plan "becomes a pumpkin" and users pay API rates.

Andrey calls 2026 "the year of the big squeeze." As subsidies dry up, leaders will think harder about where to deploy AI. A $5,000–$10,000 monthly AI bill that makes a team of six or seven people twice as productive is still a clear win — but the days of throwing tokens at everything with an unlimited plan are ending. Paulina adds that smaller organizations will feel this disproportionately, raising the entry barrier for companies without deep pockets. The hosts expect increasing focus on open-source models as organizations seek sustainable alternatives.

### The DevOps Talent Shortage Is the Real Driver

Why build an AI DevOps teammate at all? Andrey points to a straightforward market reality: good DevOps engineers are extremely hard to find. If that were not true, neither his consulting firm FivexL nor Paulina's Dubas Consulting would have customers. The talent shortage leads to developers waiting for answers, projects stalling for lack of resources, and the people who are hired spending half their time as a help desk for developers, security teams, and managers — leaving little capacity for value-add work.

Agentic coding tools help to some extent — developers can self-serve on small infrastructure tasks. But Andrey cautions that you still need expertise to tell when the LLM is giving you good answers versus nonsense, and you need grounding and sophistication to validate outputs. For genuinely new architectural work, humans remain essential: "LLMs are regurgitators — they will regurgitate what they've seen before. If you need to come up with something generally new, that's where you need humans."

Paulina reinforces this point by noting that architecture needs to account for scale from the start. Doing a little thinking upfront saves significant refactoring pain later — and that kind of forward-looking judgment is not something LLMs reliably provide.

### Day-Two Operations: The Unsexy Work That Hurts You

Beyond the help-desk drain, Andrey identifies a category of work that consistently falls through the cracks: predictable, repeatable tasks that nobody wants to do. Cost reports that get skipped because engineers are focused on higher-value work. Maintenance tasks that get deferred because people are too busy or simply forget. AWS health events that go unreviewed. New AWS service announcements that nobody maps to their actual infrastructure.

The consequences are real: a missed cost report means surprise spend; deferred maintenance surfaces as a production incident; an unread health advisory becomes an outage followed by days of post-mortem. These are exactly the tasks where LLMs shine — not because they require creativity, but because they require consistency. They are predictable, repeatable, and can be triggered on a schedule or in response to a signal.

### The AI SRE Category — And Why It Is Not Enough

Andrey notes that a new product category called "AI SRE" has emerged, with tools like Cleric, Resolve.ai, and incident.io's AI features focused primarily on incident response — connecting to monitoring data, logs, and cloud APIs to diagnose problems when something breaks. Boris can do the same.

But Andrey argues the category is misnamed. Actual SRE work is about building systems and optimizing software so incidents do not happen in the first place. Most "AI SRE" tools address only the reactive side. Boris aims to go beyond incident response into proactive operations: generating cost reports, analyzing AWS health events before monitoring raises an alert, mapping AWS announcements to the customer's actual infrastructure, and serving as the team's operational knowledge layer.

Paulina quips about the ever-expanding title situation in the industry — DevOps, platform engineering, SRE, cloud engineering, infrastructure engineering — and Andrey laughs that he usually just tells people "I do computers."

### Boris Lives in Slack — And That Changes Everything

A key architectural choice: Boris lives in Slack rather than requiring a separate interface. Andrey argues this matters because today's AI interactions are almost entirely one-to-one — you talk to your terminal, to Cursor, to ChatGPT — and then you have to relay the results to your team or copy them over. When a team is discussing an incident in a Slack thread, switching to another tool to get AI help breaks the flow and scatters context.

With Boris in the thread, you can ask it to summarize the discussion, build a post-mortem, or execute a standard operating procedure (SOP) with all the thread context already available. The team communication aspect is a differentiator: instead of an AI that talks to one person, Boris participates in the team conversation.

The workflow Andrey sees emerging: Boris has access to Slack, GitHub, and AWS. Teams describe work in Slack, Boris creates detailed GitHub issues with full context from all connected sources, and engineers feed those issues to their local coding agents (like Claude Code). The team is also building an MCP server so coding agents can query Boris directly for additional context — avoiding the need for every developer to individually configure access to Slack, AWS, and other services locally.

### Data Sovereignty: You Own Your Data

Andrey addresses a trust problem head-on. Many AI SRE tools promise to "preserve tribal knowledge," but the hosts ask: where does that knowledge go? It goes to a SaaS provider. Disconnect the tool, and the knowledge vanishes with it.

Boris takes a different approach. When a customer sets up Boris, they provide an AWS account. Boris creates S3 buckets, DynamoDB tables, and other serverless resources in the customer's own account. All structured data is stored at rest on the customer side. Boris only loads data into memory for inference — nothing from the data perspective is stored on Boris's side.

Andrey acknowledges this was a deliberately self-inflicted architectural hurdle. Building a system where all data lives on the customer side while the inference engine runs separately requires significant engineering gymnastics — no local database, careful memory management, a fundamentally different system design. But the team made this choice from day one because they have seen what happens when knowledge gets siloed in third-party tools: "We don't want to create a new silo of communication with AI on top of the existing silos between people."

He also notes the irony: while they believe data sovereignty matters, plenty of organizations are "yoloing" their sensitive data into ChatGPT without a second thought. History may prove them wrong — but that is their bet.

### Model Independence and Sustainable AI

Another deliberate architectural constraint: Boris is designed to not depend on any particular model. Today it primarily uses Anthropic's Claude, but the architecture allows swapping to self-hosted or open-source models. This ties back to the "big squeeze" thesis — as AI costs evolve and open-source models improve, customers should not be locked into a single provider's pricing and availability.

### Pricing by the Hour, Not by the Token

The hosts discuss how to make AI pricing understandable, especially for customers who are still getting used to automation itself — let alone AI. Boris bills at $25 per hour of agent work time. Andrey argues this is far easier to reason about than token-based pricing: you can see how many hours the agent spent, compare it to what a human would cost, and decide if the economics work. Twenty hours a month at $25 is $500 — an additional resource with no commitment that you can "fire anytime."

This model also gives the Boris team room to optimize tokenomics on the backend without passing complexity to the customer. Andrey notes that figuring out sustainable AI business models is something every company in the space is still working through.

## Highlights

- **Andrey on the big squeeze:** "2026 will be the year of the big squeeze. All of the companies that host LLMs have astronomical capex — Oracle is set to go cash negative. Someone's got to pay for it, and the subscription model is not sustainable." With AI coding tools already cutting allowances, the era of unlimited $20 plans is ending — and that will reshape how every organization thinks about AI ROI. Listen to the full episode to hear how Andrey connects this macro shift to the case for building an AI DevOps teammate.

- **Andrey on the AI SRE misnomer:** "Those AI SRE tools — their primary focus is incident response. The actual work of SRE is building systems so incidents don't happen. We came up with a new niche and misnamed it, as we usually do in this industry." Most tools labeled "AI SRE" only address the reactive half of the job. The proactive half — cost management, health-event triage, maintenance — is where the real value lies. Tune in to hear what going beyond AI SRE actually looks like in practice.

- **Paulina on the title treadmill:** After listing DevOps, platform engineering, SRE, cloud engineering, and infrastructure engineering, Paulina notes: "My mother keeps asking, what are you doing at work? You go to a bank asking for a loan and they're like, what do you do for work?" Andrey's answer: "I usually say computers. I do computers." Give the episode a listen for more laughs and sharp takes on where the industry is headed.

- **Andrey on LLMs and creativity:** "LLMs are regurgitators. They will regurgitate what they've seen before — repeating the same patterns. But if you need to come up with something generally new, that's where you need humans." AI is great for predictable, repeatable work. For architectural innovation, do not expect it to replace your senior engineers anytime soon. Listen to the episode for the full argument on where AI helps and where it falls short.

- **Andrey on data sovereignty:** "All those AI tools will tell you they preserve your tribal knowledge. But where does this knowledge go? They store it on their side. You disconnect the tool, the knowledge is gone." Boris stores all customer data in the customer's own AWS account — a deliberate architectural constraint that adds engineering complexity but prevents yet another knowledge silo. Hear the full breakdown of why they chose this path and what it cost them architecturally.

- **Andrey on pricing simplicity:** "We bill $25 per hour. You can see how much time the agent takes. You can compare it — 20 hours a month is $500, an additional resource you can fire anytime. That's easier than tokens." When your customers are still figuring out what AI even is, the last thing they need is tokenomics. Listen to the episode to hear how the hosts think about sustainable AI business models.

## Resources

- [B.O.R.I.S. — Your AI DevOps Teammate](https://www.getboris.ai/) — Andrey's AI-powered DevOps agent that lives in Slack, connects to AWS and GitHub, and goes beyond incident response into day-to-day operations and knowledge preservation.

- [Top AI SRE Tools in 2026: A Comprehensive Comparison (Metoro)](https://metoro.io/blog/top-ai-sre-tools) — A comparison of the emerging AI SRE category, covering tools like Resolve.ai, Cleric, incident.io, and PagerDuty's AI features — the landscape Boris is positioning beyond.

- [Cleric: AI SRE Teammate](https://cleric.ai/) — One of the AI SRE tools focused on autonomous incident investigation and root cause analysis, representative of the category Andrey describes as "squarely focused on incident response."

- [Oracle's Free Cash Flow Hits Negative $24.7 Billion Amid AI Spending (Fortune)](https://fortune.com/2026/03/10/oracle-best-quarter-negative-free-cash-flow-ai-spending/) — The numbers behind Andrey's "big squeeze" thesis: Oracle's capex rocketed to $50 billion for AI data center buildout while free cash flow went deeply negative.

- [Model Context Protocol (MCP) Servers](https://github.com/modelcontextprotocol/servers) — The open standard Boris is building on so coding agents like Claude Code can query Boris directly for infrastructure context without each developer configuring access individually.

- [AWS Health Aware (AHA)](https://github.com/aws-samples/aws-health-aware) — AWS's open-source framework for automated health event notifications — the kind of proactive operational task Boris aims to handle with AI-powered analysis rather than simple forwarding.

- [Anthropic Cuts Off Third-Party Tools, Citing Unsustainable Demand (The Decoder)](https://the-decoder.com/anthropic-cuts-off-third-party-tools-like-openclaw-for-claude-subscribers-citing-unsustainable-demand/) — Coverage of AI providers pulling back subsidies as real per-user compute costs dwarf subscription revenue, illustrating the "big squeeze" dynamic the hosts discuss.
