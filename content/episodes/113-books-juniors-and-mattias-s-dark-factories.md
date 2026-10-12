---
title: "#113 - Books, Juniors and Mattias's Dark Factories"
date: 2026-10-12T17:43:31+01:00
lastmod: 2026-10-12T17:43:31+01:00
episode: 113
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
description: "If AI writes the code, where do juniors learn to build software? Mattias Hemmingsson shares his dark factory workflow, sparking a debate about code review, practical learning and how books help engineers give clearer instructions to AI."
subtitle: "A merge straight to production is a tough first assignment for a junior engineer."
readtime: "15 min read"
image: "https://pub-44b46df59567461a91e93c803fe57df3.r2.dev/covers/113-3582c5a80b5c.png"
youtube_id: "JyAJCk9cSmA"
audio_url: "https://mcdn.podbean.com/mf/web/otm0y08r43s7t5c9/113-books-juniors-and-mattias-s-dark-factories.mp3"
aliases:
  - "/episodes/113/"
---

If AI writes the code, where do juniors learn to build software? Mattias Hemmingsson shares his dark factory workflow, sparking a debate about code review, practical learning and how books help engineers give clearer instructions to AI.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

{{< whats-in-this-post >}}

<!-- Player -->

 {{<  podbean 8b89z-1b811b6-pb "DEVSECOPS Talks #113 - Books, Juniors and Mattias's Dark Factories"  >}}

---

<!-- Video -->

{{< youtube JyAJCk9cSmA >}}

## Where does a junior start when the factory never stops {#problem}

Two years ago a small foundation wanted a platform: somewhere a project with a good aim could ask for help and have volunteers with the right skills show up. Building it then meant a team, and it was expensive enough that it waited. This year it exists, and it was built by an issue tracker, a GitHub workflow and a set of models. The model work is billed per token, and that part is the good news.

The uncomfortable question arrives right behind it. If a platform that used to need a team now gets built by a pipeline, there is less work left that obviously needs people, so where do new engineers come in? The practical version of that question is which task you hand someone in their first week that teaches them anything, when the code is already written by the time they arrive.

The hiring side of this is already visible. Postings labelled junior ask for three or four years of experience, and people who are qualified on paper write to ask what they are supposed to do about that. The published data points the same way without settling the cause. Stanford's Digital Economy Lab [puts employment for 22 to 25 year olds](https://digitaleconomy.stanford.edu/news/canariesaug26/) in the most AI-exposed occupations about 19% below where it would be if it had kept pace with same-age workers in less exposed ones, and its authors say plainly that the data cannot establish how much of that divergence AI caused. So this is a design question for anyone running an automated pipeline, not a hiring department's problem.

## A dark factory is a conveyor with chosen gates {#dark-factory}

Start with the machine, because the shape of it decides where a person can stand.

#### What is a dark factory in software?

It is a pipeline where an issue goes in and merged code comes out, and humans appear only at the gates you put there on purpose.

The name is borrowed from manufacturing. A [lights-out factory](https://www.siemens.com/en-us/technology/lights-out-factory/) runs its production floor with nobody on it, on the logic that robots do not need the lights on. The software version is less dramatic and more mundane than the phrase suggests.

We run one for the foundation platform, and the parts are ordinary. GitHub issues are the unit of work. There are two sets of boards, one for humans and one for agents: a person drags a card onto the first board, and from there the agents move it along. The flow has three stages, which is the interesting bit. First, is the idea any good. Second, what is the plan. Third, execute. The foundation's own project tool sits on the front, so a manager files work there and an issue appears in GitHub without them ever opening GitHub. The whole thing is driven by GitHub workflows, runs on our own Kubernetes cluster, and calls open models hosted by [Berget AI](https://berget.ai/), a Swedish provider serving open-weight models from Swedish infrastructure, with a different model picked per task.

{{< key-point >}}A dark factory is not a smarter agent. It is a conveyor, and the only thing you really design is where the humans stand.{{< /key-point >}}

There's no staging environment; approved changes go straight to production. That arrangement is what makes the next question sharp.

## Putting juniors on the last gate {#review-entry-point}

So the obvious place to put a newcomer is the end of the conveyor, where the changes come out.

#### Should a junior's first job be approving the agent's merge requests?

Not on its own, because approving a large generated change asks for judgement a newcomer has not built yet, and whether it belongs in the job at all is the thing we did not agree on.

Mattias wants to bring in interns and juniors, label each merge request by discipline, front-end, security, database, and give each person a role. You approve what falls in your role, a senior oversees the whole thing, and the argument for it is that reviewing is what a lot of developers spend most of their day doing anyway. Start by looking at changes, learn the system that way, and move to writing changes once you are comfortable.

Andrey thinks it is a recipe for disaster, for one reason: review is judgement, and a junior has no basis for one yet. There is a second problem stacked on the first. What arrives at that gate is a big chunk of generated change, and reviewing one of those properly is hard for an experienced engineer. Handing it to someone in their first month is not an easier version of the same task.

The first questions to settle are supervision and release impact. Is a senior paired with the junior on that review, or is the junior the only reader? And what does approval actually release? A change that lands in a low environment and a change that lands in production are not the same decision, whoever is making it.

{{< key-point >}}Approval without a basis for judgement is a rubber stamp with somebody's name on it.{{< /key-point >}}

The size problem is not imaginary. AI lets a change blow out, and suddenly the queue is full of huge pull requests. Some of that is model habit: in our experience the OpenAI family likes to build the enterprise version of whatever you asked for, wrapping guards around every edge case it can imagine, when what you wanted was a spike. <mark>Review is a late place to fix scope.</mark> By the time the diff exists, the expensive part of the mistake has already been paid for.

## Control the inputs, not the outputs {#control-the-inputs}

Which points at the other end of the pipe.

#### Where do you catch bad output from an agent?

At the input, because by the time it is output there is too much of it and it is too late to be cheap.

There are two strategies available and you can mix them. Control what goes in, and in most cases what comes out is good enough. Or let the models run and try to catch problems on the way out of the factory. The second one is where everyone's attention goes, and it is the worse deal.

Scope is the hardest part of the input to get right, and the trap is that good writing hides it. A clear, well-argued request can quietly imply a change across five tools at once, and nothing in the prose warns you. The first alignment is therefore not about design. It is how big is this, how many things does it touch, is it really needed now. Get the idea clean and the plan comes back as something a person can say yes or no to, which is the human gate that matters most in the whole flow.

{{< key-point >}}If you cut the change at the idea stage, you are cutting one paragraph. At review you are cutting a thousand lines someone already wrote.{{< /key-point >}}

The same logic shapes how we drive the tools locally. Before any interviewing happens, there is a study step: subagents go and read everything relevant across the repositories, pull in issues that overlap or duplicate the work, and run spikes on the two or three ways it could be done. Only then does the tool start asking questions. The questions are better, and they arrive once instead of trickling in. That matters even more inside a factory, where you want everything the run needs from you in a single pass. A plan that comes back with a pile of open questions means redoing the lot.

That is also where we would put someone new. Give them the problem rather than the finished change, let them run spikes with the models, work out what the options cost, and write the specification, with a senior alongside. It is slow in the way that teaches, and it is the part of the pipeline where a person still changes the outcome.

## Who pays per token and who pays per month {#model-cost}

The two setups in this conversation differ mostly in the unit of the bill, and that turns out to shape the design.

#### What changes when a pipeline bills per token instead of per month?

Model choice directly affects the bill, which makes cheaper models worth testing on routine steps.

Working locally, you can lean on subscriptions and juggle tools by hand: one orchestrating, one as the workhorse when something needs to read a lot of files and find a thing, one for the complex thinking. The factory has the same subscriptions available and does not use them for the runs. It calls the API and pays per token. That is this factory's choice, not a requirement of running unattended, and it does route between models on its own, a different one per task. What it does not have is somebody at the keyboard switching tools halfway through, and being clever about which model gets which task is the cost control that comes with paying per token.

The cheap tier is now cheap enough to change those decisions. OpenAI's [published prices](https://developers.openai.com/api/docs/pricing) put `gpt-6-luna` at $0.10 per million input tokens and $0.50 per million output, against $2 and $10 for [Claude Sonnet 5](https://claude.com/pricing). That is twenty times on input for the models doing routine work in a pipeline. Turning the reasoning effort up to `high` or `xhigh` on the cheap model got results we would have expected from Sonnet 5, which is our impression from using it and not a benchmark. OpenAI's own [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) is more careful, recommending `xhigh` only when your evals show a benefit that justifies the extra latency and cost. Both can be true, and the way to find out is to price a finished task rather than a token, since the effort setting that makes the cheap model good enough also makes it spend more.

Prices also keep moving, in both directions, so a routing decision made six months ago is worth rechecking rather than defending.

{{< key-point >}}In an unattended pipeline, model choice is a line item. Check it like one.{{< /key-point >}}

## Nobody taught us the internet {#teach-learning}

Cost is the easy part. What to teach the people coming in is where we disagreed again.

#### What can you actually teach someone when the stack keeps changing?

How to learn, how to adapt and how to work with other people, because that part outlives whatever stack you would have taught instead.

Andrey's position is that we are mostly not in a position to teach them the technology, and that they will figure it out. University curricula are already behind. We could sit people down with C and C++ and they would learn low-level programming and algorithms, and then, maybe, everything gets rewritten in a memory-safe language like Rust, or moves up an abstraction where nobody thinks in programming languages at all. Nobody knows which, and that is the point. Nobody taught our generation the internet. Nobody taught this one TikTok. The ones who are good at it will lead, and we arrive carrying a lot of baggage.

Mattias's answer was short: you need to help them. Paulina's was more specific, and it reframes what help means. Her 16 year old brother picks up new tools instantly; her parents needed a whole process to get comfortable with the same things. Her parents could not hand her technology they never had. They gave her how to learn, how to adapt and how to work with other people, and that is what let her catch up with everything that came later. Andrey agrees. The argument was never about whether to help, only about what there is to hand over.

Her two universities make the point concrete. In Poland, twelve or thirteen courses a semester, knowledge to memorise, and writing code with a pen on paper in the exam. In Denmark, three to five courses, mandatory group work, and longer exams where you could bring laptops, books and notes, because the task was to find the knowledge and apply it to a problem. She uses the second one every working day and almost none of the first.

{{< key-point >}}The curriculum ages. Knowing how you learn best is the part that still works in five years.{{< /key-point >}}

Running an intern this summer produced a usable progress metric: you are making progress when you can answer the question without asking Claude. Not never asking. Being able to answer first. The failure mode on the other side is handing a powerful coding tool to someone who cannot aim it yet, which is like giving a baby a fire hose. It goes everywhere, and there is not enough strength to point it anywhere useful.

## Books are where the vocabulary comes from {#books-vocabulary}

That ability to aim comes down to language, which is the least technical skill on this list and currently one of the most useful.

#### Why would reading books make you better at using AI?

Because precise words are what you get to steer with, and the books about programming problems are where the precise words are.

The part that holds up on its own is shared vocabulary. If you and the tool mean the same thing by the same word, a requirement takes one sentence instead of five. On top of that sits a theory, and it is only a theory: the classic programming books are in the training data, so borrowing their vocabulary lands closer to something the model already knows. Which books went into which model is not something we can check from outside. What is observable is the opposite case. Vague descriptions produce vague results, and if you do not share a vocabulary with the tool you have to establish one, which in practice means writing a skill that says when I say this, I mean that, so it stops guessing.

The failure is easy to recognise once you have watched a child do it. They start thinking out loud, and it goes on, and on, and winds through three different ideas, and the system loses the thread entirely, because the thought was never delivered as a thought. Adults do the same thing in a prompt and blame the model. The bar for input is genuinely low now compared with the voice assistants of a few years ago, which could already handle something as loose as finding the song you listened to yesterday. Low is not zero. You still have to deliver a complete thought, and reading is still the cheapest way to get better at that.

{{< key-point >}}Reading the books that describe the problems is how you get the words to describe your problem.{{< /key-point >}}

So, books. The programming classics for the vocabulary, with the caveat that Clean Code is not the one anybody is going to enjoy. If you are choosing between that and [The Five Love Languages](https://5lovelanguages.com/), take the love languages first: it is short, practical, and reads like a manual, which is more than most technical books manage. On the fiction side the current recommendations are S.H. Jucha's The Silver Ships, which gets AI roughly where we seem to be heading, and Dennis E. Taylor's Bobiverse, which is fun if you can take that much Bob.

## What this means for teams {#what-this-means}

If you are building a pipeline like this, the entry point for new people is a design decision and it defaults badly. Left alone, the only human-shaped slot in the flow is the last gate: approving a large generated change, with the deploy right behind it. That is a lot to ask of someone in their first month, and it is not the only slot you could open.

Four things worth doing this week:

- **Open a slot at the front, not only at the last gate.** Give new people a problem and let them run spikes, with the deliverable a specification somebody else can plan from, and keep a senior next to whatever reviewing they do.
- **Write down what each approval releases.** Which board, which environment, and whether a merge is a deploy. Decide that before you hand anyone the approve button, not after.
- **Put a scope gate before the plan step.** How many things does this touch, is it needed now. One paragraph cut there is a thousand lines not written.
- **Price your pipeline per finished task.** Try the routine steps on the cheap tier with reasoning effort turned up, compare the full cost of a completed task against what you run today, and recheck in a few months when the prices have moved again.

## Common questions, answered {#faq}

### How do I tell if a junior is actually learning when they use AI all day? {#faq-junior-progress}

Set the bar at answering before asking: they are making progress when they can answer a question about the system themselves and use the tool to confirm. That is a change you can watch for over weeks, and it bans nothing. Pair it with work where the thinking is visible, a spike with a written conclusion or a specification someone else can plan from, because understanding is hard to see in a merged pull request. Treat it as an indicator, not a verdict: if the answers still start with opening the assistant, look at what the tasks are asking for.

### How do I stop agent pull requests from arriving too big to review? {#faq-big-prs}

Cut the scope before anything is planned, not at review. Make the first gate a question about size: how many components does this touch, and is all of it needed now. A clearly written request is the dangerous case, because good prose can describe an enormous change and still read as reasonable. Models vary in how far they expand a task, so if the diffs are consistently bigger than what you asked for, try another model for that step.

### How do I cut the token bill on an unattended AI pipeline? {#faq-token-bill}

Route by task and try the routine work on the cheapest tier first. OpenAI lists `gpt-6-luna` at $0.10 per million input tokens against $2 for Claude Sonnet 5, so the tiers are twenty times apart on input. Then compare what actually bills you, the cost of a completed task on your own workload, not the headline rate: raising the reasoning effort to make the cheap model good enough also raises the tokens it burns, and OpenAI's reasoning guide asks for exactly that evidence before you turn effort up.

## Related episodes {#related-episodes}

- [Episode 112, DevOps Careers: What Should You Learn Now?](/episodes/112/) is the conversation this one continues, on which knowledge keeps its value when agents fill in the syntax.
- [Episode 7, How Do We Learn](/episodes/007-how-do-we-learn/) is the pre-AI version of the learning argument, from when reading the documentation was the job.
- [Episode 94, Small Tasks, Big Wins: The AI Dev Loop at System Initiative](/episodes/094-small-tasks-big-wins-the-ai-dev-loop-at-system-initiative/) covers the small-task, human-in-the-loop end of the same workflow with Paul Stack.
- [Episode 111, AI Agents: When Helpful Becomes Harmful](/episodes/111/) is the blast radius question, which is what a merge straight to production turns into.
- [Episode 104, When AI Coding Gets 10x More Expensive](/episodes/104/) is the background on token billing and why an expensive model is sometimes the cheaper one.

## Resources {#resources}

- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing) is the primary source for `gpt-6-luna` at $0.10 per million input tokens and $0.50 per million output.
- [Claude pricing](https://claude.com/pricing) gives the other side of that comparison, Sonnet 5 at $2 and $10 per million, with Opus 5.5 at $4 and $20.
- [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning) documents the reasoning effort levels including `xhigh`, and says to use it only when your own evaluations justify the cost.
- [Berget AI](https://berget.ai/) is the Swedish provider behind the factory described here, serving open-weight models over an OpenAI-compatible API from Swedish infrastructure.
- [Stanford Digital Economy Lab, canaries update](https://digitaleconomy.stanford.edu/news/canariesaug26/) has the entry-level employment gap in AI-exposed occupations, and is careful about what it does not attribute to AI.
- [Siemens, lights-out factory](https://www.siemens.com/en-us/technology/lights-out-factory/) is where the dark factory term comes from, and is a useful check on how far the software version of it actually goes.
- [The Five Love Languages](https://5lovelanguages.com/) is the book that started the episode, and the one recommendation here with no technical justification at all.
