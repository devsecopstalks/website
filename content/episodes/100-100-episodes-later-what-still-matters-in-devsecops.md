---
title: "#100 - 100 Episodes Later: What Still Matters in DevSecOps"
date: 2026-05-07T12:36:44+01:00
lastmod: 2026-05-07T12:36:44+01:00
episode: 100
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/100/"
---

What changed between episode 1 and episode 100, and what stayed surprisingly constant? The hosts revisit infrastructure as code, observability, incident response, secrets, compliance, and supply chain security through the lens of six years of conversations. It is part retrospective, part editorial reset for what the next 100 episodes should focus on.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean ncyen-1ab9b57-pb "DEVSECOPS Talks #100 - 100 Episodes Later: What Still Matters in DevSecOps"  >}}

---

<!-- Video -->

{{< youtube Zhkv7kauxTw >}}

## Summary {#summary}

Six years, 100 episodes, three hosts (and one alumni) — the DevSecOps Talks crew uses the milestone to look back at what stuck, what faded, and what to do next. Andrey argues the show's biggest mistake to avoid in the next 100 episodes is mutating into "yet another AI podcast," even as he admits AI is genuinely hard to ignore now that supply chain attacks and people shipping half-baked code quickly under AI assistance are real. Paulina frames AI as just another hype cycle in the lineage of containers and Kubernetes — and notes that the boring fundamentals look more relevant than ever because "machines can't understand what makes good software or good infra." Mattias points to Security Now's 20-year run as the north star, and the hosts commit to revisiting the evergreen topics — IaC, observability, incident response, secrets, compliance — with sharper preparation for 2026.

## Key Topics {#key-topics}

### 100 episodes, six years, and the math of consistency {#100-episodes}

The hosts open with the basic arithmetic of doing a podcast: at a weekly cadence, 100 episodes is two years; at the cadence DevSecOps Talks actually keeps, it took roughly six. Andrey points out that scaling the show is not about doing more — it is about distributing the load. Adding hosts means not everyone has to be in every recording, and rotating guests turns the burden into community participation rather than a publishing treadmill.

The conversation revisits how the hosting bench has shifted over the years. Julien Bisconti co-hosted episodes 1–68 ([episode #68 was his last](/episodes/068-julien-s-last-episode-/)). Paulina joined starting from [episode #69](/episodes/069-who-is-paulina-/), bringing a new voice and her own outside podcast. Andrey reveals he has now started a second podcast focused on agentic AI in DevOps — "if you don't have enough Andrey in your life, there is more" — explicitly to keep that material out of DevSecOps Talks.

### The commitment for the next 100: don't become "yet another AI podcast" {#stay-on-topic}

The clearest editorial decision in the episode: stay true to the show's topic. Andrey is blunt — the temptation to mutate everything into an AI podcast is real, because that is what is happening across the industry, but the hosts want to resist it. AI will appear when it is genuinely relevant — supply chain risk, AI-enabled phishing, people shipping half-baked code quickly under AI assistance — not as the default frame for every episode.

Paulina reframes the AI moment as a hype cycle — first containers, then Kubernetes, now AI — and finds that pattern reassuring rather than threatening. The base principles the hosts have championed for years (good software practice, organizational design for change, CI/CD that fits the team) are arguably *more* important now, because agents cannot infer them on their own. As she puts it, CI/CD is hard precisely because "it depends on your organization — how do humans organize to make change to the system. Well, guess what? The AI cannot see that."

### The north star: Security Now and better preparation {#preparation}

Mattias names the bar the show is aiming for: Steve Gibson's Security Now, which has been running for 20 years. "If we can get like 20% as good as Steve is, that would be an achievement." Reaching for that bar means investing more in preparation rather than relying on conversational instinct alone.

Andrey describes the episode-prep workflow he is now using: every prior episode, with descriptions, sits in a local repository; Claude with a 1M-context window summarizes themes across the entire back catalog; Claude Code and Codex compete to produce the best article description. The goal is "less babbling," more concise delivery, while keeping the conversational feel that makes the show different from a polished briefing — the meet-up energy of "I heard about this tool at a conference, how do I actually try it?"

### The six-year topic ledger: what stuck {#evergreen}

Andrey walks through the topics that have proven durable across six years of the show. **Infrastructure as code** is the founding subject ([episode #1](/episodes/001-infrastructure-as-code/), [#35 IaC Revisited](/episodes/035-iac-revisited-2021/), [#43 Terraform one-year recap](/episodes/043-terraform-one-year-recap/)) and remains evergreen. **Kubernetes** is now baseline. **Platform engineering** has been covered in at least four dedicated episodes ([#38](/episodes/038-platform-teams-with-henrik/), [#56 Backstage](/episodes/056-backstage/), [#95](/episodes/095-from-platform-theater-to-golden-guardrails/), [#96](/episodes/096-keeping-platforms-simple-and-fast-with-joachim-hill-grannec/)) with more on the way. **GitOps** appeared as the second episode ever ([#2](/episodes/002-gitops/)) — and Andrey cites an AI-generated statistic that 93% of organizations using a platform leverage GitOps in 2026, while flagging on-air that the number came from research done by AI and may not be accurate.

**Continuous topics** that keep returning: immutable infrastructure, the three pillars of observability ([#30](/episodes/030-observability/)), Git branching strategy ([#26](/episodes/026-git-branching-strategies/)), incident response ([#73](/episodes/073-incident-response-key-preparations-you-need/), [#74](/episodes/074-from-preparation-to-execution-handling-an-active-incident/), [#75](/episodes/075-learning-from-the-crisis-post-incident-actions/)), hiring and career growth ([#31](/episodes/031-hiring/), [#32](/episodes/032-getting-hired/)), distributed-team communication, secrets management ([#81](/episodes/081-keeping-secrets-safe/)), and multi-account landing zones ([#66](/episodes/066-multi-account-strategy-and-landing-zones-account-segmentation-approaches-for-security-and-efficiency-on-aws/)).

### What faded: unikernels, Nomad, service mesh defaults, and Waypoint {#faded}

Not everything aged well. Andrey runs through the topics that did not deliver on early promise:

- **Unikernels** ([#29](/episodes/029-unikernels/)) — collapsed as a hype, still niche; might find a niche again in AI workloads where boot speed matters.
- **Nomad** — never lost interest from a small base of users, but lost the orchestration war to Kubernetes definitively.
- **Service mesh** ([#33](/episodes/033-service-mesh/)) — the "Istio as default" future never arrived; simpler ingress patterns won.
- **HashiCorp Waypoint** — discussed a couple of times on the show, has since been discontinued.
- **Sturdy** ([#36](/episodes/036-sturdy/)) — the Git successor the hosts interviewed; the hosts have not heard much about it since.

Andrey also notes how his own usage shifted: HashiCorp Vault was a frequent topic in early episodes ([#13](/episodes/013-all-you-need-to-know-about-setting-up-hashicorp-vault/)), but he stopped using it professionally once it became clear it is built for big-organization problems that do not match his consulting work at FivexL.

### Compliance went from a footnote to the main event {#compliance}

In 2020 the compliance conversation was largely HIPAA and PCI DSS. Six years later, the hosts have dedicated entire episodes to the EU regulatory wave — [#87 on AI Act, DORA, and NIS2](/episodes/087-eu-compliance-101-ai-act-dora-nis2-explained/) and [#88 on DSA and MiCA](/episodes/088-eu-compliance-101-dsa-mica-explained/). The shift from "compliance is a checkbox for finance and healthcare" to "compliance is a daily concern for practitioners" mirrors the rise of **continuous compliance** tooling: the hosts interviewed Kosli ([#44](/episodes/044-kosli/)) early, and tools like Vanta, Drata, and SecureFrame have built a category.

### Supply chain security: theoretical to operational {#supply-chain}

Supply chain security has been a recurring beat — [#46](/episodes/046-supply-chain/), [#53 Supply chain again](/episodes/053-supply-chain-again/), and most recently [#97 Shift left, get hacked](/episodes/097-shift-left-get-hacked-supply-chain-attacks-hit-devs/). Andrey marks the current moment as the inflection point where supply chain attacks went from theoretical risk to the kind of news that forces real prioritization in budgets and roadmaps. Expect this thread to continue in 2026.

### The plan for the next 100 {#next-100}

Concretely: revisit the evergreen topics — IaC, observability, incident response, secrets, hiring — for a 2026 audience, and bring in guests who have spent serious time thinking about each. Frequent collaborators get a nod: Paul Stack ("he is a frequent offender") joined for [#92 on agent-native infra](/episodes/092-from-system-initiative-to-swamp-agent-native-infra-with-paul-stack/), and Helga is fondly remembered. The improved preparation pipeline, with Claude Code and Codex generating show notes, is the production upgrade that should make the next stretch tighter and more useful.

## Highlights {#highlights}

- **Andrey on resisting the AI-podcast drift:** "We should stick to the topic, try not to mutate everything into an AI podcast, because that's what's happening right now with industry. AI brings relevance to the topics we discuss — but we shouldn't become the AI-first thingy like as many other shows mutated." A clear editorial line in a year where every show is being pulled toward the same frame. Listen to episode #100 for the hosts' commitment to keep DevSecOps Talks about DevSecOps practitioners first.

- **Paulina on the AI hype cycle:** "First it was containers, then it was Kubernetes, and I feel we're going exactly in a similar fashion with AI. The base principles that we used — that were considered good practice — are even more relevant today, because those machines can't understand what makes good software or good infra." A grounding take from a self-described builder. Tune in to hear why CI/CD being hard is exactly why agents won't replace senior judgment any time soon.

- **Mattias on the north star:** "Steve Gibson with Security Now is doing an amazing job. If we can get like 20% as good as Steve is, that would be an achievement. But for him, it took a long professional career — he has something to say." Setting the bar at 20 years of consistent, opinionated security commentary. Listen for the hosts' commitment to better preparation in the next 100.

- **Andrey on what didn't age well:** "Unikernels — the hype collapsed, still kind of niche, might be quite applicable with AI workloads. Nomad stayed niche, never went anywhere — it lost the orchestration war to Kubernetes. Service mesh — Istio as default never happened. HashiCorp Waypoint got discontinued." A frank scorecard from six years of covering infrastructure trends. Catch the full episode for what the hosts think will fade from today's hype list next.

- **Andrey on supply chain going operational:** "Supply chain security — we spoke about that, but now with the latest news, it's becoming an issue. It's going from theoretical threat to a real thing that requires action and prioritization." If you have been treating supply chain as a 2026 problem, you are already late. Listen to hear which themes the hosts will revisit with new urgency.

## Resources {#resources}

- [DevSecOps Talks — Episode Archive](https://devsecops.fm/episodes/) — The full back catalog of 100 episodes, useful for tracing how the topics in this retrospective evolved over six years.

- [Security Now Podcast (Steve Gibson, GRC)](https://www.grc.com/securitynow.htm) — The 20-year-running security podcast Mattias names as the north star for DevSecOps Talks. A masterclass in long-form, opinionated technical commentary.

- [Hype Cycle — Gartner Research](https://www.gartner.com/en/research/methodologies/gartner-hype-cycle) — The framework Paulina invokes when comparing AI to the earlier container and Kubernetes waves; useful for putting current AI excitement in historical context.

- [HashiCorp Waypoint — Discontinued (HashiCorp Discuss)](https://discuss.hashicorp.com/t/hashicorp-waypoint-end-of-maintenance/68597) — Confirmation of the Waypoint discontinuation Andrey mentions, for listeners tracking which tools to remove from their evaluation lists.

- [OpenGitOps Principles (CNCF)](https://opengitops.dev/) — The OpenGitOps working group's reference site covering GitOps principles and project resources; useful background for the GitOps thread that started in episode #2.

- [Anthropic Threat Intelligence Report — November 2025](https://www.anthropic.com/news/disrupting-AI-espionage) — Anthropic's disclosure of an AI-orchestrated cyber espionage campaign; relevant background for the broader point about AI-assisted offensive operations the hosts argue a DevSecOps show cannot fully ignore.

- [Postmortem Culture: Learning from Failure (Google SRE Book)](https://sre.google/sre-book/postmortem-culture/) — Foundational reading on the incident-response practice the hosts have returned to across episodes #73, #74, #75, and #99 — and plan to revisit again in the next 100.

- [DevSecOps Talks on LinkedIn](https://www.linkedin.com/company/devsecops-talks/) — Where the hosts continue conversations from the show and where listeners can suggest topics for the next 100 episodes.
