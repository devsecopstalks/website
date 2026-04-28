---
title: "#99 - AI SRE and the End of 3 AM On-Call"
date: 2026-04-27T23:12:33+01:00
lastmod: 2026-04-27T23:12:33+01:00
episode: 99
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
---

Could AI handle the worst parts of incident response before you even join the call? Mattias and Paulina talk with Birol Yildiz about AI-written status updates, fast root cause analysis, and the path from read-only help to autonomous fixes. They also explore why post-mortems and documentation may be some of the best places to start.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean b6jn6-1aac738-pb "DEVSECOPS Talks #99 - AI SRE and the End of 3 AM On-Call"  >}}

---

<!-- Video -->

## Summary

Birol Yildiz, Co-founder and CEO of ilert, predicts that AI SRE agents will reach the same maturity as coding agents by the end of 2026 — meaning on-call engineers will only get paged when the agent cannot fix the problem itself. In this episode, Mattias and Paulina sit down with Birol to explore what modern incident response looks like when AI enters the loop: from drafting customer-facing status updates in firefighting mode, to delivering a full root cause analysis before you even open your laptop at 3 AM. Birol argues it is "irresponsible not to use" AI for post-mortems, while the hosts make the case that adopting agents for operations is no longer a nice-to-have — because if defenders do not use them to find vulnerabilities first, attackers will.

## Key Topics

### Alerts vs. Incidents: Start with Actionability, Not Labels

Birol pushes back on the common impulse to draw a sharp line between alerts and incidents up front. At ilert, the starting point is simpler: does this require immediate human attention? An alert is anything that does — even if there is no business impact yet. A database disk at 95% capacity has no customer-visible effect right now, but ignoring it for two hours could take down a central service. An incident, by contrast, is declared when there is already business impact or when the response needs to scale beyond a single responder — it becomes a "coordination anchor" for mobilizing cross-department teams.

The practical takeaway: instead of debating taxonomy, limit paging to things that are actionable. Informational signals belong in low-priority alerts that wait for the next business day rather than waking someone at 3 AM. Mattias connects this to the old Nagios and Icinga world, where warning-level alerts were arguably the most important ones to watch: "Those are the ones that tell you things are about to go wrong. You should check this now before they go critical — because they will." The hosts frame this as yet another instance of shifting left — this time applied to alerting itself.

### Incident Response at 3 AM: Building Situational Awareness

When a page fires in the middle of the night, Birol describes a structured triage sequence that applies regardless of tooling. The first job is to create situational awareness: Is there business impact already? Do customers or internal stakeholders need an update? The second question is whether the on-call responder can resolve this alone or needs to mobilize additional people.

Good alerts help with the first question by embedding context — backlinks to dashboards, ongoing metric updates, and source references — so the responder does not start from a blank screen. For the second question, modern incident response platforms eliminate the manual lookup of who is on call. Instead of consulting a spreadsheet to find which database engineer is covering the Tuesday night rotation, the responder simply requests "the database person," and the platform handles routing, escalation, and automatic fallback to a secondary if the primary does not respond.

### AI-Drafted Incident Updates: The Low-Hanging Fruit

One of ilert's first generative AI use cases was drafting customer-facing incident communications. During active firefighting, the last thing a responder wants to think about is how to phrase a professional status-page update that aligns with the organization's communication standards. Birol describes a workflow where the responder types a few keywords — "payment API is broken" or even just "nothing works" — and the platform produces a polished message. It saves only a few minutes per update, but those minutes matter when you are simultaneously diagnosing and mitigating a live incident.

This resonates with Paulina's observation that developers have always hated writing reports and documentation. Incident communication was one of the first places teams started trusting AI, precisely because the stakes of a slightly imperfect status update are much lower than the stakes of an incorrect remediation action — making it a natural entry point for building organizational trust in AI tooling.

### Building the AI SRE: Root Cause Analysis in Under Four Minutes

Birol's boldest claim: by the end of 2026, AI SRE agents will reach the maturity level that coding agents achieved, and on-call engineers will only be paged when the agent cannot resolve the issue itself. The path there starts with automated root cause analysis.

When an alert fires, ilert's agent begins triage immediately — clustering 50 alerts into two or three distinct problem groups, then running a root cause investigation on each cluster. The target is to have a complete RCA ready within three to four minutes, roughly the time it takes a human to register the notification, get out of bed, and open a laptop. By the time the responder is ready to look, they see a structured assessment rather than raw alerts.

The investigation follows the same reasoning a human would apply: Where is the problem located? What has changed recently? Since the number-one cause of incidents is change — deployments, configuration updates, new releases, feature flags — the agent checks logs, metrics, and recent releases to build a complete picture. As Mattias puts it from years of late-night firefighting: "You try to go into logs, figure out what changed, look in Slack messages — but the agent is really good at finding these things. When I open the alert, it's already filled with all this information."

### From Analysis to Autonomous Remediation: The Trust Ladder

Mattias asks the critical question: where is the threshold where the agent should stop trying to fix things and wake up a human? Birol frames this as a progression — a trust ladder that organizations climb at their own pace.

The first rung is read-only analysis: the agent investigates and presents findings, but takes no action. This is where teams gain confidence by observing the quality of the agent's reasoning without risk. As discussed in [episode #98](/episodes/098-beyond-ai-sre/), where Andrey described a similar trust-building approach for Boris, the key is starting with tasks where the agent cannot do much harm.

The next step is supervised action — the agent proposes remediation steps (increase a load balancer timeout, roll back a deployment) and a human approves or rejects. Eventually, for well-understood failure modes with high-confidence diagnoses, the agent acts autonomously. ilert's governance model moves progressively from read-only to supervised to fully autonomous, with audit trails and human-in-the-loop controls at every stage.

### Closing the Loop: AI-Powered Post-Mortems and Documentation

The hosts and Birol agree that AI's biggest impact on incident management may be after the incident is over. A well-prepared post-mortem meeting requires hours of manual reconstruction — building a timeline, correlating logs, identifying contributing factors, drafting remediation proposals. Without that preparation, Birol argues, the meeting is "wasted time." With an AI agent that has already observed the entire incident lifecycle, the reconstruction comes for free.

But the agent can go further: it can suggest concrete remediation measures — timeout adjustments, architectural changes, code-level fixes — and even integrate with source code management tools to propose specific changes. Mattias sees this as closing the learning circle: the incident feeds back into the left side of the development lifecycle, preventing the next occurrence rather than just documenting the last one.

Paulina raises a broader point about documentation debt. Code is changing faster than ever thanks to AI-assisted development, but documentation is not keeping pace — and she notes that this was already a problem before AI. She recalls Azure courses being taught on outdated documentation because features shipped faster than docs could follow. If AI can handle the documentation work that engineers consistently avoid, the hosts argue, that alone justifies adoption.

### Adopting Agents Is Not a Nice-to-Have

The episode closes with a strong call to action from all three participants. Birol acknowledges that senior, highly skilled engineers tend to be the most cautious about deploying agents in production — but his advice is to start with risk-free tasks where an agent cannot do much harm and build from there.

He addresses the concern that over-reliance on agents will erode engineering skills, comparing it to the relationship between high-level programming languages and memory management: "It's always good to have a good understanding of at least one abstraction layer below." The current generation of engineers may be the last to have written significant code entirely by hand, but that foundational knowledge makes them better at directing and evaluating agents — not worse.

The business case is straightforward: organizations that reduce cycle times and respond faster than their peers gain a competitive advantage that matters to customers. The guest frames agent adoption as something that applies equally to software development and to operations, arguing it is becoming the new standard rather than an optional enhancement.

Paulina draws a parallel to security: just as security must be embedded at every step of the process, AI integration follows the same pattern. And Birol delivers the sharpest version of the argument: if you choose not to use agents to detect vulnerabilities in your software stack, attackers will use agents to find those same vulnerabilities first. Speed is not just an efficiency metric — it is a security imperative.

## Highlights

- **Birol on the future of on-call:** "We're heading to a future where you won't be paged anymore. You will only be paged if your agent is not able to fix the problem for you. My prediction is by the end of this year, AI SRE will reach the same level of maturity that we experienced with coding agents." A bold timeline from the CEO of an incident management platform — and a concrete vision of what on-call looks like when the first responder is not human. Listen to the full episode to hear how ilert is building toward that goal.

- **Birol on post-mortem preparation:** "If you just go to a post-mortem meeting without preparation, it's wasted time. But if you go prepared and have the full post-mortem document ready, it saves you hours — and that's why it's irresponsible not to use it." Strong words: not using AI for post-mortems is not just leaving value on the table, it is irresponsible. Tune in to hear what an AI-prepared post-mortem actually includes — from incident reconstruction to architectural change proposals.

- **Mattias on 3 AM firefighting:** "Waking up a lot of nights, sitting at your laptop in the dark trying to fix things — you try to go into logs, figure out what changed, look in Slack messages. But the agent is really good at finding these things. When I open the alert, it's already filled with all this information. That's a big step." Anyone who has done on-call knows this pain. Listen to the episode to hear how automated RCA in under four minutes changes the experience.

- **Birol on agents and the security arms race:** "If you think 'I'm not going to trust an agent to detect my vulnerabilities,' then an attacker will use agents to detect vulnerabilities in your software. If you don't use agents to detect the vulnerabilities before a potential attacker detects them — that's why it's not a nice-to-have." The strongest argument for agent adoption is not efficiency — it is that the adversary is already using them. Give this episode a listen for the full case on why waiting is a risk, not a strategy.

- **Birol on being the last generation:** "We're the last generation of engineers who knows how to code by hand and have hopefully written a significant piece of code by hand. But now we need to adopt agents — for software development, but also for operations. It's not a nice-to-have. It's becoming the new standard." A reflective moment from a founder who has watched the industry evolve from Nagios alerts to autonomous remediation. Listen to hear why he thinks understanding "one abstraction layer below" still matters even as agents take over.

## Resources

- [ilert — AI-First Incident Management Platform](https://www.ilert.com/) — The incident management platform Birol co-founded, built around the principle that you should only get paged when the AI cannot safely proceed on its own.

- [ilert AI SRE — Secure Incident Investigation and Resolution](https://www.ilert.com/product/ilert-ai) — ilert's AI SRE product page detailing the agent that investigates alerts, performs root cause analysis, and proposes or executes remediation actions with human-in-the-loop governance.

- [Birol Yildiz on Autonomous Incident Response and the Future of AI SRE (Harness / ShipTalk)](https://www.harness.io/blog/birol-yildiz-on-autonomous-incident-response-and-the-future-of-ai-sre) — An in-depth conversation with Birol about how AI is transforming reliability engineering from diagnosis assistance to autonomous outage resolution.

- [Postmortem Culture: Learning from Failure (Google SRE Book)](https://sre.google/sre-book/postmortem-culture/) — Google's foundational chapter on blameless post-mortems — the manual process that AI-generated post-mortem documents are now accelerating.

- [ilert Postmortem Template to Optimize Your Incident Response](https://www.ilert.com/blog/postmortem-template-to-optimize-your-incident-response) — ilert's guide to structuring post-mortem documents, providing context for the AI-generated post-mortems discussed in the episode.

- [Top AI SRE Tools in 2026 (Metoro)](https://metoro.io/blog/top-ai-sre-tools) — A comprehensive comparison of the emerging AI SRE category including ilert, incident.io, PagerDuty, and others — useful for teams evaluating where to start with AI-powered incident response.

- [Mastering Alert Fatigue: Avoiding the Monitoring and Alerting Pitfalls](https://www.jamesridgway.co.uk/mastering-alert-fatigue-avoiding-the-monitoring-and-alerting-pitfalls/) — A practical guide to the alert fatigue problem the hosts discuss, covering the distinction between actionable alerts and informational noise.
