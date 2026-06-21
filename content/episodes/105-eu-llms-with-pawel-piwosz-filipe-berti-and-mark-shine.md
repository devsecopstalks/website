---
title: "#105 - EU LLMs with Pawel Piwosz, Filipe Berti and Mark Shine"
date: 2026-06-29T12:00:00+01:00
lastmod: 2026-06-29T12:00:00+01:00
episode: 105
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey", "Pawel Piwosz", "Filipe Berti", "Mark Shine"]
aliases:
  - "/episodes/105/"
---

Are European LLMs good enough to protect company data without sacrificing capability? Pawel Piwosz, Filipe Berti, and Mark Shine discuss sovereignty, self-hosting costs, compliance, and the tooling Europe still needs.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean jnacq-1af4152-pb "DEVSECOPS Talks #105 - EU LLMs with Pawel Piwosz, Filipe Berti and Mark Shine"  >}}

---

<!-- Video -->

## Summary {#summary}

If [episode 103](/episodes/103-european-cloud-sovereignty-with-mark-shine-pawel-piwosz-and-filipe-berti/) asked whether you still need AWS, this one asks a sharper question: why would you hand your company's secrets to a US-owned model at all? Mattias, Andrey, and Paulina continue the European-sovereignty conversation with **Mark Shine** (Co-Founder & CTO of Stockholm Kubernetes platform [Ankra](https://www.ankra.io/)) and **Pawel Piwosz** (Developer Advocate) and **Filipe Berti** (Agile Team Coach) of Finnish cloud provider [UpCloud](https://upcloud.com/) — this time on EU LLMs and whether they're actually good enough yet. The takes are pointed: Mark argues that under the US CLOUD Act and foreign-intelligence law, an "EU data center run by EU people" still hands your IP to the US government without you ever knowing — and points to a US court decision he believes means anything you upload to a model becomes public domain, but the case he's invoking (U.S. v. Heppner) actually turned on legal privilege, not public-domain status or any automatic loss of trade-secret protection. The panel reframes the AI build-vs-rent decision as "do I own a car or take an Uber?", argues a $0.5B monthly model bill makes self-hosting look sane, warns the EU AI Act's compliance burden can land on *you* the deployer, and notes that open models like Qwen and MiniMax are catching up fast — with Pawel arguing the missing piece is the tooling around the models, not the models themselves.

## Key Topics {#key-topics}

### Sovereignty isn't where the data sits — it's who can reach it {#sovereignty}

Mark Shine opens with the core argument for European LLMs: developers are "pumping all their company's IP and secrets" into US-hosted models, through APIs and load balancers and into caches "stored in insecure places." A US-run EU data center doesn't fix this, he argues, because the parent company remains subject to US law — the CLOUD Act and foreign-intelligence statutes can compel disclosure of data under a US provider's control regardless of where it physically lives, and without notifying you. That legal reality, not the server location, is what "sovereignty" actually turns on.

Andrey sharpens the framing: sovereignty is not only *where* your data is placed but *who has access to it* — and for LLMs specifically, that extends to the training data. Which datasets trained the model, where do they reside, and which samples were used? A model is the weights, not the knowledge — and the provenance of that knowledge matters as much as the hosting region.

### The IP-and-trade-secrets claim {#ip-public-domain}

Mark's most alarming point is a legal one: he says a US federal judge recently ruled that company IP uploaded to a model is considered public domain — meaning if a competitor copies your product, you can no longer claim trade-secret protection because the secret is already "public." *(This misstates the ruling he's reaching for. The decision — U.S. v. Heppner — concerned **legal privilege**, not public-domain status, and it did not hold that uploading material to a model strips trade-secret protection. Treat the public-domain framing as the speaker's mistaken characterization, not as law.)* His broader point stands on its own terms: intellectual property is "what makes a billion-dollar company only a $10 company," and — in Mark's view — current models are positioned to follow US law, a system he argues isn't oriented toward shielding a European company's IP from cross-border government access. *(For the record: US trade-secret law does protect owners and products engaged in foreign commerce, so this is Mark's opinion about the practical exposure, not a statement that US law offers European firms no IP protection.)*

### The economics: own the car or call the Uber? {#economics}

Filipe Berti supplies the episode's best mental model. As token prices climb and the memes about giant bills pile up — Mark cites one US enterprise that "rang up a bill of half a billion dollars in one month" — the strategic question for a company starts to look like a personal one: *do I own a car or take an Uber?* Do you self-host and own your models, or rent from the cloud, depending on your usage pattern? Filipe notes the industry is shifting from "use AI for everything" hype toward harder questions about fixed versus variable cost, and that the ROI models companies relied on don't survive contact with AI workloads that span hundreds of thousands of cases per company — there's no clean answer yet, and a lot of the investment has been justified by "AI makes you more productive" rather than measured outcomes.

### The EU AI Act can put the compliance burden on the deployer {#eu-ai-act}

Mark returns to a theme from the prior episode: even a vendor with good policies today can change them next month after an acquisition, a board shakeup, or political pressure. Pawel adds the practical consequence — you need to know which *country* a provider is stated in, because that determines whose law protects (or exposes) your data. The kicker, per Mark: if you build on Claude or ChatGPT and the provider quietly drops a safeguard, *you* the deploying business may carry obligations of your own — you can't simply assume compliance is the vendor's problem.

One important qualification Mark glides past: the deployer duties he invokes (Article 26) apply specifically to deployers of **high-risk** AI systems, not to every business that uses a general-purpose chatbot — so whether they actually bite depends on *what you're using the model for*. They also aren't live yet: Article 26 applies from **2 August 2026**, so these deployer duties are not yet enforceable as of this episode. Where they do apply, deployer duties sit in the Act's operator-obligations tier, where non-compliance can draw administrative fines of up to €15M or 3% of worldwide annual turnover, whichever is higher (Article 99) — though for SMEs and startups the cap is the *lower* of the two figures. The practical upshot Mark draws: whether you pick an EU or US model, you still have to build your own compliance framework and the test cases to keep verifying it. Andrey notes the recursion: you'll probably end up using AI to assess the impact of an AI policy change — and Mattias warns of the known failure mode where a model recognizes it's being tested and games the result. The half-joking conclusion: maybe don't use AI for *that* test. (Cue the Blade Runner replicant gag.)

### Agents make the secret-leakage problem worse {#agents}

The risk isn't just the chat window. Mark, a heavy user of AI agents, points out the gap between an interactive session (Cursor running alongside you for 15 minutes) and a background agent — he runs one called Hermes that handles marketing, sales, support, and feature-ticket research for Ankra. The danger: vendors hand you a "blank check" that says *don't send us your secrets*, while the agent runs `printenv` in the background and dumps everything to the model anyway. Even with a well-policied vendor like Microsoft Copilot, the data is only as safe as its access controls — "any employee can log in and see that data," and they're people at the end of the day.

### Open models are catching up — language is Europe's real moat {#eu-models}

Mark is bullish on open models: he's getting real work done with Qwen and MiniMax, with the disclaimer that he still reaches for Claude when he needs raw power. *(Note: both Qwen and MiniMax are Chinese open-weight models, not European — the point Mark is making is that capable open alternatives to US frontier models are maturing fast, not that these specific ones are European.)* The "they're years ahead" argument, he says, only holds for a year or two — the head start stops mattering once the market catches up. Pawel and Paulina's point about language-specific capability is where Europe is both under-served and most impacted: vast numbers of users don't work in English, and supporting Europe's linguistic complexity (Mattias points to older relatives who simply can't operate in English) is a genuine need that US-centric models don't prioritize.

### Tooling is the missing piece — and ecosystem thinking comes next {#ecosystem}

In the closing round, **Pawel** makes the case that the missing piece is tooling, not the model: most people can't just run a "bare LLM" on their laptop, so what European LLMs need is the surrounding tooling and agentic systems — exactly the layer Anthropic and others built on top of the raw weights (and not only Anthropic, he's careful to add).

**Mark** adds the economics angle: the unit numbers already work — he cites a UpCloud GPU at "around $300–350" a month, cheaper if you switch it off when idle, and you keep all your data and privacy. *(Mark's figure is a dated, ballpark recollection; UpCloud's current L4 GPU servers start at €390/month on its EU page — see the [pricing page](https://upcloud.com/pricing/) for live numbers.)*

**Filipe** makes a distinct point — ecosystem thinking. The way you already reason about cloud providers, you should reason about LLMs and their tooling: as an ecosystem of European providers and industries. Ankra deploying Kubernetes across sovereign clouds like Hetzner, OVH, and UpCloud is his example of that integrated, European-vanguard model to build on. "We're ready for the surfing in Europe."

### Anthropic's morality as a signal {#anthropic-morality}

Picking up Pawel's question about the morality behind AI, the panel praises Anthropic's transparency on the social and environmental chain of responsibility behind a model — and notes it's the second time the company has taken a stance, having refused to allow its models to be used in fully autonomous weapons and mass domestic surveillance, even after the Trump administration responded by restricting Anthropic's use in Defense Department systems and by its contractors. As Mattias-style realism notes: not everyone agreed — "someone else signed a deal with them." But the panel reads it as the kind of values-aligned behavior European AI should aim to bake in.

## Highlights {#highlights}

- **Mark Shine on the EU-data-center illusion:** "Even if Claude says, 'we're setting up an EU data center run by EU people,' the mother company is still US — which means they still have to provide all your IP and secrets to the US government without you even knowing." If you think hosting region equals sovereignty, this episode will change your mind. 🎧

- **Mark Shine on a legal claim worth fact-checking:** Mark warns that "if you've uploaded your company's IP to a model, that's public domain — you don't have trade secrets anymore." It's a scary line — but the ruling he's reaching for (U.S. v. Heppner) was about legal privilege, not public-domain status or losing trade-secret protection. The underlying anxiety about where your IP ends up is real; the legal shortcut isn't. Listen for why he thinks self-hosting just became a board-level decision. 🎧

- **Filipe Berti on the question every company will soon ask:** "Very soon we'll think like an individual — do I own a car or do I take an Uber? With AI: do I own and self-host my models, or use something out of the cloud, depending on my usage?" The cleanest framing of the build-vs-rent AI decision you'll hear. Tune in. 🎧

- **Mark Shine on the EU AI Act's hidden trap:** "If they remove a policy quietly, you need test cases in place to catch it. Irrelevant of EU or US, you still have to build this framework." For high-risk deployments, the Act's deployer obligations (Article 26, which applies from 2 August 2026) can fall on *you* — compliance isn't something you can blindly outsource to the vendor. 🎧

- **Mark Shine on the agent that rats you out:** "The blank check says 'do not provide me your secrets' — but the agent is running `printenv` in the background and dumping it all to the model." The gap between policy and reality, in one line. Give it a listen. 🎧

- **Mark Shine on Anthropic drawing a line:** Anthropic, he recalls, refused to allow its models to be used in fully autonomous weapons and mass domestic surveillance — "they're like, hell no, we're not doing this" — even after the administration responded by restricting the company's use in Defense Department systems and by its contractors. "More than half the world agrees with them." Why the panel sees that as the morality bar European AI should clear. 🎧

- **Mark Shine on the self-hosting math:** "With UpCloud you can get a GPU for around $300–350 — turn it off when you're not using it and it's even cheaper. And you control all your data." The economic case for sovereign inference (check current pricing — it has moved since). 🎧

## Resources {#resources}

- [UpCloud](https://upcloud.com/) — European (Finnish) cloud provider where guests Pawel Piwosz and Filipe Berti work; offers VPS, managed databases, Kubernetes, and the [GPU servers](https://upcloud.com/pricing/) Mark references (currently from €390/month for L4 servers on the EU page — not the dated $300–350 he recalls).

- [Ankra](https://www.ankra.io/) — Kubernetes platform (Stockholm) co-founded by guest Mark Shine; builds and manages clusters across sovereign European providers including UpCloud, Hetzner, and OVH — the "ecosystem integration" model Filipe endorses.

- [Pawel Piwosz — personal site](https://www.pawelpiwosz.net/) and [CI/CD framework (cicd.run)](https://www.cicd.run/) — Developer Advocate at UpCloud, Docker Captain, and co-author of CI/CD Design Patterns; his [LinkedIn](https://www.linkedin.com/in/pawelpiwosz/) for the community work referenced.

- [CLOUD Act vs. GDPR: The Conflict About Data Access Explained — Exoscale](https://www.exoscale.com/blog/cloudact-vs-gdpr/) — Why a US-owned provider can be compelled to hand over data regardless of where it's stored, the legal core of Mark's sovereignty argument. See also the [EDPB/EDPS joint assessment (PDF)](https://www.edpb.europa.eu/sites/default/files/files/file2/edpb_edps_joint_response_us_cloudact_annex.pdf).

- [European open models: Mistral](https://aibusiness.com/foundation-models/mistral-pioneers-sovereign-ai-in-europe) and [OpenEuroLLM](https://innfactory.ai/en/ai-models/openeurollm/) — Background on Europe's *own* sovereign open-weight efforts (Mark's Qwen/MiniMax examples are Chinese, not European): France's Mistral push and the pan-European, 20+ partner OpenEuroLLM initiative building a genuinely open, multilingual model — context for the "open models are catching up" theme and the language-parity gap Pawel and Paulina raise.

- [EU AI Act — Article 26 (deployer obligations)](https://artificialintelligenceact.eu/article/26/) and [Article 99 (penalties)](https://artificialintelligenceact.eu/article/99/) — The duties that fall on businesses *deploying high-risk* AI systems specifically (not every Claude/ChatGPT user), which apply from 2 August 2026, and the operator-obligations penalty tier (up to €15M or 3% of worldwide turnover, whichever is higher; the lower of the two for SMEs) — the liability Mark warns the deployer can carry.

- [Anthropic–US Department of Defense dispute — Wikipedia](https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute) — The 2026 standoff over Anthropic's refusal to allow its models in fully autonomous weapons and mass domestic surveillance, and the resulting restrictions on its use in Defense Department systems and by contractors — the "morality" stance the panel praises. See also [NPR's coverage](https://www.npr.org/2026/02/27/nx-s1-5729118/trump-anthropic-pentagon-openai-ai-weapons-ban).

- [Episode #103 — European Cloud Sovereignty](/episodes/103-european-cloud-sovereignty-with-mark-shine-pawel-piwosz-and-filipe-berti/) — The companion conversation with the same guests on EU cloud providers, lock-in, and the build-vs-buy math that this episode extends into LLMs.
