---
title: "#92 - From System Initiative to SWAMP: Agent-Native Infra with Paul Stack"
date: 2026-02-20T20:34:25+00:00
lastmod: 2026-02-20T20:34:25+00:00
episode: 92
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey", "Paul"]
---

What can you automate with SWAMP today, from AWS to a Proxmox home lab? How do skills, scripts, and reusable workflows plug into your stack? Could this be your agent’s missing guardrails?

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean egzxx-1a4fe21-pb "DEVSECOPS Talks #92 - From System Initiative to SWAMP: Agent-Native Infra with Paul Stack"  >}} 

---

<!-- Video -->

{{< youtube XTM__-Ai4Zw >}}

## Summary

System Initiative has undergone a dramatic transformation: from a visual SaaS infrastructure platform with 17 employees to **Swamp**, a fully open-source CLI built for AI agents, maintained by a five-person team whose initials literally spell the product name. Paul Stack returns for his third appearance on the show to explain why the old model failed — and why handing an AI agent raw CLI access to your cloud is, as Andrey puts it, just "console-clicking in the terminal." The conversation gets sharp when the hosts push on what problem Swamp actually solves, whether ops teams are becoming the next bottleneck in AI-era delivery, and why Paul believes the right move is not replacing Terraform but giving AI a structured system it can reason about. Paul also drops a parting bombshell: he hasn't written a single line of code in four weeks.

## Key Topics

### System Initiative's pivot from visual editor to AI-first CLI

Paul Stack explains that System Initiative spent over five years iterating on a visual infrastructure tool where users could drag, drop, and connect systems. Despite the ambition, the team eventually concluded that visual composition was too slow, too cumbersome, and too alien for practitioners accustomed to code, artifacts, and reviewable changes.

The shift started in summer 2025 when Paul spiked a public OpenAPI-spec API. A customer then built an early MCP (Model Context Protocol) server on top of it — a prototype that worked but had no thought given to token usage or tool abstraction. System Initiative responded by building its own official MCP server and pairing it with a CLI. The results were dramatically better: customers could iterate easily from the command line or through AI coding tools like Claude Code.

By Christmas 2025 the writing was on the wall. The CLI-plus-agent approach was producing better outcomes, while the company was still carrying hundreds of thousands of lines of code for a distributed SaaS platform built for a previous product direction. In mid-January 2026, the company made the call to rethink everything from first principles.

### The team behind the name

The restructuring was painful. System Initiative went from 17 people to five. Paul explains the reasoning candidly: when you don't know what the tool is going to be, keeping a large team around is unfair to them, bad for their careers, and expensive. The five who stayed were the CEO, VP of Business, COO, Paul (who ran product), and Nick Steinmetz, the head of infrastructure — who also happened to be System Initiative's most active internal user, having used the platform to build System Initiative itself.

Those five people's initials spell **SWAMP**. The name was unintentional but stuck — and Paul notes with a grin that if they ever remove the "P," it becomes "SWAM," so he's safe even if he leaves. Beyond the joke, the name fits: Swamp stores operational data in a local `.swamp/` directory — not a neatly formatted data lake, but a structured store that AI agents can pull from to reason about infrastructure state and history.

### Why raw AI agent access to infrastructure is dangerous

A major theme in the conversation is that letting an AI agent operate infrastructure directly — through the AWS CLI or raw API calls — is fundamentally unreliable. Andrey lays out the problem clearly: this kind of interaction is equivalent to clicking around the cloud console, just automated through a terminal. It is not repeatable, not reviewable, and inherits the non-deterministic behavior of LLMs. If the agent's context window fills up, it starts to forget earlier decisions and improvises — a terrifying prospect for production infrastructure.

What made System Initiative's earlier MCP-based direction compelling, in Andrey's view, was the combination of **guardrails, repeatability, and human review**. The agent generates a structured specification, a human reviews it, and only then is it applied. Paul agrees and calls this the "agentic loop with the human loop" — the strongest pattern they found.

### Token costs and the case for local-first architecture

Paul shares a hard-won lesson from building MCP integrations: a poorly designed MCP server burns enormous amounts of tokens and creates unnecessary costs for users. He spent three weeks in December reworking the server to use progressive context reveal rather than flooding the model with data. Even so, the fundamental problem with a SaaS-first architecture remained — constantly transmitting context between a central API and the user's agent was expensive regardless of optimization.

That experience pushed the team toward a local-first design. Swamp keeps data on the user's machine, close to where the agent operates, giving AI the context it needs without the round-trip overhead and cost of a remote service.

### What Swamp actually is

Swamp is a **general-purpose, open-source CLI automation tool** — not just another infrastructure-as-code framework. Its core building blocks are:

- **Models**: typed schemas with explicit inputs, outputs, and methods. Unlike traditional IaC resource definitions limited to CRUD operations, Swamp models can have methods like `analyze` or `do_next`, with the procedural logic living inside the method itself.
- **Workflows**: the orchestration layer that interacts with APIs, CLIs, or any external system. Workflows take inputs, can be composed (a workflow can orchestrate other workflows), and produce artifacts that the AI agent can inspect over time.
- **Skills**: Claude Code markdown files and shell scripts that teach the AI agent how to build models and workflows within Swamp's architecture.

Critically, Swamp ships with **zero built-in models** — no pre-packaged AWS EC2, VPC, or GCP resource definitions. Instead, the AI agent uses installed skills to generate models on the fly. Paul describes a user who joined the Discord that very morning, asked Swamp to create a schema for managing Let's Encrypt certificates, and it worked on the first attempt without writing any code.

Nick Steinmetz provides another example: he manages his homelab Proxmox hypervisor entirely through Swamp — creating and starting VMs, inspecting hypervisor state, and monitoring utilization. He recently connected it to Discord so friends can run commands like `@swamp create vm` to spin up Minecraft and gaming servers on demand.

### How Swamp fits with AI coding tools

The hosts spend significant time pinning down where Swamp sits relative to tools like Claude Code, bash access, and existing automation. Paul is clear: Swamp is **not** an AI wrapper or chatbot. It is a structured runtime that gives agents guardrails and reusable patterns.

Mattias works through several analogies to help frame it — is it like n8n or Zapier for the CLI? A CLI-based Jenkins where jobs are agents? Paul settles on this: it is a workflow engine driven by typed models, where data can be chained between steps using [CEL (Common Expression Language)](https://cel.dev/) expressions — the same dot-notation referencing used in Kubernetes API declarations. A simple example: create a VPC in step one, then reference `VPC.resource.attributes.vpcid` as input to a subnet model in step two.

In Paul's personal workflow, he uses Claude Code to generate models and workflows, checks them into Git for peer review, and then runs them manually or through CI at a time of his choosing. He has explicitly configured Claude with a permission deny on `workflow run` — the agent helps build automation but never executes it. The same CLI works whether a person or an agent runs it; the difference is timing and approval.

### Reusability, composition, and Terraform interop

Swamp workflows are parameterized and reusable across environments. If they grow unwieldy, workflows can orchestrate other workflows, collect outputs, and manage success conditions — similar to GitHub Actions calling other actions.

Paul also demonstrates that Swamp can sit alongside existing tooling rather than replacing it. In a live Discord session, he built infrastructure models in Swamp and then asked the AI agent to generate the equivalent Terraform configuration. Because the agent had typed models with explicit relationships, it produced correct Terraform with proper resource dependencies. This positions Swamp less as a replacement mandate and more as a reasoning and control layer that can output to whatever format teams already use.

When one of the hosts compares Swamp to general build systems like Gradle, Paul draws a key distinction: traditional tools were designed for humans to write, review, and debate. Swamp is designed for AI agents to inspect and operate within. He references Anton Babenko's widely-used `terraform-aws-vpc` module — with its 237+ input variables — as an example of a human-centric design that agents struggle with due to version dependencies, module structure complexity, and stylistic decisions baked in over years. Swamp instead provides the agent with structured context, explicit typing, and historical artifacts it can query.

### Open source, AGPL v3, and monetization

Paulina asks the natural question: if Swamp is fully open source under AGPL v3, how does the company make money?

Paul is candid that monetization is not the immediate priority — the focus is building a tool that resonates with users first. But he outlines a potential model: a marketplace-style ecosystem where users can publish their own models and workflows, while System Initiative offers supported, maintained, and paid-for versions of commonly needed building blocks. He draws a loose comparison to Docker Hub's model of community images alongside official ones.

The deeper argument is strategic: Paul believes there is **no longer a durable moat in software**. If users dislike a tool today, AI makes it increasingly feasible to build their own. Rather than trying to control all schemas and code, the team wants to make Swamp so extensible that users build on top of it rather than walking away from it.

### Are ops teams becoming the next bottleneck?

Paul argues that software development productivity is accelerating so fast with AI that ops teams risk becoming the next bottleneck — echoing earlier industry transitions from physical servers to cloud and from manual provisioning to infrastructure as code. Development teams can now move at a pace that traditional infrastructure workflows cannot match.

Andrey agrees with the premise but pushes back on where the bottleneck actually sits today. In his experience — spending "day and night burning tokens" on AI-assisted development — the real constraint is **testing**, not deployment. He describes pipelines that can go from idea to pull request automatically, but stall without a strong test harness and end-to-end validation. Without sufficient tests, you never even reach the deployment phase.

Paul accepts the framing and says the goal of Swamp is to strip away lower-value friction — fighting with file layouts, naming conventions, writing boilerplate models — so teams can invest their time where engineering rigor still matters most: testing, validation, and production safety.

### Swamp as an addition, not a forced replacement

Paul closes with an important positioning point: Swamp does not require teams to discard their Terraform, Pulumi, or existing infrastructure investments. It can be introduced alongside current tooling to interrogate infrastructure, validate what existing IaC does, and extend automation in AI-native ways. The extensibility is the point — users control when things run, what models to build, and how to integrate with their existing stack.

## Highlights

### "Giving an agent raw CLI access to your cloud is basically console-clicking in the terminal." — Andrey

Andrey challenges the assumption that AI-driven infrastructure is automatically safer. If an agent is just shelling out to the AWS CLI, the result may be fast — but it is non-deterministic, non-repeatable, and forget-prone once the context window fills up.

The future of infra automation needs guardrails before it needs speed. Listen to hear why structured workflows beat flashy demos.

### "The best loop was the agentic loop with the human loop." — Paul Stack

The breakthrough was not autonomous infrastructure execution. It was letting the AI generate structured specs while humans stay in charge of review and execution. Paul even blocks Claude Code from running workflows directly on his machine.

If "human in the loop" sounds conservative, this episode makes the case that it is the only production-safe pattern we have. Listen for the full argument.

### "There is no longer a moat in software." — Paul Stack

Paul argues that AI has changed the economics of building software so fundamentally that no team can rely on implementation complexity as a competitive advantage. If users dislike your tool, they can build their own — faster than ever before.

That belief is why Swamp is open source, extensible, and ships with zero built-in models. Listen for a candid take on product strategy when anyone can clone your work.

### "Ops teams are going to become the bottlenecks that we once were." — Paul Stack

As development velocity explodes with AI, Paul warns that infrastructure teams risk slowing everything down — the same pattern that played out in the shifts from physical servers to cloud and from cloud to IaC.

Andrey fires back: the real bottleneck today is testing, not deployment. Listen for a sharp debate on where delivery pipelines are actually stuck.

### "I haven't written a single line of code in four weeks." — Paul Stack

Paul reveals that the entire Swamp repository is AI-generated, with four machines running in parallel to churn out plans and implementations — including customer feature requests. The team teases a future episode to compare notes on AI-driven development workflows.

If that claim doesn't make you want to hear the follow-up, nothing will.

## Resources

- **[Swamp CLI on GitHub](https://github.com/systeminit/swamp)** — The open-source, AGPL v3 licensed CLI tool discussed in the episode. Models, workflows, and a local `.swamp/` data directory designed for AI agent interaction.

- **[System Initiative](https://www.systeminit.com/)** — The company behind Swamp, originally known for its visual infrastructure platform, now pivoted to AI-native CLI automation.

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** — Anthropic's open protocol for connecting AI models to external tools and data sources. Paul discusses the challenges of building MCP servers that are token-efficient.

- **[Claude Code](https://claude.ai/download)** — Anthropic's agentic coding tool that runs in the terminal. Used throughout the episode as the primary AI agent interface for Swamp workflows.

- **[CEL — Common Expression Language](https://cel.dev/)** — The expression language Swamp uses for chaining data between workflow steps, similar to how Kubernetes uses it for API declarations and validation policies.

- **[Proxmox Virtual Environment](https://www.proxmox.com/)** — The open-source hypervisor platform that Nick Steinmetz manages entirely through Swamp in his homelab, including Discord-driven VM creation.

- **[terraform-aws-modules/vpc](https://github.com/terraform-aws-modules/terraform-aws-vpc)** — Anton Babenko's widely-used Terraform VPC module, referenced by Paul as an example of human-centric IaC design with 237+ inputs that agents struggle to navigate.
