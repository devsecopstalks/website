---
title: "#94 - Small Tasks, Big Wins: The AI Dev Loop at System Initiative"
date: 2026-03-11T23:16:24+00:00
lastmod: 2026-03-11T23:16:24+00:00
episode: 94
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
---

We bring Paul Stack back to cover the parts we skipped last time. What changed when the models got better and we moved from one-shot Gen AI to agentic, human-in-the-loop work? How do plan mode and tight prompts stop AI from going rogue? Want to hear how six branches, git worktrees, and a TypeScript CLI came together?

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean xnuqq-1a6b211-pb "DEVSECOPS Talks #94 - Small Tasks, Big Wins: The AI Dev Loop at System Initiative"  >}} 

---

<!-- Video -->

{{< youtube R6DExMI8iVw >}}

## Summary

In this episode, Mattias, Andrey, and Paulina welcome back returning guest Paul from System Initiative to continue a conversation that started in the previous episode about their project Swamp. The discussion digs into how AI-assisted software development has changed over the past year, and why the real shift is not "AI writes code" but humans orchestrating multiple specialized agents with strong guardrails. Paul walks through the practical workflows, multi-layered testing, architecture-first thinking, cost discipline, and security practices his team has adopted — while the hosts push on how this applies across enterprise environments, mentoring newcomers, and the uncomfortable question of who is responsible when AI-built software fails.

## Key Topics

### The industry crossroads: layoffs, fear, and a new reality

Before diving into technical specifics, Paul acknowledges that the industry is at "a real crazy crossroads." He references Block (formerly Square) cutting roughly 40% of their workforce, citing uncertainty about what AI means for their teams. He wants to be transparent that System Initiative also shrank — but clarifies the company did not cut people because of AI. The decision to reduce headcount came before they even knew what they were going to build next, let alone how they would build it. AI entered the picture only after they started prototyping the next version of their product.

> Block's February 2026 layoffs, announced by CEO Jack Dorsey, eliminated over 4,000 positions. The move was framed as an AI-driven restructuring, making it one of the most visible examples of AI anxiety playing out in real corporate decisions.

### From GenAI hype to agentic collaboration

Paul explains that AI coding quality shifted significantly around October–November of the previous year. Before that, results were inconsistent — sometimes impressive, often garbage. Then the models improved dramatically in both reasoning and code generation.

But the bigger breakthrough, in his view, was not the models themselves. It was the industry's shift from "Gen AI" — one-shot prompting where you hand over a spec and accept whatever comes back — to **agentic AI**, where the model acts more like a pair programmer. In that setup, the human stays in the loop, challenges the plan, adds constraints, and steers the result toward something that fits the codebase.

He gives a concrete early example: System Initiative had a CLI written in **Deno** (a TypeScript runtime). Because the models were well-trained on TypeScript libraries and the Deno ecosystem, they started producing decent code. Not beautiful, not perfectly architected — but functional. When Paul began feeding the agent patterns, conventions, and existing code to follow, the output became coherent with their codebase.

This led to a workflow where Paul would open six Claude Code sessions at once in separate **Git worktrees** — isolated copies of the repository on different branches — each building a small feature in parallel, feeding them bug reports and data, and continuously interacting with the results rather than one-shotting them.

> **Git worktrees** let you check out multiple branches of the same repository simultaneously in separate directories. Each worktree is independent, so you can work on several features at once and merge them back via pull requests.

He later expanded this by running longer tasks on a **Mac Mini** accessible via **Tailscale** (a mesh VPN), while handling shorter tasks on his laptop — effectively distributing AI workloads across machines.

### Why architecture matters more than ever

One of Paul's strongest themes is that AI shifts engineering attention away from syntax and back toward architecture. He argues that AI can generate plenty of code, but without design principles and boundaries it will produce spaghetti on top of existing spaghetti.

He introduces the idea of "the first thousand lines" — an anecdote he read recently claiming that the first thousand lines of code an agent helps write determine its path forward. If those lines are well-structured and follow clear design principles, the agent will build coherently on top of them. If they are messy and unprincipled, everything after will compound the mess.

Paul breaks software development into three layers:

1. **Architecture** — design patterns like DDD (Domain-Driven Design), CQRS (Command Query Responsibility Segregation)
2. **Patterns** — principles like DRY (Don't Repeat Yourself), YAGNI (You Aren't Gonna Need It), KISS (Keep It Simple)
3. **Taste** — naming conventions, module layout, project structure, Terraform module organization

He argues the industry spent the last decade obsessing over "taste" while often mocking **"ivory tower architects"** — the people who designed systems but didn't write code. In an AI-driven world, those architectural concerns become critical again because the agent needs clear boundaries, domain structure, and intent to produce coherent output.

Paulina agrees and observes that this trend may also blur traditional specialization lines, pushing engineers toward becoming more general "software people" rather than narrowly front-end, back-end, or DevOps specialists.

### Encoding design docs, rules, and constraints into the repo

Paul describes how his team makes architecture actionable for AI by encoding system knowledge directly into the repository. Their approach has several layers:

**Design documents** — Detailed docs covering the model layer (the actual objects, their purposes, how they relate), workflow construction (how models connect and pass data), and expression language behavior. These live in a `/design` folder in the open-source repo and describe the intent of every part of the system.

**Architectural rules** — The agent is explicitly told to follow Domain-Driven Design: proper separation between domains, infrastructure, repositories, and output layers. The DDD skill is loaded so the agent understands and maintains bounded contexts.

**Code standards** — TypeScript strict mode, no `any` types, named exports, passing lint and format checks. License compliance is also enforced: because the project is **AGPL v3**, the agent cannot pull in dependencies with incompatible licenses.

**Skills** — A newer mechanism for **lazy-loading** contextual information into the AI agent. Rather than stuffing everything into one enormous prompt, skills are loaded on demand when the agent encounters a specific type of task. This keeps context windows lean and focused.

> **AGPL v3** (GNU Affero General Public License) is a copyleft license that requires anyone who runs modified software over a network to make the source code available. This creates strict constraints on what dependencies can be used.

### Multi-agent development: the full chain

A major part of the discussion centers on how Paul's team works with multiple specialized AI agents rather than a single all-knowing assistant. The chain looks like this:

1. **Issue triage agent** — When a user opens a GitHub issue, an agent evaluates whether it is a legitimate feature request or bug report. The agent's summary is posted back to the issue immediately, creating context for later stages.

2. **Planning agent** — If the issue is legitimate, the system enters plan mode. A specification is generated and posted for the user to review. Users can push back ("that's not how I think it should work"), and the plan is revised until everyone agrees.

3. **Implementation agent** — The code is written based on the approved plan, with all the design docs, architectural rules, and skills loaded as context.

4. **Happy-path reviewer** — A separate agent reviews the code against standards, checking that it loads correctly and appears to function.

5. **Adversarial reviewer** — Added just days before the recording, this agent is told: *"You are a grumpy DevOps engineer and I want you to pull this code apart."* It looks for security injection points, failure modes, and anything the happy-path reviewer might miss.

Both review agents write their findings as comments on the pull request, creating a visible audit trail. The PR only merges when both agents approve. If the adversarial agent flags a security vulnerability, the implementation goes back for changes.

Paul says this "Jekyll and Hyde" review setup caught a **path traversal bug** in their CLI during its first week. While the CLI runs locally and the risk was limited, it proved the value of adversarial review.

> **Path traversal** is a vulnerability where an attacker can access files outside the intended directory by manipulating file paths (e.g., using `../` sequences). Even in CLI tools, this can expose sensitive files on a user's machine.

Mattias compares the overall process to a modernized CI/CD pipeline — the same stages exist (commit, test, review, promote, release), but AI replaces some of the manual implementation steps while humans stay focused on architecture, review, and acceptance.

### Why external pull requests are disabled

One of the more provocative decisions Paul describes: the open-source Swamp project **does not accept external pull requests**. GitHub recently added a feature to disable PR creation from non-collaborators entirely, and the team turned it on immediately.

The reasoning is supply chain control. Because the project's code is 100% AI-generated within a tightly controlled context — design docs, architectural rules, skills, adversarial review — they want to ensure that all code entering the system passes through the same pipeline. External PRs would bypass that chain of custody.

Contributors are instead directed to open issues. The team will work through the design collaboratively, plan it together, and then have their agents implement it. Paul frames this not as rejecting collaboration but as controlling the process: "We love contributions, but in the AI world, we cannot control where that code is from or what that code is doing."

### Self-reporting bugs: AI filing its own issues

The team built a skill into Swamp itself so that when the tool encounters a bug during use, it can check out the version of the source code the binary was built against, analyze the problem, and **open a GitHub issue automatically** with detailed context.

This creates high-quality bug reports that already contain the information needed to reason about a fix. When the implementation agent later picks up that issue, it has precise context — where the bug is, what triggered it, and what the expected behavior should be. Paul says the quality of issues generated this way is significantly higher than typical user-filed bugs.

### Testing: the favorite part

Although the conversation starts with code generation, Paul says testing is actually his favorite part of the workflow. The team runs multiple layers:

**Product-level tests:**
- **Unit and integration tests** — standard code-level verification
- **Architectural fitness tests** — contract tests, property tests, and DDD boundary checks that verify the domain doesn't leak and the agent followed its instructions

> **Architectural fitness tests** are automated checks that verify a system's structure conforms to its intended architecture. In DDD, this means ensuring bounded contexts don't leak dependencies across domain boundaries.

**User-level tests** (separate repo):
- **User flow tests** — written from the user's perspective against compiled binaries, not source code. These live in a different repository specifically so they are not influenced by how the code is written. They test scenarios like: create a repository, extend the system, create a workflow, run a model, handle wrong inputs.

**Adversarial tests** (multiple tiers):
1. **Security boundary tests** — path traversal, environment variable exposure, supply chain attack vectors. Paul references the recent Trivy incident, where a bot stole an API key and used it to delete all of Trivy's GitHub releases and publish a poisoned VS Code extension.
2. **State corruption** — what happens when someone tampers with the state layer
3. **Concurrency** — multiple writes, lock failures, race conditions
4. **Resource exhaustion** — handling pathological inputs like a 100MB stdout message injected into a workflow

Only after all these layers pass does a build get promoted from nightly to stable. Paul can download and manually test any nightly build that maps back to a specific commit.

Paulina points out that if AI is a force multiplier, there is now even less excuse not to write tests. Paul agrees: "We were scraping the barrel before at coming up with reasons why there shouldn't be any tests. Now that's eliminated."

### Plan mode as a safety rail

Paul repeatedly emphasizes "plan mode," particularly in Claude Code. Before the agent changes anything, it produces a detailed plan describing what it intends to do and why, and waits for human approval.

The hosts immediately draw a parallel to `terraform plan` — the value is not just automation, but the chance to inspect intended changes before applying them. Paul says this was one of the biggest improvements in AI-assisted development because it reduces horror-story scenarios where an agent goes off and deletes a database or rewrites an application.

He notes that other tools are starting to adopt plan mode because it produces better results across the board. But he also warns that plan mode only helps if people actually read the plan — just like Terraform, the safeguard depends on human discipline. "If there's a big line in the middle that says 'I'm going to delete a database' and you haven't read it — it's the same thing."

### Practical lessons for getting good results

Paul shares several tactical lessons:

- **Don't give mega-prompts** — "Don't write 'rebuild me Slack' and expect an AI agent to do it. You'd be shocked at the amount of people who try this."
- **Always provide design docs** — Specifications produce dramatically better output than vague instructions.
- **Don't skip straight to code** — Start with design and planning, not "code me this method."
- **Small tasks** — Don't attempt project-wide rewrites with a single agent. Context loss is the new "restart your machine."
- **Never trust the first plan** — Paul routinely asks the agent: "Are you sure this is the right plan? Explain it to me like a five-year-old. Does this fulfill what the user needed?"
- **Compare implementation to plan** — After implementation, ask the agent to map what it actually did against the original plan and explain any deviations.

He also notes that the generated TypeScript is not always how a human would write it — but that matters less if the result is well-tested, secure, and respects domain boundaries. "The actual syntax of the code itself can change 12 times a day. It doesn't really matter as long as it adheres to the product."

### Human oversight at every stage

Despite all the automation, Paul is adamant that humans remain involved at every stage. Plans are reviewed, implementations are questioned, pull request comments are inspected, binaries are tested before reaching stable release. He describes it as "continually interacting with Claude Code" rather than just letting things happen.

When Paulina pushes on whether a human still checks things before production, Paul makes clear: yes, always. The release pipeline goes from commit to nightly to manual verification to stable promotion. "I will always download something before it goes to stable."

### The context-switching tax

Paul acknowledges that running multiple agents in parallel is not for everyone. Context switching has always been expensive for engineers, and commanding multiple agents simultaneously is a new form of it. His advice: if you work best focusing on a single task, don't force the multi-agent style. "It'll be such a context switching killer and it'll cause you to lose focus."

The key shift is that instead of writing code, you are "commanding architecture and commanding design." But that still requires focus and judgment.

### AI as a force multiplier, not a replacement

Paulina captures the dynamic bluntly: "It's a multiplier. If there is a good thing, you'll get a lot of good thing. If it's a shit, you're going to get a lot of shit."

Paul argues that experienced software and operations people are still essential because they understand architecture, security, constraints, and tradeoffs. AI amplifies whatever is already there — good engineering or bad engineering alike.

He believes engineers who learn to use these tools well become "even more important to your company than you already are." But he also acknowledges that some people will not want to work this way, and that friction between AI-forward and AI-resistant teams is already happening in organizations.

### The challenge for juniors and newcomers

Paulina raises this personally — she was recently asked to mentor someone entering IT and struggled with how to approach it. She doesn't have a formal IT education (she has an engineering background) and learned on the go. The skills she built through manual work — understanding when code needs refactoring as scale changes, knowing how to structure projects at different sizes — are hard to teach when AI handles so much of the writing.

Paul agrees this is an open question and says the industry is still figuring out the patterns. He believes teaching **principles, architecture, and core engineering fundamentals** becomes even more important, because tool-specific syntax is increasingly handled by AI. "Do you need to know how to write a Terraform module? Do you need to know how to write a Pulumi provider?" — these are becoming less essential as individual skills, while understanding how systems fit together matters more.

He frames this as an opportunity: "We are now in control of helping shape how this moves forward in the industry." As innovators and early adopters, current practitioners can set the patterns. If they don't, someone else will.

### Security, responsibility, and the risk of low-code AI

Paulina raises a concrete example from Poland: someone built an app using AI to upload receipts to a centralized accounting system, released it publicly, and exposed all their customers' data.

This leads to a deeper question from Mattias about responsibility: if someone with no engineering background builds an insecure app using an AI tool, who is accountable? The user? The platform? The model provider? The episode doesn't settle this, but Paul argues it reinforces why skilled engineers remain essential. The AI doesn't know the security boundary unless someone explicitly teaches it — "it probably wasn't fed that information that it had to think about the security context."

He expects more specialized skills and agents focused on security, accessibility, and compliance to emerge — calling out the example of loading a security skill and an accessibility skill when you know an app will be public-facing. But he says the ecosystem is not fully there yet.

### Cost discipline: structure beats vibe coding

Paul addresses economics directly. His five-person team at System Initiative all use **Claude Max Pro** at $200 per person per month. They do not exceed that cost for the full AI workflow — code generation, reviews, planning, and adversarial testing.

In contrast, he has seen other organizations spend $10,000–$12,000 per month per developer on AI tokens because they let tools roam with huge context windows and vague instructions. His conclusion: tightly scoped tasks are not just better for quality — they are far cheaper.

This maps directly to classic engineering wisdom. Tightly defined stories and tasks were always more efficient to push through a system than "go rebuild this thing and I'll see you in six months." The same principle applies to AI agents.

### How to introduce AI in cautious organizations

For teams in companies that ban or restrict AI, Paul suggests a pragmatic entry point: **use agents to analyze, not to write code.**

He describes a conversation with someone in London who asked how to get started. Paul's advice: if you already know roughly where a bug lives, ask the agent to analyze the same bug report. If it identifies the same area and the same root cause, you have evidence that the tool can accelerate diagnosis. Show your CTO: "I'm diagnosing bugs 50% faster with this agent. It's not writing code — it's helping me understand where the issue is."

Similar analysis-first use cases work for accessibility reviews, security scans, or code quality assessments. The point is to build trust before expanding scope. Paul notes this approach works faster in the private sector than the public sector, where technology adoption has always been slower.

### The pace of change is accelerating

Paul believes the conversation has shifted dramatically in the past six months — from AI horror stories and commiserating over drinks to genuine success stories and conferences forming around agentic engineering practices. He points to two upcoming events:

- An **Agentic conference in Stockholm** organized by Robert Westin, who Paulina mentions meeting just the day before
- **Agentic Conf in Hamburg** at the end of March

His prediction: the pace is not linear. "We're honestly exponential at this moment in time." He sidesteps the ethics of AI companies (referencing tensions between Anthropic and OpenAI) to focus on the practical reality that models, reasoning, and tooling are all improving at a compounding rate.

## Highlights

- **Paul on the industry mood:** "We're at this real crazy crossroads in the industry."
- **Paul on model quality:** Around late last year, "the models got really good, like really, really good. Really, really, really incredible."
- **Paul on running six agents at once:** "I had my terminal open. I had six Claude Codes going at once, building like six different small features at a time."
- **Paulina's blunt summary:** "It's a multiplier. If there is a good thing, you'll get a lot of good thing. If it's a shit, you're going to get a lot of shit."
- **Paul's spicy take on architecture:** The industry spent years mocking "ivory tower architects," but now AI is pushing engineers back into "the architecture lab."
- **Paul on plan mode:** It is the AI equivalent of `terraform plan` — useful, but only if people actually read it.
- **Paul's unusual open-source policy:** External pull requests are disabled entirely so the team can control the supply chain.
- **Most memorable workflow detail:** Paul's adversarial reviewer is instructed, "You are a grumpy DevOps engineer and I want you to pull this code apart."
- **Practical win:** That grumpy reviewer caught a path traversal bug in its first week.
- **Paul on testing excuses:** "We were scraping the barrel before at coming up with reasons why there shouldn't be any tests. Now that's eliminated."
- **Paul's warning against mega-prompts:** Asking an agent to "rebuild me Slack" with no context is a great way to conclude, incorrectly, that "AI is garbage."
- **Paul on context loss:** "Compact your conversation" is the new "restart your machine."
- **Paul on cost:** Five people, $200/month each, covering the full AI workflow — versus orgs spending $10K+ per developer per month on unfocused vibe coding.
- **Paul on adoption strategy:** Start by letting AI analyze bugs and accessibility issues — build trust before asking it to write code.

## Resources

- [Claude Code Documentation — Common Workflows](https://code.claude.com/docs/en/common-workflows) — Official Anthropic docs covering plan mode, extended thinking, and agentic workflows in Claude Code.
- [Anthropic Skills Repository](https://github.com/anthropics/skills) — Public repository of modular Markdown-based skill packages that extend Claude's capabilities for specialized tasks like security review or accessibility checking.
- [System Initiative on GitHub](https://github.com/systeminit/si) — The open-source repository for System Initiative's infrastructure automation platform, including the design documents Paul references.
- [Git Worktree Documentation](https://git-scm.com/docs/git-worktree) — Official docs for `git worktree`, the feature that enables Paul's multi-branch parallel development workflow.
- [Trivy Supply Chain Attack Analysis (Socket)](https://socket.dev/blog/unauthorized-ai-agent-execution-code-published-to-openvsx-in-aqua-trivy-vs-code-extension) — Detailed writeup of the incident Paul references where a bot stole credentials, deleted GitHub releases, and published a poisoned VS Code extension.
- [Building Evolutionary Architectures — Fitness Functions](https://evolutionaryarchitecture.com/) — The book and concepts behind architectural fitness tests that Paul's team uses to verify DDD boundaries and prevent domain leakage.
- [GitHub: New Repository Settings for Pull Request Access](https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/) — The GitHub feature Paul mentions for disabling external pull requests at the repository level.

## Summary

In this episode, Mattias, Andre, and Paulina welcome back returning guest Paul from System Initiative to continue a conversation that started in the previous episode about their project Swamp. The discussion digs into how AI-assisted software development has changed over the past year, and why the real shift is not "AI writes code" but humans orchestrating multiple specialized agents with strong guardrails. Paul walks through the practical workflows, multi-layered testing, architecture-first thinking, cost discipline, and security practices his team has adopted — while the hosts push on how this applies across enterprise environments, mentoring newcomers, and the uncomfortable question of who is responsible when AI-built software fails.

## Key Topics

### The industry crossroads: layoffs, fear, and a new reality

Before diving into technical specifics, Paul acknowledges that the industry is at "a real crazy crossroads." He references Block (formerly Square) cutting roughly 40% of their workforce, citing uncertainty about what AI means for their teams. He wants to be transparent that System Initiative also shrank — but clarifies the company did not cut people because of AI. The decision to reduce headcount came before they even knew what they were going to build next, let alone how they would build it. AI entered the picture only after they started prototyping the next version of their product.

> Block's February 2026 layoffs, announced by CEO Jack Dorsey, eliminated over 4,000 positions. The move was framed as an AI-driven restructuring, making it one of the most visible examples of AI anxiety playing out in real corporate decisions.

### From GenAI hype to agentic collaboration

Paul explains that AI coding quality shifted significantly around October–November of the previous year. Before that, results were inconsistent — sometimes impressive, often garbage. Then the models improved dramatically in both reasoning and code generation.

But the bigger breakthrough, in his view, was not the models themselves. It was the industry's shift from "Gen AI" — one-shot prompting where you hand over a spec and accept whatever comes back — to **agentic AI**, where the model acts more like a pair programmer. In that setup, the human stays in the loop, challenges the plan, adds constraints, and steers the result toward something that fits the codebase.

He gives a concrete early example: System Initiative had a CLI written in **Deno** (a TypeScript runtime). Because the models were well-trained on TypeScript libraries and the Deno ecosystem, they started producing decent code. Not beautiful, not perfectly architected — but functional. When Paul began feeding the agent patterns, conventions, and existing code to follow, the output became coherent with their codebase.

This led to a workflow where Paul would open six Claude Code sessions at once in separate **Git worktrees** — isolated copies of the repository on different branches — each building a small feature in parallel, feeding them bug reports and data, and continuously interacting with the results rather than one-shotting them.

> **Git worktrees** let you check out multiple branches of the same repository simultaneously in separate directories. Each worktree is independent, so you can work on several features at once and merge them back via pull requests.

He later expanded this by running longer tasks on a **Mac Mini** accessible via **Tailscale** (a mesh VPN), while handling shorter tasks on his laptop — effectively distributing AI workloads across machines.

### Why architecture matters more than ever

One of Paul's strongest themes is that AI shifts engineering attention away from syntax and back toward architecture. He argues that AI can generate plenty of code, but without design principles and boundaries it will produce spaghetti on top of existing spaghetti.

He introduces the idea of "the first thousand lines" — an anecdote he read recently claiming that the first thousand lines of code an agent helps write determine its path forward. If those lines are well-structured and follow clear design principles, the agent will build coherently on top of them. If they are messy and unprincipled, everything after will compound the mess.

Paul breaks software development into three layers:

1. **Architecture** — design patterns like DDD (Domain-Driven Design), CQRS (Command Query Responsibility Segregation)
2. **Patterns** — principles like DRY (Don't Repeat Yourself), YAGNI (You Aren't Gonna Need It), KISS (Keep It Simple)
3. **Taste** — naming conventions, module layout, project structure, Terraform module organization

He argues the industry spent the last decade obsessing over "taste" while often mocking **"ivory tower architects"** — the people who designed systems but didn't write code. In an AI-driven world, those architectural concerns become critical again because the agent needs clear boundaries, domain structure, and intent to produce coherent output.

Paulina agrees and observes that this trend may also blur traditional specialization lines, pushing engineers toward becoming more general "software people" rather than narrowly front-end, back-end, or DevOps specialists.

### Encoding design docs, rules, and constraints into the repo

Paul describes how his team makes architecture actionable for AI by encoding system knowledge directly into the repository. Their approach has several layers:

**Design documents** — Detailed docs covering the model layer (the actual objects, their purposes, how they relate), workflow construction (how models connect and pass data), and expression language behavior. These live in a `/design` folder in the open-source repo and describe the intent of every part of the system.

**Architectural rules** — The agent is explicitly told to follow Domain-Driven Design: proper separation between domains, infrastructure, repositories, and output layers. The DDD skill is loaded so the agent understands and maintains bounded contexts.

**Code standards** — TypeScript strict mode, no `any` types, named exports, passing lint and format checks. License compliance is also enforced: because the project is **AGPL v3**, the agent cannot pull in dependencies with incompatible licenses.

**Skills** — A newer mechanism for **lazy-loading** contextual information into the AI agent. Rather than stuffing everything into one enormous prompt, skills are loaded on demand when the agent encounters a specific type of task. This keeps context windows lean and focused.

> **AGPL v3** (GNU Affero General Public License) is a copyleft license that requires anyone who runs modified software over a network to make the source code available. This creates strict constraints on what dependencies can be used.

### Multi-agent development: the full chain

A major part of the discussion centers on how Paul's team works with multiple specialized AI agents rather than a single all-knowing assistant. The chain looks like this:

1. **Issue triage agent** — When a user opens a GitHub issue, an agent evaluates whether it is a legitimate feature request or bug report. The agent's summary is posted back to the issue immediately, creating context for later stages.

2. **Planning agent** — If the issue is legitimate, the system enters plan mode. A specification is generated and posted for the user to review. Users can push back ("that's not how I think it should work"), and the plan is revised until everyone agrees.

3. **Implementation agent** — The code is written based on the approved plan, with all the design docs, architectural rules, and skills loaded as context.

4. **Happy-path reviewer** — A separate agent reviews the code against standards, checking that it loads correctly and appears to function.

5. **Adversarial reviewer** — Added just days before the recording, this agent is told: *"You are a grumpy DevOps engineer and I want you to pull this code apart."* It looks for security injection points, failure modes, and anything the happy-path reviewer might miss.

Both review agents write their findings as comments on the pull request, creating a visible audit trail. The PR only merges when both agents approve. If the adversarial agent flags a security vulnerability, the implementation goes back for changes.

Paul says this "Jekyll and Hyde" review setup caught a **path traversal bug** in their CLI during its first week. While the CLI runs locally and the risk was limited, it proved the value of adversarial review.

> **Path traversal** is a vulnerability where an attacker can access files outside the intended directory by manipulating file paths (e.g., using `../` sequences). Even in CLI tools, this can expose sensitive files on a user's machine.

Mattias compares the overall process to a modernized CI/CD pipeline — the same stages exist (commit, test, review, promote, release), but AI replaces some of the manual implementation steps while humans stay focused on architecture, review, and acceptance.

### Why external pull requests are disabled

One of the more provocative decisions Paul describes: the open-source Swamp project **does not accept external pull requests**. GitHub recently added a feature to disable PR creation from non-collaborators entirely, and the team turned it on immediately.

The reasoning is supply chain control. Because the project's code is 100% AI-generated within a tightly controlled context — design docs, architectural rules, skills, adversarial review — they want to ensure that all code entering the system passes through the same pipeline. External PRs would bypass that chain of custody.

Contributors are instead directed to open issues. The team will work through the design collaboratively, plan it together, and then have their agents implement it. Paul frames this not as rejecting collaboration but as controlling the process: "We love contributions, but in the AI world, we cannot control where that code is from or what that code is doing."

### Self-reporting bugs: AI filing its own issues

The team built a skill into Swamp itself so that when the tool encounters a bug during use, it can check out the version of the source code the binary was built against, analyze the problem, and **open a GitHub issue automatically** with detailed context.

This creates high-quality bug reports that already contain the information needed to reason about a fix. When the implementation agent later picks up that issue, it has precise context — where the bug is, what triggered it, and what the expected behavior should be. Paul says the quality of issues generated this way is significantly higher than typical user-filed bugs.

### Testing: the favorite part

Although the conversation starts with code generation, Paul says testing is actually his favorite part of the workflow. The team runs multiple layers:

**Product-level tests:**
- **Unit and integration tests** — standard code-level verification
- **Architectural fitness tests** — contract tests, property tests, and DDD boundary checks that verify the domain doesn't leak and the agent followed its instructions

> **Architectural fitness tests** are automated checks that verify a system's structure conforms to its intended architecture. In DDD, this means ensuring bounded contexts don't leak dependencies across domain boundaries.

**User-level tests** (separate repo):
- **User flow tests** — written from the user's perspective against compiled binaries, not source code. These live in a different repository specifically so they are not influenced by how the code is written. They test scenarios like: create a repository, extend the system, create a workflow, run a model, handle wrong inputs.

**Adversarial tests** (multiple tiers):
1. **Security boundary tests** — path traversal, environment variable exposure, supply chain attack vectors. Paul references the recent Trivy incident, where a bot stole an API key and used it to delete all of Trivy's GitHub releases and publish a poisoned VS Code extension.
2. **State corruption** — what happens when someone tampers with the state layer
3. **Concurrency** — multiple writes, lock failures, race conditions
4. **Resource exhaustion** — handling pathological inputs like a 100MB stdout message injected into a workflow

Only after all these layers pass does a build get promoted from nightly to stable. Paul can download and manually test any nightly build that maps back to a specific commit.

Paulina points out that if AI is a force multiplier, there is now even less excuse not to write tests. Paul agrees: "We were scraping the barrel before at coming up with reasons why there shouldn't be any tests. Now that's eliminated."

### Plan mode as a safety rail

Paul repeatedly emphasizes "plan mode," particularly in Claude Code. Before the agent changes anything, it produces a detailed plan describing what it intends to do and why, and waits for human approval.

The hosts immediately draw a parallel to `terraform plan` — the value is not just automation, but the chance to inspect intended changes before applying them. Paul says this was one of the biggest improvements in AI-assisted development because it reduces horror-story scenarios where an agent goes off and deletes a database or rewrites an application.

He notes that other tools are starting to adopt plan mode because it produces better results across the board. But he also warns that plan mode only helps if people actually read the plan — just like Terraform, the safeguard depends on human discipline. "If there's a big line in the middle that says 'I'm going to delete a database' and you haven't read it — it's the same thing."

### Practical lessons for getting good results

Paul shares several tactical lessons:

- **Don't give mega-prompts** — "Don't write 'rebuild me Slack' and expect an AI agent to do it. You'd be shocked at the amount of people who try this."
- **Always provide design docs** — Specifications produce dramatically better output than vague instructions.
- **Don't skip straight to code** — Start with design and planning, not "code me this method."
- **Small tasks** — Don't attempt project-wide rewrites with a single agent. Context loss is the new "restart your machine."
- **Never trust the first plan** — Paul routinely asks the agent: "Are you sure this is the right plan? Explain it to me like a five-year-old. Does this fulfill what the user needed?"
- **Compare implementation to plan** — After implementation, ask the agent to map what it actually did against the original plan and explain any deviations.

He also notes that the generated TypeScript is not always how a human would write it — but that matters less if the result is well-tested, secure, and respects domain boundaries. "The actual syntax of the code itself can change 12 times a day. It doesn't really matter as long as it adheres to the product."

### Human oversight at every stage

Despite all the automation, Paul is adamant that humans remain involved at every stage. Plans are reviewed, implementations are questioned, pull request comments are inspected, binaries are tested before reaching stable release. He describes it as "continually interacting with Claude Code" rather than just letting things happen.

When Paulina pushes on whether a human still checks things before production, Paul makes clear: yes, always. The release pipeline goes from commit to nightly to manual verification to stable promotion. "I will always download something before it goes to stable."

### The context-switching tax

Paul acknowledges that running multiple agents in parallel is not for everyone. Context switching has always been expensive for engineers, and commanding multiple agents simultaneously is a new form of it. His advice: if you work best focusing on a single task, don't force the multi-agent style. "It'll be such a context switching killer and it'll cause you to lose focus."

The key shift is that instead of writing code, you are "commanding architecture and commanding design." But that still requires focus and judgment.

### AI as a force multiplier, not a replacement

Paulina captures the dynamic bluntly: "It's a multiplier. If there is a good thing, you'll get a lot of good thing. If it's a shit, you're going to get a lot of shit."

Paul argues that experienced software and operations people are still essential because they understand architecture, security, constraints, and tradeoffs. AI amplifies whatever is already there — good engineering or bad engineering alike.

He believes engineers who learn to use these tools well become "even more important to your company than you already are." But he also acknowledges that some people will not want to work this way, and that friction between AI-forward and AI-resistant teams is already happening in organizations.

### The challenge for juniors and newcomers

Paulina raises this personally — she was recently asked to mentor someone entering IT and struggled with how to approach it. She doesn't have a formal IT education (she has an engineering background) and learned on the go. The skills she built through manual work — understanding when code needs refactoring as scale changes, knowing how to structure projects at different sizes — are hard to teach when AI handles so much of the writing.

Paul agrees this is an open question and says the industry is still figuring out the patterns. He believes teaching **principles, architecture, and core engineering fundamentals** becomes even more important, because tool-specific syntax is increasingly handled by AI. "Do you need to know how to write a Terraform module? Do you need to know how to write a Pulumi provider?" — these are becoming less essential as individual skills, while understanding how systems fit together matters more.

He frames this as an opportunity: "We are now in control of helping shape how this moves forward in the industry." As innovators and early adopters, current practitioners can set the patterns. If they don't, someone else will.

### Security, responsibility, and the risk of low-code AI

Paulina raises a concrete example from Poland: someone built an app using AI to upload receipts to a centralized accounting system, released it publicly, and exposed all their customers' data.

This leads to a deeper question from Mattias about responsibility: if someone with no engineering background builds an insecure app using an AI tool, who is accountable? The user? The platform? The model provider? The episode doesn't settle this, but Paul argues it reinforces why skilled engineers remain essential. The AI doesn't know the security boundary unless someone explicitly teaches it — "it probably wasn't fed that information that it had to think about the security context."

He expects more specialized skills and agents focused on security, accessibility, and compliance to emerge — calling out the example of loading a security skill and an accessibility skill when you know an app will be public-facing. But he says the ecosystem is not fully there yet.

### Cost discipline: structure beats vibe coding

Paul addresses economics directly. His five-person team at System Initiative all use **Claude Max Pro** at $200 per person per month. They do not exceed that cost for the full AI workflow — code generation, reviews, planning, and adversarial testing.

In contrast, he has seen other organizations spend $10,000–$12,000 per month per developer on AI tokens because they let tools roam with huge context windows and vague instructions. His conclusion: tightly scoped tasks are not just better for quality — they are far cheaper.

This maps directly to classic engineering wisdom. Tightly defined stories and tasks were always more efficient to push through a system than "go rebuild this thing and I'll see you in six months." The same principle applies to AI agents.

### How to introduce AI in cautious organizations

For teams in companies that ban or restrict AI, Paul suggests a pragmatic entry point: **use agents to analyze, not to write code.**

He describes a conversation with someone in London who asked how to get started. Paul's advice: if you already know roughly where a bug lives, ask the agent to analyze the same bug report. If it identifies the same area and the same root cause, you have evidence that the tool can accelerate diagnosis. Show your CTO: "I'm diagnosing bugs 50% faster with this agent. It's not writing code — it's helping me understand where the issue is."

Similar analysis-first use cases work for accessibility reviews, security scans, or code quality assessments. The point is to build trust before expanding scope. Paul notes this approach works faster in the private sector than the public sector, where technology adoption has always been slower.

### The pace of change is accelerating

Paul believes the conversation has shifted dramatically in the past six months — from AI horror stories and commiserating over drinks to genuine success stories and conferences forming around agentic engineering practices. He points to two upcoming events:

- An **Agentic conference in Stockholm** organized by Robert Westin, who Paulina mentions meeting just the day before
- **Agentic Conf in Hamburg** at the end of March

His prediction: the pace is not linear. "We're honestly exponential at this moment in time." He sidesteps the ethics of AI companies (referencing tensions between Anthropic and OpenAI) to focus on the practical reality that models, reasoning, and tooling are all improving at a compounding rate.

## Highlights

- **Paul on the industry mood:** "We're at this real crazy crossroads in the industry."
- **Paul on model quality:** Around late last year, "the models got really good, like really, really good. Really, really, really incredible."
- **Paul on running six agents at once:** "I had my terminal open. I had six Claude Codes going at once, building like six different small features at a time."
- **Paulina's blunt summary:** "It's a multiplier. If there is a good thing, you'll get a lot of good thing. If it's a shit, you're going to get a lot of shit."
- **Paul's spicy take on architecture:** The industry spent years mocking "ivory tower architects," but now AI is pushing engineers back into "the architecture lab."
- **Paul on plan mode:** It is the AI equivalent of `terraform plan` — useful, but only if people actually read it.
- **Paul's unusual open-source policy:** External pull requests are disabled entirely so the team can control the supply chain.
- **Most memorable workflow detail:** Paul's adversarial reviewer is instructed, "You are a grumpy DevOps engineer and I want you to pull this code apart."
- **Practical win:** That grumpy reviewer caught a path traversal bug in its first week.
- **Paul on testing excuses:** "We were scraping the barrel before at coming up with reasons why there shouldn't be any tests. Now that's eliminated."
- **Paul's warning against mega-prompts:** Asking an agent to "rebuild me Slack" with no context is a great way to conclude, incorrectly, that "AI is garbage."
- **Paul on context loss:** "Compact your conversation" is the new "restart your machine."
- **Paul on cost:** Five people, $200/month each, covering the full AI workflow — versus orgs spending $10K+ per developer per month on unfocused vibe coding.
- **Paul on adoption strategy:** Start by letting AI analyze bugs and accessibility issues — build trust before asking it to write code.

## Resources

- [Claude Code Documentation — Common Workflows](https://code.claude.com/docs/en/common-workflows) — Official Anthropic docs covering plan mode, extended thinking, and agentic workflows in Claude Code.
- [Anthropic Skills Repository](https://github.com/anthropics/skills) — Public repository of modular Markdown-based skill packages that extend Claude's capabilities for specialized tasks like security review or accessibility checking.
- [System Initiative on GitHub](https://github.com/systeminit/si) — The open-source repository for System Initiative's infrastructure automation platform, including the design documents Paul references.
- [Git Worktree Documentation](https://git-scm.com/docs/git-worktree) — Official docs for `git worktree`, the feature that enables Paul's multi-branch parallel development workflow.
- [Trivy Supply Chain Attack Analysis (Socket)](https://socket.dev/blog/unauthorized-ai-agent-execution-code-published-to-openvsx-in-aqua-trivy-vs-code-extension) — Detailed writeup of the incident Paul references where a bot stole credentials, deleted GitHub releases, and published a poisoned VS Code extension.
- [Building Evolutionary Architectures — Fitness Functions](https://evolutionaryarchitecture.com/) — The book and concepts behind architectural fitness tests that Paul's team uses to verify DDD boundaries and prevent domain leakage.
- [GitHub: New Repository Settings for Pull Request Access](https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/) — The GitHub feature Paul mentions for disabling external pull requests at the repository level.
