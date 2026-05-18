---
title: "#101 - Infrastructure as Code in 2026: Still Essential or Already Changing?"
date: 2026-05-19T00:16:31+01:00
lastmod: 2026-05-19T00:16:31+01:00
episode: 101
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/101/"
---

Six years after the podcast first covered infrastructure as code, what still holds up and what does not? The hosts revisit IaC through a 2026 lens: platform teams shipping secure-by-default modules, stacks becoming standard, GitOps making more sense for Kubernetes, and AI raising new questions instead of removing old ones. It is a practical look at where infra tooling is heading and what teams should stop assuming.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean 4itsu-1ac94ec-pb "DEVSECOPS Talks #101 - Infrastructure as Code in 2026: Still Essential or Already Changing?"  >}}

---

<!-- Video -->

{{< youtube mrLdSzqji1A >}}

## Summary {#summary}

Six years after [episode #1 on Infrastructure as Code](/episodes/001-infrastructure-as-code/), is IaC still worth caring about in a world where agents can write Terraform and call cloud APIs directly? Andrey walks through how the discipline has actually evolved — modules became the de facto reuse primitive, stacks emerged as deployable units, and platform teams now ship internal libraries of secure-by-default building blocks. The hosts also cover the messy parts: GitOps versus CI for Kubernetes, why Crossplane can hammer your S3 bucket into oblivion, the Terralith problem at scale, and what Stategraph and Paul Stack's Swamp are trying to fix. The verdict: IaC is more relevant than ever — but the layers around it have changed enough that 2020-era advice is no longer current.

## Key Topics {#key-topics}

### How you slice IaC depends on how the organization is shaped {#shape}

There is no universal IaC structure — only one that fits the organization. Paulina lays out the two main axes: scope (single-account/single-region versus multi-account/multi-region) and layering. Most non-trivial setups split into a **base infrastructure** layer (networking, shared databases, KMS keys, the things every team depends on) and the **application** layer that sits on top. In larger organizations, a dedicated team typically owns the base layer so that product teams can build without re-deriving foundational decisions every time.

Slicing further — by team, by product, by domain — is then a question of organizational design, not Terraform syntax. The structure of the code mirrors the structure of who is responsible for what.

### Modules were never meant to be reusable libraries — and now they are {#modules}

Andrey points out a quiet bit of history: Terraform modules were not designed to become an industry-wide library of reusable infrastructure components. They evolved into that. Today the [public Terraform Registry](https://registry.terraform.io) is a deep catalog of community modules, and the AWS CDK community built the same idea more deliberately with **constructs**.

The practical pattern in mature organizations: a platform team maintains an internal library of primitives — S3 bucket modules with logging and encryption baked in, secure-by-default networking constructs, opinionated wrappers over the cloud-vendor APIs. Developers consume those primitives rather than writing raw resources. The bucket is private, encryption is set, logging is configured — the developer just supplies a name and a few parameters. This is what platform engineering looks like at the IaC layer, and it is now table stakes, not an advanced practice. The hosts have explored this thread in [episode #95 on platform theater versus golden guardrails](/episodes/095-from-platform-theater-to-golden-guardrails/) and [episode #96 with Joachim Hill-Grannec](/episodes/096-keeping-platforms-simple-and-fast-with-joachim-hill-grannec/).

### Stacks: the newest deployable unit {#stacks}

The biggest conceptual addition since the hosts first covered IaC in [episode #1](/episodes/001-infrastructure-as-code/) and [episode #35 in 2021](/episodes/035-iac-revisited-2021/) is **stacks**. The evolution looks like this:

1. One big state file describing everything.
2. Slice it into modules for reuse.
3. Add environments (dev, staging, prod).
4. Add stacks — composed pieces of infrastructure deployable as a unit, parameterized per environment.

A networking stack, for example, can be deployed to development, staging, and production with environment-specific parameters, without copy-paste. Stacks are a newer concept in the IaC framing — they didn't exist when the hosts first covered this topic — and most IaC tools today have some flavor of the idea.

### GitOps vs CI: why GitOps makes more sense for Kubernetes {#gitops}

GitOps comes up briefly — and Andrey frames it as "mostly a fancier name for CI applying infrastructure," with one substantive exception. When the workload is **Kubernetes**, GitOps tools like [Argo CD](https://argo-cd.readthedocs.io) run *inside* the cluster and pull changes from Git, rather than having an external CI server push to the Kubernetes control plane API. That is a real architectural win: you do not have to expose the Kubernetes API to the outside world (or to GitHub Actions public runners), because the apply happens from within. The rest of CI can stay on public runners; the cluster pulls what it needs. The hosts originally covered this idea back in [episode #2 on GitOps](/episodes/002-gitops/) — the principle hasn't changed, just the tooling around it.

### Crossplane: same shape as Terraform, with a Kubernetes twist (and a footgun) {#crossplane}

[Crossplane](https://www.crossplane.io) takes the same general idea — declare your cloud resources, let a controller make them real — but uses Kubernetes manifests and a Kubernetes reconciliation loop. Adoption is uneven; the hosts agree it shows up "here and there" rather than as a default.

Andrey shares a war story worth remembering: because Kubernetes continuously reconciles desired state, a misbehaving Crossplane resource can repeatedly hammer a cloud API trying to converge. He saw a stuck S3 bucket deletion attempt cycle so aggressively against AWS that it racked up real cost — "is it still there? trying to delete. is it still there? trying to delete." This was five years ago and may well be fixed, but the broader point stands: reconciliation loops against billed APIs need timeouts and backoff configured deliberately.

### HashiCorp's full IBM lap, and the OpenTofu fork {#hashicorp}

The HashiCorp story has come full circle since the BSL relicense. Both co-founders are now gone — [Mitchell Hashimoto departed in late 2023](https://www.hashicorp.com/en/blog/mitchell-reflects-as-he-departs-hashicorp), and [Armon Dadgar stepped down](https://www.sdxcentral.com/news/hashicorp-co-founder-and-cto-armon-dadgar-steps-down-to-pause-and-recharge/) more recently. [IBM completed the HashiCorp acquisition in February 2025](https://newsroom.ibm.com/2025-02-27-ibm-completes-acquisition-of-hashicorp,-creates-comprehensive,-end-to-end-hybrid-cloud-platform), and Terraform is now being integrated with Ansible — what someone on the internet jokingly called "Terrible." The joke is real product strategy now.

[OpenTofu](https://opentofu.org), the open-source fork, has done what competition is supposed to do: forced movement. The hosts cover the current state in detail in [episode #83 with Cole Bittel](/episodes/083-opentofu-vs-terraform-where-we-are-now-with-cole-bittel/) and [episode #85](/episodes/085-is-it-time-for-opentofu-our-hashiconf-takeaways/), and the HashiCorp thread in the [100th-episode recap](/episodes/100-100-episodes-later-what-still-matters-in-devsecops/). The hosts argue competitors like Pulumi and OpenTofu forced Terraform to move faster after a stagnant stretch.

### The Terralith problem and Stategraph {#terralith}

A real pain point at scale: the **[Terralith](https://masterpoint.io/blog/terralith-monolithic-terraform-architecture/)** — a Terraform state so big it becomes impossible to work with quickly. The usual advice is to slice it, but slicing has its own coordination costs.

[Stategraph](https://stategraph.com/) is one of the more interesting recent attempts at a fix. It pitches itself as "a better control plane for Terraform" — backed by a database instead of S3 state files, with state represented as a graph so plans can be calculated much faster. For organizations sitting on a multi-thousand-resource state, this is worth watching.

### The agentic AI question: is IaC still relevant? {#ai}

Yes — but with new constraints. Andrey's argument: agentic AI can write Terraform with "some level of success" and can call cloud APIs directly with "some level of success." What it cannot do reliably is be **deterministic**. The whole point of IaC is that the same input produces the same output, repeatably. An agent that drifts is the opposite of that contract.

This is exactly the problem Paul Stack is targeting with **[Swamp](https://github.com/systeminit/swamp)** — agent-native infrastructure tooling designed to make agentic IaC deterministic by construction. The hosts went deep on this in [episode #92 with Paul Stack](/episodes/092-from-system-initiative-to-swamp-agent-native-infra-with-paul-stack/). For now, the takeaway is that IaC is not being replaced by AI; it is being *re-architected* so AI can use it safely.

## Highlights {#highlights}

- **Andrey on Terraform modules outgrowing their original design:** "Terraform modules were never intended to be reusable components in the way they are now. That's what we got." A reminder that the most useful patterns in infra tooling often emerge from the field, not from the spec. Listen to episode #101 for how this accidental library became a platform-engineering primitive.

- **Andrey on Crossplane's reconciliation footgun:** "It had a conflict, it was trying to delete a bucket, not succeeding, and just hammering that bucket with API requests. Is it still there? Trying to delete. Is it still there? Trying to delete." A cautionary tale about pointing Kubernetes-style reconciliation at billed cloud APIs. Catch the episode for what to watch for if you're considering Crossplane.

- **Andrey on IBM's HashiCorp era:** "Someone coined the terrible — putting together Ansible and Terraform. It was a joke, but now it's happening." HashiCorp came full circle into IBM, both co-founders are gone, and the Ansible/Terraform integration is now a real roadmap item. Tune in for the hosts' read on the IBM integration and how OpenTofu-driven competition is finally pushing Terraform to move again.

- **Andrey on agentic AI versus determinism:** "Agentic AI is there. It could write your Terraform with some level of success. It could also call the cloud API with some level of success. But it's not deterministic." The clearest framing of why IaC isn't going anywhere — and why Paul Stack's Swamp matters. Listen for what "agent-native infrastructure" actually means in practice.

- **Andrey on the Terralith:** "People are now being advised to slice it. But Stategraph might be able to do it for you." The big-state problem that keeps biting mature teams, and one recent attempt worth watching to address it without forcing a refactor. Catch the full episode for what's worth piloting in 2026.

## Resources {#resources}

- [Terraform Registry](https://registry.terraform.io) — Public registry of Terraform providers and reusable modules; the de facto library for community-built infrastructure primitives.

- [AWS CDK Constructs](https://docs.aws.amazon.com/cdk/v2/guide/constructs.html) — Official AWS CDK v2 documentation on constructs (L1/L2/L3), the analog of Terraform modules in the CDK ecosystem.

- [OpenTofu](https://opentofu.org) — Linux Foundation–stewarded, fully open-source fork of Terraform; covered in detail in [episode #83](/episodes/083-opentofu-vs-terraform-where-we-are-now-with-cole-bittel/) and [episode #85](/episodes/085-is-it-time-for-opentofu-our-hashiconf-takeaways/).

- [Argo CD](https://argo-cd.readthedocs.io) — Declarative GitOps continuous delivery for Kubernetes; the reference implementation of the in-cluster pull model the hosts describe.

- [Crossplane](https://www.crossplane.io) — CNCF project that turns Kubernetes into a control plane for managing external cloud infrastructure via manifests.

- [Stategraph](https://stategraph.com/) — Database-backed control plane for Terraform that represents state as a graph for faster, scoped plans; pitched at teams suffering from Terralith problems.

- ["Terralith" — Masterpoint blog](https://masterpoint.io/blog/terralith-monolithic-terraform-architecture/) — Defines the Terralith antipattern (a single-root-module / single-state Terraform monolith) and outlines the practical pitfalls of letting state grow unbounded.

- [Swamp (systeminit/swamp on GitHub)](https://github.com/systeminit/swamp) — Open-source, agent-native infrastructure CLI from Paul Stack and the System Initiative team; covered in [episode #92](/episodes/092-from-system-initiative-to-swamp-agent-native-infra-with-paul-stack/).
