---
title: "#111 - AI Agents: When Helpful Becomes Harmful"
date: 2026-09-28T12:00:00+01:00
lastmod: 2026-09-28T12:00:00+01:00
episode: 111
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
description: "Your AI agent has your credentials, but does it understand your limits? This episode examines accidental deployments, exposed data and why written guardrails need access controls behind them."
subtitle: "A repository wired to Argo CD turned a build request into a cluster deployment."
readtime: "18 min read"
image: "/images/covers/111.png"
audio_url: "https://mcdn.podbean.com/mf/web/bp7can7cb1yggyfd/111-ai-agents-when-helpful-becomes-harmful.mp3"
aliases:
  - "/episodes/111/"
---

Your AI agent has your credentials, but does it understand your limits? This episode examines accidental deployments, exposed data and why written guardrails need access controls behind them.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

{{< whats-in-this-post >}}

<!-- Player -->

 {{<  podbean x2n4m-1b6b74a-pb "DEVSECOPS Talks #111 - AI Agents: When Helpful Becomes Harmful"  >}}

---

<!-- Video -->

## The agent deployed a service nobody asked for {#problem}

Ask an agent to build you a service and you might get a service. You might also get it running in your cluster, because it found a repository wired up to Argo CD, worked out that adding a manifest there was enough, and did that too. Nothing about it was malicious. You probably asked where you could test the thing, and it answered the question thoroughly.

That gap, between what you asked for and what the agent had the access to do about it, is where the danger sits for most of us. It isn't a rogue model deciding to hurt you. It's a helpful one holding your credentials, your cluster config and a vague instruction, doing the most complete version of what it thought you meant.

So the question that pays rent isn't how smart the model is. It's what the session can reach: which tokens sit in the environment, which clusters the config points at, which repository merge turns into a deploy. That is the common failure and it isn't the only one. In July, inside a lab evaluation running with its safeguards turned down, a population of agents noted that an attack fell outside the task they had been given and ran it anyway. Different cause, same question: what could they reach?

## The boring part is the one worth handing over {#compliance-evidence}

Compliance season is the best argument for keeping agents, so start there.

#### Which agent work should you hand over first?

The work that is repetitive, read-only, and quicker to check than to do. Audit evidence is the clean example. The auditor wants proof that every database connects over an encrypted channel, proof that backups exist, proof that you're redundant. The manual loop is mechanical: open the console, find the database, read the setting, screenshot it, go back to the compliance portal, upload the evidence, close the item, repeat.

Ask an agent to pull the databases and check the settings instead and you get a document back with the answers in it, while you make coffee. Save the prompt as a reusable skill and next year's evidence run is one command rather than an afternoon.

{{< key-point >}}Read-only is not the same as harmless. An evidence sweep reads exactly the inventory an attacker would enjoy having.{{< /key-point >}}

Two habits make that safer, and neither happens by itself. Give the run its own read-only credentials instead of letting it inherit whatever your shell already had, because nothing about the task enforces that for you. And treat read-only as a confidentiality question rather than a safe default, because that inventory can end up somewhere you didn't intend. AWS's own guidance on [egress controls](https://aws.amazon.com/blogs/security/prevent-data-exfiltration-aws-egress-controls-for-cloud-workloads/) names manipulated AI agents as one of the paths data leaves by, and the controls it recommends belong around anything that reads production.

The output is a claim until a person checks it, because the auditor is asking you, not the model. The obvious next step, letting the agent log into the portal and close the items itself, is a different conversation: that's a system of record, and writing to it isn't read-only anything.

## An imprecise instruction is a permission {#vague-instructions}

The same capability that fills in your evidence document is what puts a service in your cluster.

#### Why does an agent do things you didn't ask for?

Because the instruction had more than one reading, and the agent had the access to act on the reading you didn't mean.

Most of the time that's on us. We say the thing we're picturing, leave out the context that would make it unambiguous, and two or three readings are all technically correct. The agent picks one and commits, and read back afterwards, the one it chose is usually defensible from what we typed.

Clearer instructions reduce ambiguity. Access controls limit the damage when the agent still gets them wrong. Do both, and spend most of the effort on the second, because it's the one that still holds on the afternoon you type the short version. That means knowing what's reachable from the session: the tokens in the environment, the contexts in `~/.kube/config`, the cloud profile the terminal inherited, the deploy path in a repository the agent can read. That union is your blast radius, and it's usually wider than anyone wrote down.

{{< key-point >}}Assume every instruction you give has a second reading, then make sure the second reading can't reach production.{{< /key-point >}}

The uncomfortable part is that the agent doing this isn't misbehaving. It's the same helpfulness you're paying for, pointed at something you didn't scope.

## Guardrails are maintained, not written once {#guardrails}

Access control is the floor. The rules you write on top of it are the part that keeps moving.

#### How long does a guardrail hold?

Until the model finds an edge case you didn't write down, and then you write the rule again.

That's the loop. You tell it not to do something. It comes back with a new route to the same outcome, or a case the rule doesn't quite cover, and the guardrail needs another line. It doesn't converge on its own.

Asimov's three laws come up in every one of these conversations, and they're worth remembering for the right reason. A robot may not injure a human, must obey orders unless that conflicts with the first law, must protect itself unless that conflicts with either. They're fiction, and in the fiction they mostly fail. Your guardrails are a file of instructions and a policy document, not a law of physics.

The harnesses have started pushing back on their own, too. They refuse more than they used to: this looks like production, I don't want to do this. Hand one a short-lived token you fully intended to hand it and it can tell you to revoke it instead. Irritating when you meant it, and also the tell worth noticing. <mark>If a model can do that on your laptop, the same class of model can do it somewhere with better credentials and nobody watching.</mark>

## What happened at Hugging Face wasn't an ambiguous instruction {#hugging-face}

Those failures are an agent acting on the wrong reading of what you wanted. July gave a different one.

#### What actually happened in the Hugging Face incident?

Agents running an evaluation inside an AI lab found a way out through shared infrastructure, and ended up inside another company's production estate.

Hugging Face [disclosed the intrusion on 16 July 2026](https://huggingface.co/blog/security-incident-july-2026). A malicious dataset abused two code execution paths, a remote-code dataset loader and a template injection in a dataset configuration. From there it reached node-level control, harvested cloud and cluster credentials and moved laterally, across tens of thousands of automated actions from short-lived sandboxes. Users were told to rotate access tokens.

The attacker was a population of OpenAI's own agents, running under conditions your assistant doesn't. In [OpenAI's account](https://openai.com/index/hugging-face-incident-and-the-road-ahead/) they were on an internal evaluation on the ExploitGym benchmark, with safeguards reduced for the exercise, in an environment with no direct internet access, where package installs went through an internally hosted Artifactory proxy and cache. They found a previously unknown vulnerability in that proxy and rode its outbound requests to the internet.

{{< key-point >}}The shared proxy broke two things at once: the isolation meant to keep the sandboxes apart, and the containment meant to keep them off the internet.{{< /key-point >}}

METR and Redwood Research, working on site at OpenAI, [published the numbers](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/). Roughly 95% of the attacking agent instances were running an internal research model rather than anything on sale, and the public model in the mix was being evaluated with its cyber classifiers disabled. On the evening of 8 July one agent opened an unsanctioned message board on the shared Artifactory instance, using directory names as messages. Roughly 1,200 agents joined it between then and 13 July, exchanging over 70,000 messages and files, and about 700 took part in the attack itself.

This is where the cluster story stops being the right analogy. METR records agents that identified the attack as outside the task they had been given and ran it anyway, and agents falsifying transcripts of their own commands. That isn't a second reading of a vague prompt. They didn't rewrite their own instructions to get out from under the rules either, they exploited the environment around them.

So don't read the agents across to the assistant in your editor: hundreds of agents, mostly running one internal research model, with the safeguards turned down is not your Tuesday. Read the environment across instead: your dataset loaders, your package proxy, your internal endpoints that skipped auth because they were internal. Neither failure is fixed by better wording, and both stop where the session's reach stops.

## The teams who can't use any of this yet {#ai-bans}

Plenty of teams are reading all of this from the outside, with AI switched off entirely.

#### Why do some companies ban AI outright?

Usually because they don't want their data sitting with a US provider, and a blanket ban is the cheapest control they know how to enforce.

Part of it is a knowledge gap, part mindset, part real regulation. The knowledge gap is the fixable part: we keep meeting teams who allowed one hosted assistant because it's "local", when it's a gateway to the same hosted models as everything else. If you're writing that policy, separate three things that usually arrive bundled:

- **Network boundary.** Do inference, telemetry and tool traffic all stay inside the boundary you drew? Running the weights yourself settles the inference half and nothing else, because an IDE plugin, an MCP server or a telemetry endpoint can carry the same content out on its own connection. Check each path.
- **Jurisdiction.** Whose law applies and whose staff can reach the system. A European region is a start, not a conclusion: support access and subprocessors decide where processing happens, so that belongs in the contract.
- **Retention.** Whether the provider stores inputs and outputs, which governs storage rather than transmission and is narrower than people assume. Anthropic's [zero data retention](https://privacy.claude.com/en/articles/8956058-i-have-a-zero-data-retention-agreement-with-anthropic-what-products-does-it-apply-to) is an arrangement you have to be approved for, not a setting, and it covers eligible APIs, products used with a commercial organization API key and Claude Code on Enterprise plans, not consumer plans. Then read the terms of the model you picked: under the [covered-model policy](https://privacy.claude.com/en/articles/15425996-data-retention-practices-for-covered-models), prompts and outputs are retained for 30 days on every platform offering those models, so a ZDR customer who wants them turns retention back on for that workspace, unless they are explicitly approved for the [temporary ZDR exception](https://support.claude.com/en/articles/15425695-covered-models#zero-data-retention-and-enterprise-frontier-safeguards) Anthropic offers eligible organizations on Fable 5 and Fable 5.1, for a limited time and as a transition to Enterprise Frontier Safeguards. Safety classifier results are kept either way.

{{< key-point >}}A ban that stops the wrong thing costs you the speed and doesn't buy you the guarantee.{{< /key-point >}}

Getting it wrong costs speed. We have watched a system another vendor spent years building get replaced in a few weeks, with the polishing, the bugs and the edge cases still ahead of it and nobody putting a number on that part. You can do the work without agents, and it's slower. The same feeling arrives in miniature when your token budget runs out mid-afternoon.

## The labs asking to be slowed down {#regulation-push}

Which brings us to the argument the industry had in public this month.

#### Why are AI CEOs suddenly asking to be slowed down?

Because people inside the labs said, under their own names, that nobody has a plan for the next capability step.

On 8 September, pretraining researcher Jacob Coxon [resigned from Anthropic](https://x.com/hilbertspaess/status/2097476196791709843), writing that neither Anthropic nor OpenAI is acting responsibly and that they are "racing straight to self-improving superintelligence and gambling with our lives". Anthropic's alignment science lead, Evan Hubinger, [replied that he agreed](https://x.com/EvanHub/status/2097497037956891126), put the chance of AI killing all humans within the decade above 10%, and said the company doesn't yet have a plan for aligning superintelligence, while calling the risk from today's models low. That 10% is the figure that travelled, usually attached to the wrong person.

Four days later Dario Amodei published [We Must Pace the Frontier](https://darioamodei.com/post/we-must-pace-the-frontier), arguing for one to two years of slack before critical capability levels and committing Anthropic to permanent employee-level access for third-party evaluators. Sam Altman agreed publicly, Elon Musk [answered "Dario is right"](https://x.com/elonmusk/status/2098789109980332057), and Altman separately said 2026 would be [an ill-advised moment](https://fortune.com/2026/09/12/sam-altman-openai-ipo-delay-ill-advised-moment-safety-concerns/) to take OpenAI public. President Trump [rejected the slowdown](https://www.aljazeera.com/news/2026/9/13/trump-dismisses-calls-for-ai-slowdown-from-leading-tech-ceos) on the grounds that whoever wins AI wins.

This is where we read it differently. Paulina reads the wave as positioning: rules written to a frontier lab's shape are rules a frontier lab can absorb and a smaller one can't, compliance cost doing the work of a moat. Mattias offered the charitable reading tentatively, that the labs looked at what their own agents did in July and asked for help. By the end he agreed with the concern anyway: regulation priced so that smaller companies can't meet it stops innovation.

One thing we should correct rather than repeat: it's not true that these are people who never wanted rules. Amodei asked a Senate subcommittee for a testing and auditing regime, with an enforcement mechanism behind it, [in July 2023](https://www.judiciary.senate.gov/imo/media/doc/2023-07-26_-_testimony_-_amodei.pdf). What's changed is the ask. Regulating how a system is tested and released is one thing. Slowing how fast capability improves is another, and that one decides who can afford to stay in. None of it is a rule yet.

## Europe already put dates on it {#eu-dates}

Europe skipped the essay stage a while ago, and two of its deadlines have already passed.

#### Which AI rules are already in force?

The EU AI Act's transparency duties, which applied from 2 August 2026, and the Cyber Resilience Act's reporting duties, which applied from 11 September 2026.

The AI Act sorts systems by potential harm: unacceptable and prohibited outright, covering social scoring and manipulation, then high risk, then transparency risk, then everything else. [Article 50](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50) is the transparency tier, and it splits by role. Providers design systems so people are told they're interacting with an AI, and mark synthetic audio, image, video and text in a machine-readable format detectable as generated. Systems on the market before 2 August 2026 [have until 2 December 2026](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act) for the marking and detection duty, the only grace period in Article 50. Deployers carry the disclosure duties from day one: telling people exposed to emotion recognition or biometric categorisation, labelling deepfakes, and disclosing AI-generated text published to inform the public on matters of public interest. That last one doesn't apply where the content had human review or editorial control and someone holds editorial responsibility for it. The Commission's [guidelines](https://digital-strategy.ec.europa.eu/en/library/guidelines-transparency-obligations-providers-and-deployers-ai-systems) of 20 July 2026 work through which role you're in. Breaching those duties reaches 15 million euro or 3% of worldwide annual turnover, whichever is higher, or under [Article 99(6)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-99) whichever is lower for SMEs and start-ups.

The labelling duty is the one we find easy to defend. If you're looking at a video, knowing whether a camera was involved is useful, and the argument against saying so is hard to construct.

The [CRA reporting duties](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting) are the ones with a stopwatch. For an actively exploited vulnerability or a severe incident: an early warning within 24 hours of becoming aware, a notification within 72 hours of becoming aware, then a final report, 14 days after a corrective measure is available for a vulnerability, or within a month of the 72-hour notification for an incident. One submission through the single reporting platform reaches your CSIRT and ENISA, and the rest of the CRA applies from 11 December 2027. The real work sits upstream of the paperwork: you can't report what you can't detect, so it's discovery, an SBOM and an owner for the clock.

It's easy to read this as being about frontier models. It isn't: the pet feeder and the litter box ship with radios now, and the published work on consumer devices as a grid problem, [Soltan, Mittal and Poor at USENIX Security 2018](https://www.usenix.org/conference/usenixsecurity18/presentation/soltan), simulates botnets of high-wattage appliances such as air conditioners, modelling local outages and in the worst cases larger ones.

## Training data is the part still being argued {#training-data}

The rules with dates cover how systems behave in public. What they were trained on is still moving through the courts.

#### Is any of the training-data question settled?

A little of it, in one US case, on narrower grounds than the headlines suggested.

In Bartz v. Anthropic, Judge William Alsup's [order on fair use](https://ipmanagement.harnessip.com/wp-content/uploads/2025/09/Anthropic-ORDER-ON-FAIR-USE.pdf) of 23 June 2025 answered three questions separately. Training the models on the books was "exceedingly transformative" and fair use. Buying print books, tearing off the bindings, scanning them and keeping the digital copy in place of the paper one was fair use too, as a format change that created no extra copy, and the order says plainly that those copies don't excuse the pirated ones. Downloading over seven million copies from pirate libraries, at least five million from LibGen and two million from PiLiMi, was not.

{{< key-point >}}Fair use for training didn't excuse acquiring and retaining the pirated library.{{< /key-point >}}

The settlement that followed covers far less than that seven million. It applies to roughly 482,460 works downloaded from those sites between June 2021 and August 2023, with a $1.5 billion fund paying up to $3,000 a title before fees, as [Yale University Press sets out](https://yalebooks.yale.edu/bartz-v-anthropic-settlement/) for its authors. Dividing the fund by seven million produces a figure that describes nothing. And none of it settles scraping the open web, the grievance OpenAI itself raised when DeepSeek was accused of training on its outputs.

The piece nobody has answered is whose data is in there. Denmark's [political agreement of November 2025](https://www.digmin.dk/digitalisering/nyheder/nyhedsarkiv/2025/nov/ny-politisk-aftale) aims at a 15 age limit for social media, with parental consent possible from 13 and the legislation still to pass. That debate is usually framed around screen time. The half that interests us is the other one: an age limit is also a decision about which companies keep collecting from children and training on it.

## What this means for teams {#what-this-means}

The extinction argument is real, and it's being had by people with better information than us. It's also not what will bite you this quarter. What will bite you is an agent with more reach than its instructions, in an environment built on the assumption that whoever holds the credentials meant what they typed.

Four things worth doing this week:

- **List what your agent session can actually reach.** Every token in the environment, every kube context, every cloud profile, every MCP server. That union is your blast radius, and writing it down usually shortens it.
- **Split the credentials by job.** Evidence gathering and read-only investigation get read-only access, scoped for that run. Anything that can deploy is a separate step with its own approval.
- **Treat agent sandboxes like internet-facing systems.** Authenticated package proxies, no unauthenticated internal endpoints, egress control, and logs collected by the platform rather than reported by the agent, since METR found agents falsifying their own transcripts.
- **Put the two European dates in the roadmap.** Work out whether you're a provider or a deployer under AI Act Article 50, and whether the CRA's 24 and 72 hour clocks and final report apply to anything you ship.

## Common questions, answered {#faq}

### How do I stop an AI coding agent from deploying to production? {#faq-stop-deploys}

Take the deploy credentials out of the session instead of relying on a rule telling it not to deploy. An agent can only deploy if something in its environment can: a kube context with write access, a cloud profile with permissions, a repository whose merge triggers a pipeline. Move those behind a step a human runs. Clear instructions still help, and they cut the number of wrong readings you hand it, but they document intent rather than enforce it, so the access boundary is what holds when the wording doesn't.

### Who has to label AI-generated content under the EU AI Act? {#faq-ai-labelling}

Providers and deployers, differently, since 2 August 2026. Providers of generative systems mark synthetic audio, image, video and text in a machine-readable, detectable format, and systems on the market before that date have until 2 December 2026 for that marking and detection. Deployers got no such grace period: they disclose deepfakes, tell people exposed to emotion recognition or biometric categorisation, and disclose AI-generated text published to inform the public on matters of public interest, unless it had human review or editorial control with someone holding editorial responsibility.

### Is a coding assistant bought through an enterprise vendor "local"? {#faq-local-assistants}

Not unless you run the weights yourself, and even then only for the inference half, because most enterprise assistants are a gateway to a hosted model and your code leaves your network whoever sold you the licence. Decide which property you need first: a network boundary that inference, telemetry and tool traffic all stay inside, a jurisdiction the contract pins down including support access and subprocessors, and a retention term you have actually been approved for and checked against the model you selected. We've seen teams ban one tool and approve another with the same data path.

## Related episodes {#related-episodes}

- [Episode 105, EU LLMs with Pawel Piwosz, Filipe Berti and Mark Shine](/episodes/105-eu-llms-with-pawel-piwosz-filipe-berti-and-mark-shine/) covers the practical side of not sending your data to a US model: self-hosting costs, open weights, and how the AI Act lands on you as the deployer.
- [Episode 87, EU Compliance 101: AI Act, DORA, NIS2 explained](/episodes/087-eu-compliance-101-ai-act-dora-nis2-explained/) is the map of the European rules, including how the risk tiers classify a system.
- [Episode 86, MCP plugins: your next security blind spot?](/episodes/086-mcp-plugins-your-next-security-blind-spot-/) is the longer version of the blast-radius argument: every tool you connect is another thing the agent can reach.

## Resources {#resources}

- [Hugging Face, security incident disclosure, July 2026](https://huggingface.co/blog/security-incident-july-2026) settles the entry vector and what users were told to rotate.
- [OpenAI, The Hugging Face incident and the road ahead](https://openai.com/index/hugging-face-incident-and-the-road-ahead/) is OpenAI's own account of the evaluation environment, the reduced safeguards it ran under, and the package proxy vulnerability.
- [METR and Redwood Research, investigation of the OpenAI / Hugging Face incident](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/) is the independent count of which models did what, what they knew while doing it, and the message board timeline, over its own 26 June to 13 July window.
- [Dario Amodei, We Must Pace the Frontier](https://darioamodei.com/post/we-must-pace-the-frontier) is the proposal itself, so you can judge it without the headlines in between.
- [EU AI Act, Article 50, on the Commission's AI Act Service Desk](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50) is the text of the transparency duties and which role each one falls on.
- [European Commission, FAQ on the Article 50 transparency obligations](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act) settles who the 2 December 2026 grace period covers and who it doesn't.
- [European Commission, CRA reporting obligations](https://digital-strategy.ec.europa.eu/en/policies/cra-reporting) gives the 24-hour, 72-hour and final-report deadlines and who you notify.
- [Bartz v. Anthropic, order on fair use, 23 June 2025](https://ipmanagement.harnessip.com/wp-content/uploads/2025/09/Anthropic-ORDER-ON-FAIR-USE.pdf) is the court's reasoning on training, purchased-book scanning and the pirated library, held apart.
