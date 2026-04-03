---
title: "#2 - GitOps"
date: 2020-03-09T00:00:00+00:00
lastmod: 2020-03-09T00:00:00+00:00
episode: 2
author: "DevSecOps Talks"
participants: ["Andrey", "Mattias", "Julien"]
aliases:
  - /episodes/gitops/
---

What is GitOps and how to use it? Here we try to sort out the concept and how you can use it.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

{{< podbean 6k6ub-d6b123 "DEVSECOPS Talks #2 - GitOps" >}}

## Summary

GitOps sounds simple — put Kubernetes manifests in Git and let the cluster pull changes — but the episode quickly reveals the real debate is not about Git at all. Andrey argues the only genuinely novel thing about GitOps is the pull-based model where an in-cluster agent reconciles state, while Julien questions whether GitOps is good for day-2 operations or just for bootstrapping clusters. The spiciest moment: Andrey declares "life is too short to do pull requests" and advocates pushing straight to master with strong CI/CD guardrails instead.

## Key Topics

### What GitOps actually is — and what it is not

Andrey frames the discussion by separating what is genuinely new about GitOps from what teams have already been doing for years. Storing deployment specifications in Git, he argues, is just version control — teams have done that for a decade. The meaningful difference is the deployment model: instead of an external CI/CD server pushing changes into Kubernetes by calling the cluster API, GitOps places an agent *inside* the cluster that either receives a webhook or polls a Git repository, pulls in the desired state, and applies it from within.

That pull-based model is what Andrey identifies as the core innovation. It eliminates the need to expose the Kubernetes API externally — a real concern when using hosted CI services like CircleCI, which would otherwise need network access to the cluster. As Andrey puts it, exposing the API externally is risky "unless you want someone mining bitcoin on your cluster."

He references the tooling landscape at the time: [Weaveworks](https://www.weave.works/) (the company that coined the term "GitOps" and created [WeaveNet](https://www.weave.works/oss/net/), a Kubernetes CNI driver), [Flux](https://fluxcd.io/), [Argo](https://argo-cd.readthedocs.io/), and [Jenkins X](https://jenkins-x.io/). He notes that Flux and Argo were joining forces at the time of recording. He also mentions Jenkins X as a potential GitOps tool, since it runs CI/CD jobs natively in Kubernetes, but expresses skepticism about using Kubernetes for build workloads — Kubernetes is declarative about desired state, but "you cannot declare my build is successful because you have no idea how your build gonna go."

*Editor's note: Weaveworks, the company that originated the term "GitOps," [shut down in February 2024](https://techcrunch.com/2024/02/05/cloud-native-container-management-platform-weaveworks-shuts-its-doors/). Flux continues as a [CNCF graduated project](https://fluxcd.io/). The GitOps principles have since been formalized by the [OpenGitOps](https://opengitops.dev/) project under the CNCF.*

### The Weaveworks definition, read straight from the source

Andrey reads Weaveworks' concise GitOps definition from their blog and walks through its key points:

1. **The desired state of the whole system is described declaratively** — Git is the single source of truth for every environment.
2. **All changes to desired state are Git commits** — operations are driven through version control.
3. **The cluster state is observable** — so teams can detect when desired and observed states have converged or diverged.
4. **A convergence mechanism brings the system back** — when states diverge, the cluster automatically reconciles, either triggered immediately by a webhook or on a configurable polling interval. Rollback is simply convergence to an earlier desired state.

Andrey also raises a nuance about Helm: since Helm templates can produce different output depending on input variables, true GitOps implies committing not only the Helm charts but also the rendered manifests — because the generated output is what actually represents the declarative desired state.

He draws a comparison to GitHub's earlier promotion of [ChatOps](https://github.com/exAspArk/awesome-chatops), noting that many of the same ideas — observable, verifiable changes driven through a central workflow — were already part of GitHub's operational philosophy, just with a different interface.

### Two layers: infrastructure-as-code and in-cluster GitOps

Julien offers a more practical framing, splitting the problem into two distinct layers:

1. **Infrastructure as code** — setting up the underlying infrastructure (VPCs, clusters, networking)
2. **GitOps** — managing what runs *inside* the Kubernetes cluster: applications, operational tooling like monitoring (he mentions FluentD as an example), and supporting services

In Julien's model, a Git repository becomes the authoritative inventory of everything that should exist in the cluster. He describes the ideal: "if anything else is running here, alert me or kill it." That gives teams confidence that the observed cluster state matches the intended one, and helps prevent configuration drift — a problem the hosts discussed in their earlier infrastructure-as-code episode.

### Day-2 operations: where the model gets tested

While Julien appreciates GitOps for defining and bootstrapping cluster state, he is openly skeptical about its effectiveness for long-running operations. He distinguishes between two very different challenges: "setting up things" versus "running things for a long time — they're not the same."

Real environments drift. People intervene manually during incidents. Urgent fixes happen outside the normal workflow. The clean desired-state model becomes harder to maintain once the messiness of day-2 operations enters the picture. Julien frames this as an open question rather than a settled answer: GitOps may be excellent for establishing a clean baseline, but whether it holds up as a complete long-term operating model remains to be proven.

### Who controls changes: developers, operators, or both?

Andrey raises a governance concern: GitOps can look like a direct developer-to-cluster pathway. If a developer changes a YAML file, commits it, and the cluster automatically applies the change, operations staff are effectively bypassed — "there is nowhere an operation person can interfere with this."

Julien pushes back, arguing that the workflow — not the tooling — determines who has control. If changes go through pull requests with review and approval, it does not matter whether the author is a developer or an operator. Both participate in the same process. The mechanism is the same one used for application code: propose a change, review it, merge it.

### Pull requests, compliance, and "push to master"

The conversation takes its most opinionated turn when the topic shifts to pull requests.

Andrey is blunt: "Life is too short to do pull requests. You never get anything done. You do a pull request, you ask for review and then you hunt the person for two days." His preference is to push directly to master and build CI/CD pipelines strong enough to catch mistakes — "you build your system to defend yourself from the fools."

He does acknowledge an important exception: regulated industries where every production deployment must be peer-reviewed or approved. In those environments, formal review is not just a process preference but a compliance mechanism that can significantly reduce legal exposure when something goes wrong.

Andrey also shares a personal practice: because he frequently switches between projects and loses context, the first thing he does is document every verification step as part of the CI/CD pipeline. That way, when he returns to a project months later, the pipeline already encodes everything he would need to remember. "There is no guarantee that someone else has a better understanding of what I did."

### Observability gaps in GitOps pipelines

Andrey identifies a practical developer-experience problem with GitOps: the visibility gap.

In a traditional pipeline, a developer can trace a change end-to-end — build, test, deploy — in one place. With GitOps, the CI pipeline ends when it commits changes to a repository. The actual deployment happens later, inside the cluster, through a separate reconciliation process. "My pipeline stops at the place where I do commit, push, done. Since then, pipeline doesn't have much to absorb."

To understand whether a deployment succeeded, the developer needs to inspect cluster state rather than the original pipeline. Bridging that gap requires additional tooling and represents a real paradigm shift in how teams observe deployments.

He also flags a repository-structure problem: if source code and deployment manifests live in the same repository, updating manifests can trigger the source-code pipeline again — requiring conditional logic to prevent unnecessary rebuilds.

### Deployment ordering and full-system validation

Julien closes the discussion with a practical concern: deployment order matters in real systems. A proxy may need a backend to exist first. Some components cannot be rolled out in arbitrary order without causing failures.

He also questions the validation model. In a software build pipeline, teams rebuild and test the entire application from the main branch to verify the whole system works. But with GitOps, a change to one part of the cluster may be applied incrementally without validating the full cluster state end-to-end. "I will never test the full master branch and rebuild the full cluster from it, except everything goes."

That leaves an open question the hosts do not fully resolve: how can teams preserve the elegance of declarative Git-driven deployment while managing sequencing, dependencies, and whole-system confidence?

## Highlights

### "Unless you want someone mining bitcoin on your cluster"

Andrey explains the security motivation behind the pull-based GitOps model — if you use an external CI system, you need to expose your Kubernetes API, which is not exactly ideal. His colorful warning about cryptocurrency miners makes the point memorable.

*Listen to the episode for Andrey's full breakdown of why the pull-vs-push distinction is the real heart of GitOps.*

### "Life is too short to do pull requests."

The spiciest take of the episode. Andrey argues that pull requests slow teams to a crawl — you open one, ask for review, then spend two days hunting the reviewer. His alternative: push to master and build pipelines strong enough to protect against mistakes. He does carve out an exception for regulated industries where peer review is legally required.

*Listen to the episode and decide whether you agree or strongly disagree.*

### "GitOps is a nice way to set up your Kubernetes cluster — but is it a good tool to keep it running? I'm not sure."

Julien draws a sharp line between bootstrapping a cluster and operating it long-term. Setting up things and running things for a long time are "not the same." It is a refreshingly honest admission that a clean architecture pattern does not automatically solve the messy reality of day-2 operations.

*Listen to the episode for a take that many GitOps advocates skip over.*

### "You build your system to defend yourself from the fools."

Andrey's philosophy in one sentence. Rather than relying on human review processes, invest in CI/CD pipelines and automated guardrails that prevent mistakes regardless of who pushes the change. He backs this up with a personal habit: encoding every verification step into the pipeline so future-him does not have to remember anything.

*Listen to the episode for a practical argument in favor of automation over process.*

### "If anything else is running here — alert me or kill it."

Julien describes the appeal of GitOps as an authoritative inventory of what should exist in a cluster. If the Git repository defines the desired state and the cluster enforces it, anything unauthorized can be flagged or removed. It is one of the clearest expressions of why teams are drawn to the GitOps model.

*Listen to the episode for a practical view of GitOps as cluster hygiene.*

### The daughter interruption

Mid-argument about observability gaps, Andrey's daughter walks in wanting to share something exciting. It is a charming reminder that even deep infrastructure debates happen in real life with real interruptions.

*Listen to the episode for the unscripted moment — and Andrey's smooth recovery.*

## Resources

- [Flux — the GitOps family of projects](https://fluxcd.io/) — The CNCF-graduated GitOps toolkit originally created by Weaveworks. Continuously reconciles Kubernetes cluster state with Git repositories.
- [Argo CD — Declarative GitOps CD for Kubernetes](https://argo-cd.readthedocs.io/en/stable/) — A declarative, GitOps continuous delivery tool for Kubernetes with a rich web UI for visualizing application state and deployments.
- [Jenkins X — Cloud Native CI/CD Built On Kubernetes](https://jenkins-x.io/) — An opinionated CI/CD platform for Kubernetes that automates pipelines, preview environments, and promotion using GitOps principles.
- [OpenGitOps — CNCF Sandbox Project](https://opengitops.dev/) — The vendor-neutral, CNCF-backed project that formalizes GitOps principles: declarative, versioned and immutable, pulled automatically, and continuously reconciled.
- [What is GitOps Really? — Weaveworks Blog](https://www.weave.works/blog/what-is-gitops-really) — The original Weaveworks blog post defining GitOps that Andrey reads from during the episode. Weaveworks coined the term before [shutting down in February 2024](https://techcrunch.com/2024/02/05/cloud-native-container-management-platform-weaveworks-shuts-its-doors/).
- [gitops.tech](https://www.gitops.tech/) — A community resource explaining GitOps concepts, principles, and the ecosystem of tools that implement the pattern.
- [Awesome ChatOps](https://github.com/exAspArk/awesome-chatops) — A curated list of ChatOps resources and tools, relevant to Andrey's comparison between GitOps and GitHub's earlier ChatOps movement driven by Hubot.
