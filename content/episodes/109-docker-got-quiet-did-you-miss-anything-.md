---
title: "#109 - Docker Got Quiet. Did You Miss Anything?"
date: 2026-07-27T12:00:00+01:00
lastmod: 2026-07-27T12:00:00+01:00
episode: 109
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/109/"
---

What changed in Docker while everyone was watching AI? The hosts review BuildKit, Buildx, security features, provenance, and the updates practitioners should know.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean q5pvm-1b1e5a3-pb "DEVSECOPS Talks #109 - Docker Got Quiet. Did You Miss Anything?"  >}}

---

<!-- Video -->

## Summary {#summary}

Docker got quiet, and the hosts wanted to know why. Paulina joins Andrey to revisit a topic the podcast last covered in [episode #45](/episodes/045-docker/) back in November 2022, and they land on an uncomfortable verdict: Docker the company lost the battle for production and now survives as development tooling riding on the glory of its own name. Andrey walks through the numbers — $207M ARR in 2024, by third-party estimates — alongside the 2024 Docker Hub rate-limit blowup that he thinks did the company more harm than good, and an AI pivot (MCP catalog, Ask Gordon, a Model Runner that "feels very much like a reskinned Ollama") that neither host has seen a single customer actually use. The good news for practitioners: if you're worried Docker sailed on without you, it didn't — most of what shipped is security and provenance tooling plus syntax sugar, or "synthetic sugar," as Andrey accidentally put it.

## Key Topics {#key-topics}

### Containers became a commodity — like Git {#commodity}

The framing that opens the episode: containers are now something you're just *supposed* to know, the same way you're supposed to know Git. Andrey's analogy is that Git ships continuous releases, but the core workflow — clone, branch, commit, push — hasn't meaningfully changed in years. New flags, some convenience tooling, nothing that rewrites how you work.

Paulina agrees on the core but pushes back on the conclusion. The key stays stable, but side functionality does change, and because nobody's writing about it — "everything is about AI right now" — you miss workflow improvements that would make your life easier. Containers are foundational to building software and get almost none of the attention.

Both hosts note the vocabulary lag: most people still say "Docker" when they mean "containers," and that's less and less accurate every year.

### Great technology, hard business model {#business-model}

Andrey traces the arc. Docker's technical foundation was excellent and adoption was enormous — 2013 through 2015, people talked about Docker the way people talk about AI in 2026. (Docker itself grew out of dotCloud, a PaaS company, and the runtime was open-sourced in 2013.) Then Kubernetes arrived and got even bigger.

But the business model never landed. Docker followed the open-source-startup playbook — gain adoption, raise money, figure out monetization later — and Andrey's read is that it never really worked. The company was "almost extinct in 2019," when the enterprise business was sold off. Andrey was personally involved on the sales side of the Docker Enterprise platform offering and saw the deals on the table; Kubernetes offering a cheaper version of the same thing killed it.

What stabilized things was **paid Docker Desktop** — free below a company-size and revenue threshold, paid above it — plus Docker Hub subscriptions and a secure-images business. The figures Andrey cites are third-party estimates published by Sacra, and the dates don't all line up to the same year: **$207M ARR for 2024**, up 25% from **$165M in 2023**, **over one million paid subscriber seats**, and a **$2.1B valuation dated to 2023**. Not massive, but real.

On hardened images specifically, Andrey thinks others do it better. **Chainguard** is the most prominent: if you can run a Go binary on `scratch` you don't need much, but for something like Python, buying pre-hardened images that get patched fast is a genuine service.

### The Docker Hub squeeze and the registry escape hatch {#docker-hub}

The 2024 announcement of consumption-based pull limits on Docker Hub produced what Andrey calls a huge blowback from the developer community — and in his view, Docker "did more harm than good for themselves with this kind of approach." A lot of people went looking for alternatives, and found plenty:

- **GitHub Container Registry** — if you're already on GitHub, everything's in one bundle
- **Amazon ECR** — and every other cloud provider has an equivalent
- **JFrog Artifactory** — already in place at many organizations
- **Harbor** — self-hosted

Andrey's conclusion: a registry isn't something people will pay a premium for. There are too many alternatives and it's too easy to self-host. Paulina adds the practical nuance — you pay *somewhere*, whether that's hosting costs or a cloud plan — and points out that most teams end up mirroring base images locally anyway. You don't want to pull from Docker Hub or anyone else's registry on every build; you host your own, update it on your schedule, and build on top of that.

Docker Hub is still the default destination for community-built images. It's just no longer a moat.

### The AI pivot nobody seems to be using {#ai-pivot}

With AI everywhere, Docker tried to reposition itself as an AI destination. Andrey runs through what shipped:

- **Ask Gordon** — a Docker AI agent you can ask about your images and Docker itself
- **Docker MCP Catalog and Toolkit** — a curated set of containerized MCP servers, positioning Docker as the gateway where you run MCP servers
- **Docker Model Runner** — run models locally through Docker

Andrey thinks the MCP gateway idea was genuinely interesting positioning. But neither host has seen it in the wild. "Haven't seen also in any of the customers that they use it," Paulina says. And Model Runner "feels very much like a reskinned Ollama" — Ollama already does that job.

*(MCP — Model Context Protocol — is the emerging standard for connecting AI agents to external tools and data sources.)*

### The 2026 competitive landscape {#landscape}

Andrey re-explains the architecture that makes the alternatives possible, and it's worth getting the layers straight because they get conflated constantly. When you run `docker`, you're using the **Docker CLI**, which talks over a socket to a daemon that implements the **Docker Engine API** — usually local, but it can be a remote machine. The CLI isn't the whole thing, and what's on the other end only has to speak the Engine API; it doesn't have to be Docker's own daemon, which is why Docker-compatible endpoints and drop-in CLIs exist.

Below that sit two more layers, and they're distinct:

- **The CRI layer** — the Container Runtime Interface that Kubernetes speaks. **containerd** and **CRI-O** both implement it. Docker Engine itself does not: Kubernetes removed its direct Docker Engine integration (dockershim) in v1.24, so running Docker Engine under Kubernetes now requires the separate **`cri-dockerd`** adapter. Docker Engine is still a supported option in the Kubernetes docs — it's just no longer directly integrated by default, and containerd or CRI-O is what you'll find in practice. CRI-O displacing Docker as the Kubernetes runtime was already the story when the hosts covered this in 2022.
- **The OCI layer** — the low-level runtime that actually creates and runs the container. containerd doesn't do this itself; it manages container lifecycle and delegates through a shim to an OCI runtime such as **runc**. Docker Engine sits on top of containerd, which sits on top of runc. So "containerd is the runtime" is shorthand: it's the lifecycle manager, and runc (or an alternative like crun or a sandboxed runtime) is what does the running.

What Paulina sees in the field, across customers who don't always let her pick:

- **Kaniko** — still in use, though it was archived by Google in June 2025 and is now effectively frozen (Chainguard picked up a fork)
- **AWS ECR** and self-hosted **Artifactory** / JFrog
- **BuildKit** — increasingly common
- **Podman** — "not so much." Andrey notes the recurring Reddit pattern: people saying it doesn't work for them, and people replying that they just don't know how to cook it. His read is that if you genuinely want daemonless and rootless, it's a good option that costs you extra work.
- **Docker Desktop** — still the most common for local development, mostly because developers are used to it. People outside the infra world go with what they know.
- **OrbStack** — widely used among Mac users
- **Rancher Desktop** — seen once or twice; Paulina is not a fan
- **Compose** — alive and well, but almost entirely for local development and end-to-end test environments where you need several containers without spinning up cloud infrastructure. Not production.

Andrey's summary of it all: the market is saturated, and the dominant narrative is that Docker lost production. Kubernetes dominates orchestration, commonly over containerd or CRI-O at the CRI layer; Docker is delegated to development tooling, and it's a fairly small player even there because of the open-source alternatives. It still rides the name. Paulina frames it more gently — Docker *was* the industry standard, so its name became the word for the whole category.

Two alternatives Andrey singles out as worth checking if you're shopping: **Lima** (Linux VMs on macOS) and **nerdctl** (a Docker-compatible CLI for containerd).

### What actually shipped: BuildKit and Buildx features worth knowing {#buildkit-features}

This is the practical payload of the episode. Andrey runs through the accumulated build features, and the theme is unmistakable — almost all of it is security, provenance, and convenience:

**Secrets and credentials**
- `--mount=type=secret` — mount a secret into a build step without persisting it in a layer (around for a long time now)
- `--mount=type=ssh` — bind your SSH agent, useful for cloning private repos during a build
- `--mount=type=cache` — persist caches across builds

**Isolation**
- `RUN --network=none` — run a step with no network access. Andrey's example: you downloaded a script from somewhere and you're worried it'll exfiltrate something. Cut the network.
- `RUN --security=insecure` — the opposite direction. This isn't just "extra kernel capabilities": Docker documents it as running the step without sandbox protections, equivalent to `docker run --privileged`. It's deliberately opt-in on both ends — buildkitd has to be started with the `security.insecure` entitlement allowed (`--allow-insecure-entitlement security.insecure` or the equivalent config), and the build itself has to pass `--allow security.insecure`.

**Dockerfile conveniences**
- `ADD --checksum` — verify the checksum of remote artifacts you pull in, instead of doing it yourself
- `COPY --link` — creates independent layers that survive base image changes
- `COPY --parents`, `--exclude`, `--chmod`, `--chown`
- **Heredoc syntax** — write multi-line `RUN` blocks without chaining everything with `&& \`

**Supply chain and provenance**
- `--sbom=true` and `--provenance` — attestations are built in now, with format options, so you can track dependencies
- Compose-level supply chain provenance

**Tooling**
- `docker buildx build --check` — runs Docker's built-in build checks (its own predefined rule set) against your Dockerfile without building it. Handy, and it may reduce how much you lean on a separate linter, but it isn't a drop-in replacement for every third-party Dockerfile linter.
- `docker buildx history` — past build records
- Two separate debugging interfaces, both **experimental**, and worth not conflating:
  - `docker buildx debug build` launches Buildx's interactive CLI monitor — you get a shell into the build to inspect a failure, optionally only `--on error`. Failure inspection, not stepping.
  - `docker buildx dap build` is the breakpoint workflow: it starts a debug session over the [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/overview) so a DAP-capable editor (VS Code, for example) drives stepping, breakpoints, and `stopOnEntry`. Docker warns it may take backwards-incompatible changes.
- **Build policies written in Rego** — validate your build inputs (base images, Git repos, HTTP downloads) against policy. Also **experimental**, and it needs Buildx 0.31.0 or later.

Also for practitioners: **Compose v5** is out. And no, you didn't miss two major releases — Docker skipped v3 and v4 entirely, because the legacy Compose *file format* used `version: "3.x"` and jumping the CLI to 5 creates a clean break from that history.

Andrey's honest assessment: if you're already using build secrets and multi-stage `COPY --from`, you're using most of the useful stuff. The rest marginally improves your processes. "It feels more like some synthetic sugar around that. What I meant is syntax sugar, not synthetic sugar." Same conclusion as Git — the product is mature and won't change much. He suggests the next revisit in 2030.

## Highlights {#highlights}

- **Andrey on Docker's real position in 2026:** "Docker as a company, as a runtime, it lost battle for production." Kubernetes dominates orchestration — commonly over containerd or CRI-O — and Docker Engine isn't even directly integrated there anymore; it needs the `cri-dockerd` adapter. What's left for Docker is development tooling, plus the name, and the name is still doing a lot of work. Listen to episode #109 for the full autopsy.

- **Andrey on the Docker Hub rate-limit blowup:** Docker tried to squeeze Docker Hub in 2024 with consumption-based pull limits. Andrey's verdict: "they actually did more harm than good for themselves with this kind of approach." A lot of teams went looking for alternatives — GHCR, ECR, Harbor, Artifactory — and found out how easy a registry is to replace. Tune in for why registries turned out to be a bad thing to monetize.

- **The AI pivot nobody's using:** Docker shipped an MCP catalog, an MCP toolkit, Ask Gordon, and Model Runner. Andrey found the MCP gateway idea genuinely interesting positioning — but neither he nor Paulina has seen a single customer using any of it, and Model Runner "feels very much like a reskinned Ollama." Catch the episode for the honest field report.

- **Andrey on Rego, everywhere:** Buildx now supports build policies written in Rego — still experimental, and it needs Buildx 0.31.0 or later. His take: "If you write some Rego policies, you don't love the circus. But yeah, now you can suffer from Rego in one more place." Real security value, delivered in the language nobody asked for. Listen for the rest of the BuildKit feature rundown.

- **Andrey on Podman:** The Reddit pattern never changes — half the thread says it doesn't work, the other half says you just don't know how to cook it. His read: if you genuinely want daemonless and rootless, Podman is a good option that costs you more work. Paulina sees it rarely; Docker Desktop and OrbStack still dominate local development. Tune in for the full 2026 landscape.

- **Andrey on whether you're missing out:** "If you're worrying that the Docker should be sailing without you — probably not." Four years of releases amount to security, provenance, and syntax sugar. Same story as Git: the product is mature. He's proposing the next Docker episode for 2030. Listen to #109 to find out what you can safely ignore.

## Resources {#resources}

- [Episode #45 — What is happening with Docker?](/episodes/045-docker/) — The November 2022 predecessor to this episode, with Andrey, Mattias, and Julien covering Docker's history, adoption, and the Docker/containerd/CRI-O distinction.

- [Docker revenue and valuation — Sacra](https://sacra.com/c/docker/) — The third-party estimates behind the numbers Andrey cites: $207M ARR for 2024 (up 25% from $165M in 2023), over 1M paid subscriber seats, and a $2.1B valuation dated to 2023.

- [Container runtimes — Kubernetes Docs](https://kubernetes.io/docs/setup/production-environment/container-runtimes/) — The CRI layer, straight from the source: containerd, CRI-O, and why Docker Engine now needs the `cri-dockerd` adapter after dockershim was removed in v1.24.

- [Revisiting Docker Hub Policies — Docker Blog](https://www.docker.com/blog/revisiting-docker-hub-policies-prioritizing-developer-experience/) — Docker's own walk-back of the 2024 rate-limit plan after the community reaction, including the decision not to enforce the April 2025 changes.

- [Build secrets — Docker Docs](https://docs.docker.com/build/building/secrets/) — Official reference for `--mount=type=secret` and `--mount=type=ssh`, the two features Andrey singles out as the ones actually worth using.

- [Dockerfile reference — Docker Docs](https://docs.docker.com/reference/dockerfile/) — Covers the rest of the syntax discussed: heredocs, `ADD --checksum`, `COPY --link/--parents/--exclude`, `RUN --network=none`, and the privileged behavior and entitlement requirements of `RUN --security=insecure`.

- [Docker MCP Catalog and Toolkit — Docker Docs](https://docs.docker.com/ai/mcp-catalog-and-toolkit/) and [Docker Model Runner](https://docs.docker.com/ai/model-runner/) — The AI pivot, documented. Judge the positioning for yourself.

- [Lima](https://github.com/lima-vm/lima) and [nerdctl](https://github.com/containerd/nerdctl) — The two alternatives Andrey explicitly recommends checking out: Linux VMs on macOS, and a Docker-compatible CLI for containerd.
