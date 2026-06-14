---
title: "#103 - European Cloud Sovereignty with Mark Shine, Pawel Piwosz and Filipe Berti"
date: 2026-06-14T11:10:53+01:00
lastmod: 2026-06-14T11:10:53+01:00
episode: 103
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey", "Mark Shine", "Pawel Piwosz", "Filipe Berti"]
aliases:
  - "/episodes/103/"
---

Mark Shine, Pawel Piwosz, and Filipe Berti discuss why the default choice of AWS, Azure, or GCP is no longer automatic for every team. The conversation covers cost, managed services, open source, AI workloads, and what European cloud providers can offer instead.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean f9i9z-1aeab7f-pb "DEVSECOPS Talks #103 - European Cloud Sovereignty with Mark Shine, Pawel Piwosz and Filipe Berti"  >}}

---

<!-- Video -->

{{< youtube B5ApttZM13U >}}

## Summary {#summary}

Three vendors walk into a podcast and agree on the same heresy: the era of reflexively reaching for AWS, Azure, or GCP is ending — at least in Europe. Mattias, Andrey, and Paulina are joined by **Mark Shine** (Co-Founder & CTO of Stockholm-based Kubernetes platform [Ankra](https://www.ankra.io/)), and **Pawel Piwosz** (Developer Advocate) and **Filipe Berti** (Engineering Manager) from Finnish cloud provider [UpCloud](https://upcloud.com/), for a frank conversation about European cloud sovereignty, open source as a competitive weapon, and what AI is doing to the build-vs-buy math. The spicy takes land fast: that American SaaS is often "just hosting an open source tool with a UI on top" while charging 5x your own engineer; that one team cut OPEX 60% — about $100,000 a year — simply by moving infrastructure off GCP to European providers because they already had the skills; that the AWS DNS outage made single-provider architecture look "not smart, not reliable"; and that the EU AI Act, fines and all, might actually be a feature. Plus why being a "fan of AI but not a fanboy" is the right posture, and why the future is hybrid, not one European champion to rule them all.

## Key Topics {#key-topics}

### The AI infrastructure stack is suddenly its own thing {#ai-stack}

Mark opens on a shift he's watched up close: the open source community has stopped just shipping models and started shipping the *full stack* needed to run them in production. He points to [llm-d](https://github.com/llm-d/llm-d), the Red Hat–led, Kubernetes-native distributed inference project he saw demoed at the Lovable office in Stockholm with Red Hat presenting. His read on why it matters isn't the technology — load balancing across LLMs, embeddings, KV-cache-aware routing have existed for a while — but that it's all "packed into one daemon," deployable as a single service. "That's the game changer," he argues.

The deeper point: AI infrastructure is the first stack in years that *doesn't* generalize. A database is universal, a VM is generic, most managed services are reusable across workloads — but these AI-serving tools are custom to AI and nothing else. Even Amazon, Google, and Microsoft, Mark notes, haven't "cracked" offering this as one off-the-shelf product; build it yourself on a hyperscaler and you end up assembling open source components anyway. Pawel adds the cost angle: alongside llm-d, small language models and projects like [vLLM](https://github.com/vllm-project/vllm) let smaller players run inference at a fraction of big-infrastructure prices — so the race is now about brainpower, not just dollars.

### Pricing, leanness, and the "milking the stone" critique {#pricing}

The panel's sharpest recurring theme is value. Filipe frames UpCloud's positioning around *granularity* — slicing server plans into leaner, more fine-tuned capacity tiers because that's what their user base keeps asking for, with the same revamp coming to managed databases and other services. The persona they design for, he says, is the experienced platform engineer who wants control and thinks carefully about what's excess.

Mark puts the contrast more bluntly. European providers, he argues, still operate on an "old-fashioned" model of fair value rather than "milking every drop of blood out of the stone." Dig into what some American services actually charge for, he says, and "they're just hosting an open source tool and putting a UI on top of it" — for five times what running it yourself would cost. Pawel ties it to culture: the US leans heavily on SaaS ("using something others are delivering"), while in Poland and Eastern Europe the instinct is "why use a foreign service if I can use my own brainpower and own the tool?" He's careful to say there are pros and cons to both — open source means giving up polished UIs and vendor support — which is exactly the gap Ankra targets.

### Vendor lock-in, multi-cloud, and a 60% cost cut {#lock-in}

This is where Ankra's pitch crystallizes. Managed services are great, Mark concedes — right up until you're locked to AWS or GCP. Run open source tooling you control, and "your bureaucracy is in your control." His real-world example: a company running everything managed on GCP integrated with Ankra (which already connects UpCloud, Hetzner, and OVH) and realized they could go multi-cloud "without investing into it." Because they'd already built the operational skill to know good logs from bad, they moved infrastructure to European providers, left their APIs on GKE, and dropped OPEX by 60% — roughly $100,000 a year for a single team.

Filipe reinforces it with the enterprise pattern he's seeing: hybrid cloud is becoming a deliberate architecture choice, partly driven by last year's major DNS failures (the kind that took half the internet offline) that made concentrating everything in one provider look like a revenue risk. He cites "perhaps the third biggest company in England" moving warehouse workloads from AWS to GCP for cost and efficiency once they'd mastered enough internally. The throughline: engineering overhead is real at every maturity level, and the more cloud experience you gain, the more you realize you can do differently. The hosts covered adjacent ground in [episode #90 on Kubernetes vs. managed services](/episodes/090-k8s-vs-managed-services-cost-lock-in-and-reality/).

### "You tick the box but forget to use it" {#managed-services}

A host (channeling years of consulting war stories) delivers one of the episode's best lines: setting up an RDS on AWS is like his mother using her phone — she knows *how*, but not *what it does*. With European providers you often get a VPS and install the database yourself, which forces understanding. The counterpoint, raised across the panel, is that managed services were genuinely valuable precisely because they removed a required skill set — but that convenience breeds complacency.

The killer anecdote: a team paying for Google Cloud SQL with premium support, looking good on paper, "ticking the box" for high availability — while routing all traffic to a single instance. "You're paying for it, it looks good on the box, but you forgot to actually use it." Pawel generalizes it: we adopt deeply managed services "fingers crossed it'll work and be secure," but you still need to know what's inside — the parameters, the kernel tuning, the SQL query design. Throwing a bigger machine at a slow NGINX is the lazy fix; updating the config is the real one.

### AI as a leveler — for the people who actually read the output {#ai-leveler}

Everyone agrees AI is shrinking the knowledge gap that managed services used to paper over. Pawel's framing — "I'm a fan of AI, but not a fanboy" — captures the panel's posture: used deliberately, AI helps you understand the deeper layers of a platform fast. Filipe notes local implementation engineers are now working "four times faster," turning a two-month Redis HA rollout into a week or two, which compounds the cost savings.

Mark adds a useful caveat to the "more knowledge = more AI power" assumption. He's met people with modest starting expertise who simply *keep digging* — "if I use these tools, how do I make it highly available? okay, and then how do I…" — and become superheroes fast. The failure mode isn't lack of expertise; it's the people who don't read what the AI returns, rush through, get bad results, and blame the tool. Pawel's deadpan: it's the same as copy-pasting from Stack Overflow without understanding the comment. "We've all done it."

### The EU AI Act, sovereignty, and "values baked in" {#eu-act}

The conversation turns geopolitical. Mark sees the EU AI Act as a genuine positive: a mechanism to require AI models serving EU citizens to *prove* their safeguards rather than "maybe they're there." He flags the liability trap — if you build on OpenAI and they quietly drop a policy, *you*, the business, are on the hook for the fine, not them. European-hosted AI aligned to EU values, built on open source with sound unit economics, is his bet against an American "AI bubble." He concedes enforcement will be hard but loves the transparency principle.

Filipe supplies the commercial backdrop: recent EU investigations into the big clouds' practices — allegations of gatekeeping and unfair competition that make it hard for local clouds to win deals — and the Digital Markets Act as part of rebalancing. Both he and Pawel stress this isn't only about data location; it's also about *which models* you run, where European options like Mistral are catching up. Pawel notes you often don't need the absolute latest frontier version anyway — a slightly older European model at a lower pay-per-token price may be plenty.

### Don't build a European hyperscaler — integrate the ecosystem {#hybrid-future}

Filipe's strategic thesis closes the loop: the goal should *not* be to clone "the European AWS." No single player will have it all, and the certification-and-skills moat the big clouds built can't be replaced overnight. The smarter path is conveniently integrating Europe's existing providers into a coherent, hybrid, diverse ecosystem — which is precisely the role infrastructure tooling like Ankra plays.

Pawel reframes the "but they don't have as many services" objection as an excuse: the hyperscalers had a multi-year head start, and adoption is a two-way street — every workload you run on a European provider today funds the next service it builds. Mark closes on the human signal he's seeing: individual developers, not just companies, are actively choosing European providers on places like Reddit because the money stays in the society they live in. Mark's final 30 seconds: developer self-service is the way forward — "it's not about isolated DevOps, it's about empowering them as much as possible."

## Highlights {#highlights}

- **Mark Shine on what American SaaS is really charging for:** "You start realizing — oh, they're just hosting an open source tool and putting a UI on top of it. I'm paying five times what it would cost to have my own engineer." His argument: European providers still price for fair value instead of "milking every drop of blood out of the stone." Listen for how that reframes build-vs-buy in 2026. 🎧

- **Mark Shine on a 60% cost cut nobody had to engineer from scratch:** "We dropped their OPEX by 60% — about $100,000 a year — just by moving infrastructure to European providers, because they already had the skills." A single team, multi-cloud without a rebuild, APIs left on GKE. The episode breaks down exactly how. 🎧

- **Filipe Berti on why single-cloud stopped being safe:** "Given the DNS failures last year — half the world without services — concentrating everything in one provider became something not smart, not reliable, not redundant enough. And that impacts your revenue." Hybrid cloud as a board-level resilience decision, not a hobby. Tune in. 🎧

- **A host on the managed-service illusion:** "You're paying for the premium HA option, it looks good on the box, you ticked it — but you sent all your traffic to one instance. You forgot to actually use it." The line that should make every team re-read their cloud bill. 🎧

- **Pawel Piwosz on the right way to use AI:** "I'm a fan of AI, but not a fanboy." The gap, he argues, isn't expertise — it's whether you actually read what the AI gives you, or rush through it like an un-read Stack Overflow answer and then blame the tool. 🎧

- **Mark Shine on the EU AI Act's hidden liability:** "If you're using OpenAI and they remove one of those policies — they're not the ones on the hook for the fine. You are." Why he thinks EU-hosted, open-source AI with its values baked in is the safer bet. 🎧

- **Filipe Berti on what Europe should NOT build:** "Don't try to build the European version of one of the big three, as if one player will have it all. Smartly integrate the ecosystem we already have." A contrarian take on cloud sovereignty worth the full listen. 🎧

## Resources {#resources}

- [Ankra](https://www.ankra.io/) — AI-powered, Kubernetes platform (Stockholm) co-founded by guest Mark Shine; builds and manages clusters visually across providers including UpCloud, Hetzner, and OVH. The multi-cloud "without investing into it" angle in this episode.

- [UpCloud](https://upcloud.com/) — European (Finnish) cloud infrastructure provider where guests Pawel Piwosz and Filipe Berti work; offers VPS, managed databases, managed Kubernetes, and GPU servers. See their [8 Layers of European Digital Sovereignty](https://upcloud.com/blog/8-layers-european-digital-sovereignty-explained/) for the sovereignty framing discussed.

- [Pawel Piwosz on LinkedIn](https://www.linkedin.com/in/pawelpiwosz/) — Developer Advocate at UpCloud, Docker Captain, and DevOps community contributor.

- [llm-d](https://github.com/llm-d/llm-d) ([overview](https://www.redhat.com/en/topics/ai/what-is-llm-d)) — Kubernetes-native distributed LLM inference framework (now a CNCF project) founded by Red Hat, Google Cloud, IBM Research, CoreWeave, and NVIDIA. The "packed into one daemon" project Mark highlights; built on [vLLM](https://github.com/vllm-project/vllm).

- [EU AI Act — European Commission regulatory framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — The official European Commission page on the AI Act. For GPAI model providers (the case discussed here), [Article 101](https://artificialintelligenceact.eu/article/101/) caps fines at €15M or 3% of annual worldwide turnover; the broader €35M / 7% maximum applies to other infringements such as prohibited practices. Note: [artificialintelligenceact.eu](https://artificialintelligenceact.eu/) is an independent tracker maintained by the Future of Life Institute, not an official EU source.

- [AWS US-EAST-1 DNS/DynamoDB outage analysis — ThousandEyes (Oct 20, 2025)](https://www.thousandeyes.com/blog/aws-outage-analysis-october-20-2025) — Root-cause breakdown of the ~15-hour DNS-driven cascade that took down much of the internet. The "single provider isn't redundant" event Filipe references.

- [Sovereign AI in 2026 — definition and real choices](https://dpliance.com/en/blog/sovereign-ai/) — Overview of European model options (Mistral, Aleph Alpha, Lucie) and open-weight models like Qwen deployed on European infrastructure. Grounds the "which models, not just which region" point.

- [Episode #90 — Kubernetes vs. Managed Services: Cost, Lock-In and Reality](/episodes/090-k8s-vs-managed-services-cost-lock-in-and-reality/) — The earlier DevSecOps Talks discussion of managed-service trade-offs that this episode extends into the European-cloud and AI era.
