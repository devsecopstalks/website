---
title: "#95 - From Platform Theater to Golden Guardrails with Steve Wade"
date: 2026-03-23T23:08:52+00:00
lastmod: 2026-03-23T23:08:52+00:00
episode: 95
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias"]
---

Is your Kubernetes stack bloated, slow, and hard to explain? Steve Wade shares simple checks—the hiring treadmill, onboarding time, and the acronym test—to spot platform theater fast. What would a 30-day deletion sprint cut, save, and secure?

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean d4uwv-1a7d5a7-pb "DEVSECOPS Talks #95 - From Platform Theater to Golden Guardrails with Steve Wade"  >}} 

---

<!-- Video -->

{{< youtube 4stB_XSc9ok >}}

## Summary
In this episode of DevSecOps Talks, Mattias and Paulina speak with Steve Wade, founder of Platform Fix, about why so many Kubernetes and platform initiatives become overcomplicated, expensive, and painful for developers. Steve has helped simplify over 50 cloud-native platforms and estimates he has removed around $100 million in complexity waste. The conversation covers how to spot a bloated platform, why "free" tools are never really free, how to systematically delete what you don't need, and why the best platform engineering is often about subtraction rather than addition.

## Key Topics

### Steve's Background: From Complexity Creator to Strategic Deleter
Steve introduces himself as the founder of Platform Fix — the person companies call when their Kubernetes migration is 18 months in, millions over budget, and their best engineers are leaving. He has done this over 50 times, and he is candid about why it matters so much to him: he used to be this problem.

Years ago, Steve led a migration that was supposed to take six months. Eighteen months later, the team had 70 microservices, three service meshes (they kept starting new ones without finishing the old), and monitoring tools that needed their own monitoring. Two senior engineers quit. The VP of Engineering gave Steve 90 days or the team would be replaced.

Those 90 days changed everything. The team deleted roughly 50 of the 70 services, ripped out all the service meshes, and cut deployment time from three weeks of chaos to three days, consistently. Six months later, one of the engineers who had left came back. That experience became the foundation for Platform Fix.

As Steve puts it: "While everyone's collecting cloud native tools like Pokemon cards, I'm trying to help teams figure out which ones to throw away and which ones to keep."

### Why Platform Complexity Happens
Steve explains that organizations fall into a complexity trap by continuously adding tools without questioning whether they are actually needed. He describes walking into companies where the platform team spends 65–70% of their time explaining their own platform to the people using it. His verdict: "That's not a team, that's a help desk with infrastructure access."

People inside the complexity normalize it. They cannot see the problem because they have been living in it for months or years. Steve identifies several drivers: conference-fueled recency bias (someone sees a shiny tool at KubeCon and adopts it without evaluating the need), resume-driven architecture (engineers choosing tools to pad their CVs), and a culture where everyone is trained to add but nobody asks "what if we remove something instead?"

He illustrates the resume-driven pattern with a story from a 200-person fintech. A senior hire — "Mark" — proposed a full stack: Kubernetes, Istio, Argo, Crossplane, Backstage, Vault, Prometheus, Loki, Tempo, and more. The CTO approved it because "Spotify uses it, so it must be best practice." Eighteen months and $2.3 million later, six engineers were needed just to keep it running, developers waited weeks to deploy, and Mark left — with "led Kubernetes migration" on his CV. When Steve asked what Istio was actually solving, nobody could answer. It was costing around $250,000 to run, for a problem that could have been fixed with network policies.

He also highlights a telling sign: he asked three people in the same company how many Kubernetes clusters they needed and got three completely different answers. "That's not a technical disagreement. That's a sign that nobody's aligned on what the platform is actually for."

### The AI Layer: Tool Fatigue Gets Worse
Paulina observes that the same tool-sprawl pattern is now being repeated with AI tooling — an additional layer of fatigue on top of what already exists in the cloud-native space. Steve agrees and adds three dimensions to the AI complexity problem: choosing which LLM to use, learning how to write effective prompts, and figuring out who is accountable when AI-written code does not work as expected. Mattias notes that AI also enables anyone to build custom tools for their specific needs, which further expands the toolbox and potential for sprawl.

### How Leaders Can Spot a Bloated Platform
One of the most practical segments is Steve's framework for helping leaders who are not hands-on with engineering identify platform bloat. He gives them three things to watch for:

- **The hiring treadmill:** headcount keeps growing but shipping speed stays flat, because all new capacity is absorbed by maintenance.
- **The onboarding test:** ask the newest developer how long it took from their first day to their first production deployment. If it is more than a week, "it's a swamp." Steve's benchmark: can a developer who has been there two weeks deploy without asking anyone? If yes, you have a platform. If no, "you have platform theater."
- **The acronym test:** ask the platform team to explain any tool of their choosing without using a single acronym. If they cannot, it is likely resume-driven architecture rather than genuine problem-solving.

### The Sagrada Familia Problem
Steve uses a memorable analogy: many platforms are like the Sagrada Familia in Barcelona — they look incredibly impressive and intricate, but they are never actually finished. The question leaders should ask is: what does an MVP platform look like, what tools does it need, and how do we start delivering business value to the developers who use it? Because, as Steve says, "if we're not building any business value, we're just messing around."

### Who the Platform Is Really For
Mattias asks the fundamental question: who is the platform actually for? Steve's answer is direct — the platform's customers are the developers deploying workloads to it. A platform without applications running on it is useless.

He distinguishes three stages:
- **Vanilla Kubernetes:** the out-of-the-box cluster
- **Platform Kubernetes:** the foundational workloads the platform needs to function (secret management, observability, perhaps a service mesh)
- **The actual platform:** only real once applications are being deployed and business value is delivered

The hosts discuss how some teams build platforms for themselves rather than for application developers or the business, which is a fast track to unnecessary complexity.

### Kubernetes: Standard Tool or Premature Choice?
The episode explores when Kubernetes is the right answer and when it is overkill. Steve emphasizes that he loves Kubernetes — he has contributed to the Flux project and other CNCF projects — but only when it is earned. He gives an example of a startup with three microservices, ten users, and five engineers that chose Kubernetes because "Google uses it" and the CTO went to KubeCon. Six months later, they had infrastructure that could handle ten million users while serving about 97.

"Google needs Kubernetes, but your Series B startup needs to ship features."

Steve also shares a recent on-site engagement where he ran the unit economics on day two: the proposed architecture needed four times the CPU and double the RAM for identical features. One spreadsheet saved the company from a migration that would have destroyed the business model. "That's the question nobody asks before a Kubernetes migration — does the maths actually work?"

Mattias pushes back slightly, noting that a small Kubernetes cluster can still provide real benefits if the team already has the knowledge and tooling. Paulina adds an important caveat: even if a consultant can deploy and maintain Kubernetes, the question is whether the customer's own team can realistically support it afterward. The entry skill set for Kubernetes is significantly higher than, say, managed Docker or ECS.

### Managed Services and "Boring Is Beautiful"
Steve's recommendation for many teams is straightforward: managed platforms, managed databases, CI/CD that just works, deploy on push, and go home at 5 p.m. "Boring is beautiful, especially when you call me at 3 a.m."

He illustrates this with a company that spent 18 months and roughly $850,000 in engineering time building a custom deployment system using well-known CNCF tools. The result was about 80–90% as good as GitHub Actions. The migration to GitHub Actions cost around $30,000, and the ongoing maintenance cost was zero.

Paulina adds that managed services are not completely zero maintenance either, but the operational burden is orders of magnitude less than self-managed infrastructure, and the cloud provider takes on a share of the responsibility.

### The New Tool Tax: Why "Free" Tools Are Never Free
A central theme is that open-source tools carry hidden costs far exceeding their license fee. Steve introduces the **new tool tax** framework with four components, using Vault (at a $40,000 license) as an example:

- **Learning tax (~$45,000):** three engineers, two weeks each for training, documentation, and mistakes
- **Integration tax (~$20,000):** CI/CD pipelines, Kubernetes operators, secret migration, monitoring of Vault itself
- **Operational tax (~$50,000/year):** on-call, upgrades, tickets, patching
- **Opportunity tax (~$80,000):** while engineers work on Vault, they are not building things that could save hundreds of hours per month

Total year-one cost: roughly $243,000 — a 6x multiplier over the $40,000 budget. And as Steve points out, most teams never present this full picture to leadership.

Mattias extends the point to tool documentation complexity, noting that anyone who has worked with Envoy's configuration knows how complicated it can be. Steve adds that Envoy is written in C — "How many C developers do you have in your organization? Probably zero." — yet teams adopt it because it offers 15 to 20 features that may or may not be useful.

This is the same total cost of ownership concept the industry has used for on-premises hardware, but applied to the seemingly "free" cloud-native landscape. The tools are free to install, but they are not free to manage and maintain.

### Why Service Meshes Are Often the First to Go
When Mattias asks which tool type Steve most often deletes, the answer is service meshes. Steve does not name a specific product but says six or seven times out of ten, service meshes exist because someone thought they were cool, not because the team genuinely needed mutual TLS, rate limiting, or canary deploys at the mesh level.

Mattias agrees: in his experience, he has never seen an environment that truly required a service mesh. The demos at KubeCon are always compelling, but the implementation reality is different. Steve adds a self-deprecating note — this was him in the past, running three service meshes simultaneously because none of them worked perfectly and he kept starting new ones in test mode.

### A Framework for Deleting Tools
Steve outlines three frameworks he uses to systematically simplify platforms.

**The Simplicity Test** is a diagnostic that scores platform complexity across ten dimensions on a scale of 0 to 50: tool sprawl, deployment complexity, cognitive load, operational burden, documentation debt, knowledge silos, incident frequency, time to production, self-service capability, and team satisfaction. A score of 0–15 is sustainable, 16–25 is manageable, 26–35 is a warning, and 36–50 is crisis. Over 400 engineers have taken it; the average score is around 34. Companies that call Steve typically score 38 to 45.

**The Four Buckets** categorize every tool: Essential (keep it), Redundant (duplicates something else — delete immediately), Over-engineered (solves a real problem but is too complicated — simplify it), or Premature (future-scale you don't have yet — delete for now).

From one engagement with 47 tools: 12 were essential, 19 redundant, 11 over-engineered, and 5 premature — meaning 35 were deletable.

He then prioritizes by **impact versus risk**, tackling high-impact, low-risk items first. For example, a large customer had Datadog, Prometheus, and New Relic running simultaneously with no clear rationale. Deleting New Relic took three hours, saved $30,000, and nobody noticed. Seventeen abandoned databases with zero connections in 30 days were deprecated by email, then deleted — zero responses, zero impact.

The security angle matters here too: one of those abandoned databases was an unpatched attack surface sitting in production with no one monitoring it. Paulina adds a related example — her team once found a Flyway instance that had gone unpatched for seven or eight years because each team assumed the other was maintaining it. As she puts it, lack of ownership creates the same kind of hidden risk.

### The 30-Day Cleanup Sprint
Steve structures platform simplification as a focused 30-day effort:

- **Week 1: Audit.** Discover what is actually running — not what the team thinks is running, because those are usually different.
- **Week 2: Categorize.** Apply the four buckets and prioritize quick wins. During this phase, Steve tells the team: "For 30 days, you're not building anything — you're only deleting things."
- **Week 3: Delete.** Remove redundant tools and simplify over-engineered ones.
- **Week 4: Systemize.** Document everything — how decisions were made, why tools were removed, and how new tool decisions should be evaluated going forward. Build governance dashboards to prevent complexity from creeping back.

He illustrates this with a company whose VP of Engineering — "Sarah" — told him: "This isn't a technical problem anymore. This is a people problem." Two senior engineers had quit on the same day with the same exit interview: "I'm tired of fighting the platform." One said he had not had dinner with his kids on a weekend in six months. The team's morale score was 3.2 out of 10.

The critical insight: the team already knew what was wrong. They had known for months. But nobody had been given permission to delete anything. "That's not a cultural problem and it's not a knowledge problem. It's a permissions problem. And I gave them the permission."

Results: complexity score dropped from 42 to 26, monthly costs fell from $150,000 to $80,000 (roughly $840,000 in annual savings), and deployment time improved from two weeks to one day.

But Steve emphasizes the human outcome. A developer told him afterward: "Steve, I went home at 5 p.m. yesterday. It's the first time in eight months. And my daughter said, 'Daddy, you're home.'" That, Steve says, is what this work is really about.

### Golden Paths, Guardrails, and Developer Experience
Mattias says he wants the platform he builds to compete with the easiest external options — Vercel, Netlify, and the like. If developers would rather go elsewhere, the internal platform has failed.

Steve agrees and describes a pattern he sees constantly: developers do not complain when the platform is painful — they route around it. He gives an example from a fintech where a lead developer ("James") needed a test environment for a Friday customer demo. The official process required a JIRA ticket, a two-day wait, YAML files, and a pipeline. Instead, James spun up a Render instance on his personal credit card: 12 minutes, deployed, did the demo, got the deal. Nobody knew for three months, until finance found the charges.

Steve's view: that is not shadow IT or irresponsibility — it is a rational response to poor platform usability. "The fastest path to business value went around the platform, not through it."

The solution is what Steve calls the **golden path** — or, as he reframes it using a bowling alley analogy, **golden guardrails**. Like the bumpers that keep the ball heading toward the pins regardless of how it is thrown, the guardrails keep developers on a safe path without dictating exactly how they get there. The goal is hitting the pins — delivering business value.

Mattias extends the guardrails concept to security: the easiest path should also be the most secure and compliant one. If security is harder than the workaround, the workaround wins every time. He aims to make the platform so seamless that developers do not have to think separately about security — it is built into the default experience.

### Measuring Outcomes, Not Features
Steve argues that platform teams should measure developer outcomes, not platform features: time to first deploy, time to fix a broken deployment, overall developer satisfaction, and how secure and compliant the default deployment paths are.

He recommends monthly platform retrospectives where developers can openly share feedback. In these sessions, Steve goes around the room and insists that each person share their own experience rather than echoing the previous speaker. This builds a backlog of improvements directly tied to real developer pain.

Paulina agrees that feedback is essential but notes a practical challenge: in many organizations, only a handful of more active developers provide feedback, while the majority say they do not have time and just want to write code. Collecting representative feedback requires deliberate effort.

She also raises the business and management perspective. In her consulting experience, she has seen assessments include a third dimension beyond the platform team and developers: business leadership, who focus on compliance, security, and cost. Sometimes the platform enables fast development, but management processes still block frequent deployment to production — a mindset gap, not a technical one. Steve agrees and points to value stream mapping as a technique for surfacing these bottlenecks with data.

### Translating Engineering Work Into Business Value
Steve makes a forceful case that engineering leaders must express technical work in business terms. "The uncomfortable truth is that engineering is a cost center. We exist to support profit centers. The moment we forget that, we optimize for architectural elegance instead of business outcomes — and we lose the room."

He illustrates this with a story: a CFO asked seven engineering leaders one question — "How long to rebuild production if we lost everything tomorrow?" Five seconds of silence. Ninety-four years of combined experience, and nobody could answer. "That's where engineering careers die."

The translation matters at every level. Saying "we deleted a Jenkins server" means nothing to a CFO. Saying "we removed $40,000 in annual costs and cut deployment failures by 60%" gets attention.

Steve challenges listeners to take their last three technical achievements and rewrite each one with a currency figure, a percentage, and a timeframe. "If you can't, you're speaking engineering, not business."

### Closing Advice: Start Deleting This Week
Steve's parting advice is concrete: pick one tool you suspect nobody is using, check the logs, and if nothing has happened in 30 days, deprecate it. In 60 days, delete it. He also offers the simplicity test for free — it takes eight minutes, produces a 0-to-50 score with specific recommendations, and is available by reaching out to him directly.

"Your platform's biggest risk isn't technical — it's political. Platforms die when the CFO asks you a question you can't answer, when your best engineer leaves, or when the team builds for their CV instead of the business."

## Highlights
- **Steve Wade:** "While everyone's collecting cloud native tools like Pokemon cards, I'm trying to help teams figure out which ones to throw away and which ones to keep."
- **Steve Wade:** "That's not a team, that's a help desk with infrastructure access." — on platform teams spending most of their time explaining their own platform
- **Steve Wade:** "If the answer is yes, it means you have a platform. And if it's no, it means you have platform theater."
- **Steve Wade:** "So many platforms are like the Sagrada Familia — they look super impressive, but they're never finished yet."
- **Steve Wade:** "Boring is beautiful, especially when you call me at 3 a.m."
- **Steve Wade:** "Google needs Kubernetes, but your Series B startup needs to ship features."
- **Steve Wade:** "One spreadsheet saved them from a migration that would have just simply destroyed the business model."
- **Steve Wade:** "They knew what was wrong. They'd known for months. But nobody was given the permission to delete anything."
- **Steve Wade:** "They're not really free. They're just free to install." — on open-source CNCF tools
- **Steve Wade:** "Your platform's power doesn't come from what you add. It comes from what you have the courage to delete."
- **Mattias:** Argues that an internal platform should compete with the easiest external alternatives — if developers would rather use Vercel, the platform has failed. Also extends the guardrails concept to security: the easiest path should always be the most secure path.
- **Paulina:** Highlights the ownership gap — tools can go unpatched for years when each team assumes another team maintains them. Also raises the management dimension: sometimes it is not the platform that is slow, but organizational processes that block deployment.

## Resources
- [The Pragmatic CNCF Manifesto](https://www.pragmatic-cncf.com/) — Steve Wade's guide to cloud-native sanity, with six principles, pragmatic stack recommendations, and anti-patterns to avoid, drawn from 50+ enterprise migrations.
- [The Deletion Digest](https://newsletter.platformfix.com/) — Steve's weekly newsletter for platform leaders, delivering one actionable lesson on deleting platform complexity every Saturday morning.
- [CNCF Cloud Native Landscape](https://landscape.cncf.io/) — the full interactive map of cloud-native tools that Steve references when talking about needing to zoom out on your browser just to see everything.
- [How Unnecessary Complexity Gave the Service Mesh a Bad Name (InfoQ)](https://www.infoq.com/articles/service-mesh-unnecessary-complexity/) — a detailed analysis of why service meshes became the poster child for over-engineering in cloud-native environments.
- [What Are Golden Paths? A Guide to Streamlining Developer Workflows](https://platformengineering.org/blog/what-are-golden-paths-a-guide-to-streamlining-developer-workflows) — a practical guide to designing the "path of least resistance" that makes the right way the easy way.
- [Value Stream Mapping for Software Delivery (DORA)](https://dora.dev/guides/value-stream-management/) — the DORA team's guide to the value stream mapping technique Steve mentions for surfacing bottlenecks between engineering and business.
- [Inside Platform Engineering with Steve Wade (Octopus Deploy)](https://octopus.com/blog/inside-platform-engineering-steve-wade) — a longer conversation with Steve about platform engineering philosophy and practical approaches.
- [Steve Wade on LinkedIn](https://www.linkedin.com/in/stevendavidwade/) — where Steve regularly posts about platform simplification and can be reached directly.
