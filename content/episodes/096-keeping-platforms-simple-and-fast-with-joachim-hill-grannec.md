---
title: "#96 - Keeping Platforms Simple and Fast with Joachim Hill-Grannec"
date: 2026-04-01T21:54:54+01:00
lastmod: 2026-04-01T21:54:54+01:00
episode: 96
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias"]
---

This episode with Joachim Hill-Grannec asks: How do platforms bloat, and how do you keep them simple and fast with trunk-based dev and small batches? Which metrics prove it works—cycle time, uptime, or developer experience? Can security act as a partner that speeds delivery instead of a gate?

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean g4amm-1a8a8ee-pb "DEVSECOPS Talks #96 - Keeping Platforms Simple and Fast with Joachim Hill-Grannec"  >}} 

---

<!-- Video -->

{{< youtube 6o8q6g9cbOY >}}

## Summary
In this episode of DevSecOps Talks, Mattias speaks with Joachim Hill-Grannec, co-founder of Peltek, a boutique consulting firm specializing in high-availability, cloud-native infrastructure. Following up on a previous episode where Steve discussed cleaning up bloated platforms, Mattias and Joachim dig into *why* platforms get bloated in the first place and how platform teams should think when building from scratch. Their conversation spans cloud provider preferences, the primacy of cycle time, the danger of adding process in response to failure, and a strong argument for treating security and quality as enablers rather than gatekeepers.

## Key Topics

### Platform Teams Should Serve Delivery Teams
Joachim frames the core question of platform engineering around who the platform is actually for. His answer is clear: the delivery teams are the client. Platform engineers should focus on making it easier for developers to ship products, not on making their own work more convenient.

He connects this directly to platform bloat. In his experience, many platforms grow uncontrollably because platform engineers keep adding tools that help the platform team itself: "Look, I spent this week to make my job this much faster." But Joachim pushes back on this instinct — the platform team is an amplifier for the organization, and every addition should be evaluated by whether it helps a product get to production faster and gives developers better visibility into what they are working on.

### Choosing a Cloud Provider: Preferences vs. Reality
The conversation briefly explores cloud provider choices. Joachim says GCP is his personal favorite from a developer perspective because of cleaner APIs and faster response times, though he acknowledges Google's tendency to discontinue services unexpectedly. He describes AWS as the market workhorse — mature, solid, and widely adopted, comparing it to "the Java of the land." Azure gets the coldest reception; both acknowledge it has improved over time, but Joachim says he still struggles whenever he is forced to use it.

They observe that cloud choices are frequently made outside engineering. Finance teams, investors, and existing enterprise agreements often drive the decision more than technical fit. Joachim notes a common pairing: organizations using Google Workspace for productivity but AWS for cloud infrastructure, partly because the Entra ID (formerly Azure AD) integration with AWS Identity Center works more smoothly via SCIM than the equivalent Google Workspace setup, which requires a Lambda function to sync groups.

### Measuring Platform Success: Cycle Time Above All
When Mattias asks how a team can tell whether a platform is actually successful, Joachim separates subjective and objective measures.

On the subjective side, he points to developer happiness and developer experience (DX). Feedback from delivery teams matters, even if surveys are imperfect.

On the objective side, his favorite metric is cycle time — specifically, the time from when code is ready to when it reaches production. He also mentions uptime and availability, but keeps returning to cycle time as the clearest indicator that a platform is helping teams deliver faster. This aligns with DORA research, which has consistently shown that deployment frequency and lead time for changes are strong predictors of overall software delivery performance.

### Start With a Highway to Production
A major theme of the episode is that platforms should begin with the shortest possible route to production. Mattias calls this a "highway to production," and Joachim strongly agrees.

For greenfield projects, Joachim favors extremely fast delivery at first — commit goes to production, commit goes to production — even with minimal process. As usage and risk increase, teams can gradually add automation, testing, and safeguards. The critical thing is to keep the flow and then ask "how do we make those steps faster?" as you add them, rather than letting each new step slow down the pipeline unchallenged.

He also makes a strong case for tags and promotions over branch-based deployment, noting his instinctive reaction when someone asks "which branch are we deploying from?" is: "No branches — tags and promotions."

### The Trap of Slowing Down After Failure
Joachim warns about a common and dangerous pattern: when a bug reaches production, the natural organizational reaction is not to fix the pipeline, but to add gates. A QA team does a full pass, a security audit is inserted, a manual review step appears. Each gate slows delivery, which leads to larger batches, which increases risk, which triggers even more controls.

He sees this as a vicious cycle. Organizations that respond to incidents by slowing delivery actually get worse security, worse quality, and worse throughput over time. He references a study — likely the research behind the book *Accelerate* by Nicole Forsgren, Jez Humble, and Gene Kim — showing that faster delivery correlates with better security and quality outcomes. The organizations adding Engineering Review Boards (ERBs) and Architecture Review Boards (ARBs) in the name of safety often do not measure the actual impact, so they never see that the controls are making things worse.

Mattias connects this to AI-assisted development, where developers can now produce changes faster than ever. If the pipeline cannot keep up, the pile of unreleased changes grows, making each release riskier.

### Getting Buy-In: Start With Small Experiments
Joachim does not recommend that a slow, process-heavy organization throw everything out overnight. Instead, he suggests starting with small experiments. Code promotions are a good entry point: teams can start producing artifacts more rapidly without changing how those artifacts are deployed. Once that works, the conversation shifts to delivering those artifacts faster.

He finds starting on the artifact pipeline side produces quicker wins and more organizational buy-in than starting with the platform deployment side, which tends to be more intertwined and higher-risk to change.

### Guiding Principles Over a Rigid Golden Path
Mattias questions the idea of a single "golden path," saying the term implies one rigid way of working. Joachim leans toward guiding principles instead.

His strongest principle is simplicity — specifically, simplicity to *understand*, not necessarily simplicity to *create*. He references Rich Hickey's influential talk *Simple Made Easy* (from Strange Loop 2011), which distinguishes between things that are simple (not intertwined) and things that are easy (familiar or close at hand). Creating simple systems is hard work, but the payoff is systems that are easy to reason about, easy to change, and easy to secure.

His second guiding principle is replaceability. When evaluating any tool in the platform, he asks: "How hard would it be to yank this out and replace it?" If swapping a component would be extremely difficult, that is a smell — it means the system has become too intertwined. Even with a tool as established as Argo CD, his team thinks about what it would look like to switch it out.

### Tooling Choices and Platform Foundations
Joachim outlines the patterns his team typically uses when building platforms, organized into two paths:

**Delivery pipeline (artifact creation):**
- Trunk-based development over GitFlow
- Release tags and promotions rather than branch-based deployment
- Containerization early in the pipeline
- Release Please for automated release management and changelogs
- Renovate for dependency updates (used for production environment promotions from Helm charts and container images)

**Platform side (environment management):**
- Kubernetes-heavy, typically EKS on AWS
- Karpenter for node scaling
- AWS Load Balancer Controller only as a backing service for a separate ingress controller (not using ALB Ingress directly, due to its rough edges)
- Argo CD for GitOps synchronization and deployment
- Argo Image Updater for lower environments to pull latest images automatically
- Helm for packaging, despite its learning curve

He notes that NGINX Ingress Controller has been deprecated, so teams need to evaluate alternatives for their ingress layer.

### Developers Should Not Be Fully Shielded From Operations
One of the more nuanced parts of the conversation is how much operational responsibility developers should have. Joachim rejects both extremes. He does not think every developer needs to know everything about infrastructure, but he has seen too many cases where developers completely isolated from runtime concerns make poor decisions — missing simple code changes that would make a system dramatically easier to deploy and operate.

He advocates for transparency and collaboration. Platform repos should be open for anyone on the dev team to submit pull requests. When the platform team makes a change, they should pull in developers to work alongside them. This way, the delivery team gradually builds a deeper understanding of how the whole system works.

Joachim loves the open-source maintainer model applied inside organizations: platform teams are maintainers of their areas, but anyone in the organization should be able to introduce change. He warns against building custom CLIs or heavy abstractions that create dependencies — if a developer wants to do something the CLI does not support, the platform team becomes a bottleneck.

Mattias adds that opening up the platform to contributions also exposes assumptions. What feels easy to the person who built it may not be easy at all; it is just familiar. Outside contributors reveal where the system is actually hard to understand.

### Designers, Not Artists: Detaching Ego From Code
Joachim shares an analogy he prefers over the common "developers as artists" framing. He sees developers more like designers than artists, because an artist's work is tied to their identity — they want it to endure. A designer, by contrast, creates something to serve a purpose and expects it to be replaced when something better comes along.

He applies this to platforms and infrastructure: "I want my thing to get wiped out. If I build something, I want it to get removed eventually and have something better replace it." Organizations where ego is tied to specific systems or tools tend to resist change, which leads to the kind of dysfunction that keeps platforms bloated and brittle.

### Complexity Is the Enemy of Security
Mattias raises the difficulty of maintaining complex security setups over time, especially when the original experts leave. Joachim responds firmly: complexity is anti-security.

If people cannot comprehend a system, they cannot secure it well. He acknowledges that some problems are genuinely hard, but argues that much of the complexity engineers create is unnecessary — driven by ego rather than need. "The really smart people are the ones that create simple things," he says, wishing the industry would redirect its narrative from admiring complicated systems to admiring simple ones.

### Security and QA as Internal Consulting, Not Gatekeeping
Joachim draws a parallel between security and QA. He dislikes calling a team "the quality team," preferring "verification" — they are one component of quality, not the entirety of it. Similarly, security is not one team's responsibility; it spans product design, development practices, tooling, and operations.

His ideal model is for security and QA teams to operate as internal consultants whose goal is to reduce risk and improve the overall system — not to catch every possible issue at any cost. The framing matters: if a security team's mandate is simply "block all security issues," the logical conclusion is to stop shipping or delete the product entirely. That may be technically secure, but it is useless.

He frames security as risk management: "Security is a risk management process, not just security for the sake of security. You're managing the risk to the business." The goal should be to deliver faster *and* more securely — an "and," not an "or."

Mattias recalls a PCI DSS consultant joking over drinks that a system being down is perfectly compliant — no one can steal card numbers if the system is unavailable. The joke lands because it exposes exactly the broken incentive Joachim describes.

### Business Value as the Unifying Frame
The episode closes by tying everything back to business outcomes. Joachim argues that speed and security are not opposites; both contribute to business value. Fast delivery creates value directly, while security reduces business risk — and risk management is itself a business operation.

He explains why focusing on the highest-impact business bottleneck first builds trust. When you hit the big items first, you earn credibility, and subsequent changes become easier to justify. For example, one of his clients has a security group that is the slowest part of their organization. Speeding up that security process would have a massive impact on business delivery — more than optimizing the artifact pipeline.

Mattias reflects that he used to see platform work as separate from business concerns — "I don't care about the business, I'm here to build a platform for developers." Looking back, he would reframe that: using business impact as the measure of platform success does not mean abandoning the focus on developers, it means having a clearer way to prioritize and demonstrate value.

## Highlights
- **Joachim on platform bloat:** "Your job is not to make your job faster and easier — you're an amplifier to the organization."
- **Joachim on his favorite metric:** "Cycle time is my favorite metric. I love cycle time metrics."
- **Joachim on deployment strategy:** "No branches, no branches — tags and promotions."
- **Mattias on platform design:** He calls the ideal early setup a "highway to production."
- **Joachim on simplicity vs. ease:** He references Rich Hickey's *Simple Made Easy* talk — "It's very hard to create simple systems that are easy to reason about. And it's very easy to create systems that are very hard to reason about."
- **Joachim on replaceability:** "If swapping a tool out would be extremely hard, that's a pretty big smell."
- **Joachim on complexity and security:** "If it's complicated, you just can't keep all the context together. Simple systems are much easier to be secure."
- **Joachim on engineering ego:** "I don't particularly like the aspect of [developers as] artists... I want my thing to get wiped out. I want it to get removed eventually and have something better replace it." He prefers the analogy of designers over artists, because artists tie their identity to their creations.
- **Joachim on security as a blocker:** "If their goal is we are going to block every security issue, the best way to do that is delete your product."
- **Spicy cloud takes:** Joachim calls GCP his favorite cloud for developers, compares AWS to "the Java of the land," and says he still struggles every time he is forced to use Azure.
- **PCI DSS dark humor:** Mattias recalls a consultant joking that a downed system is perfectly compliant — you cannot steal card numbers from a system that is not running.
- **Joachim on the slow-down trap:** Organizations add ERBs, ARBs, and manual security gates after incidents, but "the faster you can deliver, you actually get better security, better quality, and better throughput — and the more you slow it down, you go the opposite."

## Resources
- [Simple Made Easy by Rich Hickey (InfoQ)](https://www.infoq.com/presentations/Simple-Made-Easy/) — The influential 2011 talk Joachim references on distinguishing simplicity from ease in system design.
- [DORA Metrics: The Four Keys](https://dora.dev/guides/dora-metrics-four-keys/) — The research framework behind cycle time, deployment frequency, and the finding that speed and stability are not tradeoffs.
- [Trunk Based Development](https://trunkbaseddevelopment.com/) — A comprehensive guide to the branching strategy Joachim recommends over GitFlow.
- [Argo CD — Declarative GitOps for Kubernetes](https://argo-cd.readthedocs.io/en/stable/) — The GitOps tool Joachim's team uses for cluster synchronization and deployment.
- [Release Please (GitHub)](https://github.com/googleapis/release-please) — Google's tool for automated release management based on conventional commits, used by Joachim's team for tag-based promotions.
- [Karpenter — Kubernetes Node Autoscaler](https://karpenter.sh/) — The node autoscaler Joachim's team uses with EKS for fast, flexible scaling.
- [Renovate — Automated Dependency Updates](https://docs.renovatebot.com/) — The dependency management bot Joachim uses for both build dependencies and production environment promotions.
