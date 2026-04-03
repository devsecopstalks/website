---
title: "#1 - Infrastructure as Code"
date: 2020-02-24T00:00:00+00:00
lastmod: 2020-02-24T00:00:00+00:00
episode: 1
author: "DevSecOps Talks"
participants: ["Andrey", "Mattias", "Julien"]
aliases:
  - /episodes/infrastructure-as-code/
---

When should you start using infrastructure as code and when not. What tools are there to help and how can you use them. Follow us in our first talk.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

{{< podbean d7x4q-d53cd6 "DEVSECOPS Talks #1 - Infrastructure as Code" >}}

---

## Summary
In this inaugural episode, Mattias, Andrey, and Julien discuss what infrastructure as code really means, why teams adopt it, and where it can go wrong. They explore the evolution from manual server management to declarative infrastructure, the differences between configuration management and infrastructure provisioning, the growing complexity of tools like Terraform and CloudFormation, and why culture, process, and operational discipline matter as much as the tooling itself.

## Key Topics

### What Infrastructure as Code Actually Solves
The discussion starts with Mattias describing the shift from manually editing Apache configs over SSH to defining cloud environments in code. He recalls the progression: first managing individual servers by hand, then adopting configuration management tools like Puppet, Chef, and Ansible, and finally arriving at cloud-native tools like AWS CloudFormation that can provision entire environments declaratively.

Andrey pushes the conversation toward first principles, arguing that it is important to separate the "what" from the "how." He explains that infrastructure as code depends on having APIs — software-defined interfaces that allow infrastructure to be created and managed programmatically. Without that kind of interface, teams are limited to SSH and the manual tools they had before. The rise of public cloud providers and platforms like OpenStack finally gave teams the APIs they needed to describe infrastructure declaratively in definition files.

### Configuration Management vs Infrastructure as Code
A key distinction in the episode is the difference between server configuration tools and true infrastructure as code. Andrey notes that tools like Puppet, Chef, and Ansible were originally conceived as server configuration management tools — designed to automate the provisioning and configuration of servers, not to define infrastructure itself.

He acknowledges this is a gray area, since tools like Ansible can now call AWS APIs and manage infrastructure directly. But historically, the configuration management era was about fighting configuration drift on existing servers, while the cloud era introduced the ability to declare entire environments as code. If you asked the vendors selling Chef, they would tell you Chef is "all about infrastructure as code" — but the original intent was different.

### When to Automate — and When Not To
The hosts caution against automating too early. Andrey says he tends not to automate things until they genuinely need automation. If creating one cluster with a few nodes and one database is all you need, full automation may be premature. But if you know you will eventually manage hundreds or thousands, starting early makes sense.

Julien reinforces this point with a memorable gym analogy: "You go to the gym, you see Arnold Schwarzenegger lifting 200 kilos from the ground and you say, he does it, I can do it. And then you pick up the little weight and find out that if you start with 200 kilos, you're gonna break your back." His point is that infrastructure as code tools get you up and running fast — that is what they are designed for — but day two operations always come knocking. The automation itself can become a burden if you are not careful about what you automate and when.

### Infrastructure as Documentation and Source of Truth
Mattias describes one of his main reasons for using infrastructure as code: knowing what is actually running. He sees the codebase as documentation and as proof of the intended state of the environment — a way to verify that what he thinks is deployed matches what is actually in the cloud.

The hosts agree with that idea, but they also point out the tension between declared state and reality. If people still make manual changes in the cloud console, the code drifts away from what is actually running. Andrey notes the problem: if undocumented manual changes are not reflected back into code, the next infrastructure deployment could recreate the original broken state — "you're back to the fire state, basically."

### The Terraform Complexity Problem
Julien brings up Terraform as "the elephant in the room" and argues that it has become significantly more complex over time. He says the language started out as purely descriptive, but newer features in HCL2 — such as for loops, conditionals, and sequencing logic — have pushed it closer to a general-purpose programming language.

His concern is that this makes infrastructure definitions harder to read and reason about. Instead of simply describing desired state, users now have to mentally execute the code to understand what it will produce. Andrey agrees there is a legitimate need for this evolution — once a declarative setup grows large enough, you genuinely want loops and conditionals — but acknowledges it creates a tension between readability and expressiveness.

### Declarative vs Imperative Approaches
The episode explores the difference between declarative and imperative models. Andrey explains that shell scripts are imperative — you tell the system exactly what to do, step by step — while a declarative tool lets a team state the desired outcome and rely on the platform to converge on that state.

Kubernetes is presented as a strong example of the declarative model. You submit manifests that declare what you want, and operators work to make reality match that intent — not necessarily immediately, but as soon as all requirements are fulfilled. Andrey suggests infrastructure tooling may evolve in this direction, with systems that continuously enforce declared state rather than only applying changes on demand. He gives a security example: an intruder stops AWS CloudTrail, but a reactive system — like a Kubernetes operator — detects the deviation and turns it back on automatically.

Julien adds that this is already happening. He mentions that a Kubernetes operator exists to bridge the gap to cloud APIs, allowing teams to define infrastructure resources inside Kubernetes YAML manifests and have the operator create them in the cloud. Google Cloud's Config Connector is a concrete example of this pattern, letting teams manage GCP resources as native Kubernetes objects.

### Immutable Infrastructure and Emergency Changes
Andrey strongly advocates for immutable infrastructure: baking golden images using tools like Packer, deploying them as-is, and replacing systems rather than patching them in place. In that model, people should not be logging into systems or making changes manually. If you need a change, you burn a new image and roll it out. SSH should not even be enabled in a proper cloud setup.

Mattias raises a practical challenge: in real incidents, people with admin access to the cloud console often need to click a button to resolve the problem quickly. He describes his own experience — the team started with read-only production access but had to grant write access once on-call responsibilities kicked in. Andrey agrees that teams should not be dogmatic when production is on fire: "You go and do whatever it takes to put fire down." But those emergency fixes must be reflected back into code, and the team must know exactly what was changed. Otherwise, the next deployment may recreate the original problem.

### Culture and Process Matter More Than Tools
One of the clearest themes in the conversation is that infrastructure as code is not just a tooling choice. Julien argues that it does not matter what technology you use if your process and culture are not aligned with security and best practices: "You can fix the technology only so much, but it's mainly about people."

Mattias describes a setup where Jenkins applies all CloudFormation changes, and every modification to the cloud goes through pull requests, code review, and change management — the same workflow used for application code. This means infrastructure changes become auditable, reviewable, and easier to track. Andrey sees this as applying development principles to infrastructure: version history, visibility into who changed what, the ability to ask someone why they made a change, and code review before changes are applied.

### Guardrails for Manual Changes
Andrey shares a practical example from a previous engagement where developers had near-admin access to the AWS console and would create EC2 instances, S3 buckets, and other resources outside of Terraform or CloudFormation. To control cost and reduce unmanaged resources, the team built a system using specific tags generated by a Terraform module.

A Lambda function ran every night, scanned for resources without the required tags, posted a Slack notification saying "I found these, gonna delete them next day," and tagged them for deletion. The following night, anything still tagged for deletion was removed. This gave developers flexibility for experimentation — they could spin up resources manually and try things out — while preventing forgotten resources from becoming permanent, invisible infrastructure. It also helped keep costs under control.

### Tooling Is Only the Start
Julien stresses that adopting infrastructure as code does not automatically make systems reliable, immutable, or resilient. In his view, it is "just the beginning of the journey." He warns against the myth that infrastructure as code equals immutable infrastructure — you can absolutely build stateful, mutable systems with code if you choose to.

He also pushes back on the assumption that automation always saves time, admitting with self-awareness: "I automated a task, it took me two days to automate it, and I saved barely 10 seconds of my life." His advice is to measure the actual benefit rather than being seduced by the marketing brochure. Data will tell you more about a tool's real value than excitement will.

### Abstraction, Code Generation, and Developer Experience
The hosts discuss the challenge of making infrastructure easy for developers who just want a database and a connection string, not a deep understanding of DBA work and security configuration. Andrey argues that abstracting best practices away from developers saves enormous organizational time, since developer time is expensive and holds back feature delivery.

He describes a third approach beyond declarative and imperative: code generators. Large companies with resources sometimes build internal generators that take simplified YAML inputs and output fully declarative specs. This creates another level of abstraction on top of existing tools, allowing developers to be productive without needing to understand infrastructure details. It is controversial — in some ways it takes power away from people — but it can dramatically simplify the developer experience.

### Pulumi vs Terraform and Community Support
Andrey introduces Pulumi as an interesting new branch of infrastructure tooling that lets teams describe infrastructure in general-purpose languages like TypeScript, Python, or Go instead of domain-specific languages like HCL. He notes that while it feels familiar to developers — you stay in your comfort zone — you still need to learn a new DSL embedded in that language. It is "not entirely like you just described infrastructure in the language you know."

Julien says he tried Pulumi and found it appealing for developers who want consistency across their codebase. But he remains cautious, arguing that "code is a liability" — referencing Kelsey Hightower's satirical GitHub project *nocode* ("write nothing, deploy nowhere, run securely") to make the point that less code means fewer problems. For beginners, Julien recommends starting with Terraform or the native tooling from cloud providers, mainly because the community is larger, tutorials are more abundant, and there are meetup groups where people can learn from each other. His advice is pragmatic: "Just make sure that you ditch Terraform the minute it gets in your way."

### Start With the Problem, Not the Tool
Andrey repeatedly returns to the same question: what problem is being solved? He argues that teams should choose tools based on business needs and existing team capabilities, not because a tool is fashionable. "A lot of people and developers, they like shiny tools — and there's nothing wrong about that — but you always have to ask, what is the problem we are solving?"

Andrey's framing connects tool selection to team dynamics: if your team already has knowledge of a particular tool, relearning a new one just because it is trendy does not make sense. What you need is not a fancy tool but to deliver business value with the capabilities you have.

### Migration, Legacy, and Incremental Adoption
The hosts acknowledge that many teams are not starting from a clean slate. Andrey points out that legacy infrastructure exists for a reason: it helped the business survive and grow. As Mattias puts it bluntly: "Legacy pays the bills."

For organizations with years of manually built systems and hybrid environments, Andrey suggests doing value stream mapping to identify the biggest pain point and tackling that first. A greenfield project can serve as a success story to demonstrate the approach before trying to transform everything. He emphasizes that coming into an organization with a shiny idea and telling people "whatever you did before was crap" is a sure way to lose allies. Technology boils down to working with people — the tools are fine, but they do not replace the people running them.

### The Templating Dilemma
Mattias raises a specific frustration with infrastructure as code: templating. He likes looking at his Git repository and seeing exactly what is running, but heavy use of variables and templates means he sees placeholder names instead of actual values. This tension — between reusable, DRY templates and readable, concrete definitions — is a real challenge that the hosts acknowledge without a clean resolution.

### Resilience and Recovery
Near the end of the episode, Andrey gives a concrete example of losing a Kubernetes cluster in production. Because the environment had been defined as code, the team was able to recreate it and recover in about one to two hours. Some things that were not properly documented slowed them down; with complete documentation the recovery could have been as fast as 15 to 20 minutes — mostly just waiting for AWS to provision the resources after the API calls.

Julien adds context to this: he argues that even with infrastructure as code, recreating a Kubernetes cluster and failing over traffic while maintaining service is genuinely hard. The concept is sound, but having the safety net to actually do it takes time, practice, and a lot of work. His advice for building confidence is to adopt the mentality of immutable infrastructure and get into the habit of regularly recreating things and practicing failovers.

### Final Advice
Andrey recommends education first. He specifically mentions the book *Infrastructure as Code* by Kief Morris (published by O'Reilly, now in its third edition) as a strong foundation. His broader advice: understand the domain, define the problem clearly, ask yourself what outcome you want to deliver for the business, and let the answers to those questions guide your tool decisions.

Julien's closing thought is that in a large organization, a dedicated infrastructure team using infrastructure as code can manage everything — on-prem or cloud — with a single workflow. That team can abstract complexity so developers do not need to learn Terraform, CloudFormation, or any other tool. The specialization pays off by reducing onboarding friction and letting each team focus on what they do best.

## Highlights
- **Julien's gym analogy:** "You go to the gym, you see Arnold Schwarzenegger lifting 200 kilos from the ground and you say, he does it, I can do it. And then you pick up the little weight and find out that if you start with 200 kilos, you're gonna break your back." His point: infrastructure as code tools make the start easy, but day two operations will humble you.
- **Julien on Terraform:** He calls it "the elephant in the room" and argues that it has drifted from a descriptive language toward something more like a programming language, making it harder to reason about.
- **Julien on coding overhead:** "Code is a liability" — referencing Kelsey Hightower's *nocode* project to argue that every line of infrastructure code carries long-term maintenance costs.
- **Julien on no silver bullets:** "There is no silver bullets. Stop dreaming. Just see how much work it takes, how complicated it is."
- **Julien on automation ROI:** "I automated a task, it took me two days to automate it, and I saved barely 10 seconds of my life."
- **Andrey on incidents:** Teams should not be dogmatic — "If your production is on fire, you go and do whatever it takes to put fire down" — then put the fix back into code afterward.
- **Andrey on manual cloud resources:** He describes a Lambda-based cleanup system that scanned for untagged AWS resources nightly, posted to Slack, and deleted them the next day if no one claimed them.
- **Andrey on shiny tools:** "A lot of people and developers, they like shiny tools — and there's nothing wrong about that — but you always have to ask, what is the problem we are solving?"
- **Mattias on legacy:** "Legacy pays the bills" — a reminder that existing infrastructure made the business successful, and it deserves respect during any modernization effort.
- **Andrey's recovery story:** After losing a production Kubernetes cluster, the team recreated everything in one to two hours because it was defined as code — and could have done it in 15-20 minutes with better documentation.

## Resources
- [Infrastructure as Code by Kief Morris (O'Reilly)](https://www.oreilly.com/library/view/infrastructure-as-code/9781098150341/) — The book Andrey recommends as essential reading for practitioners. Now in its third edition, it covers patterns and practices for building and evolving infrastructure as code.
- [Pulumi — Infrastructure as Code in Any Programming Language](https://www.pulumi.com/) — The tool discussed in the episode that lets teams define infrastructure using TypeScript, Python, Go, and other general-purpose languages instead of domain-specific languages like HCL.
- [AWS CloudFormation](https://aws.amazon.com/cloudformation/) — AWS's native infrastructure as code service using declarative YAML/JSON templates, which Mattias and the team use with Jenkins for their deployment pipeline.
- [GCP Config Connector](https://cloud.google.com/config-connector/docs/overview) — The Google Cloud Kubernetes operator mentioned in the episode that lets teams manage GCP resources as native Kubernetes objects, bridging the gap between Kubernetes and cloud APIs.
- [Forseti Security (archived)](https://github.com/forseti-security/forseti-security) — The GCP security scanning tool Julien describes that could detect policy violations (like open ports) and automatically revert changes. Originally developed by Spotify and Google, it was archived in January 2025.
- [Kelsey Hightower's nocode](https://github.com/kelseyhightower/nocode) — The satirical GitHub project Julien references: "The best way to write secure and reliable applications. Write nothing; deploy nowhere." A humorous reminder that code is a liability.
- [HashiCorp Terraform](https://www.terraform.io/) — The infrastructure as code tool the hosts discuss extensively, including its evolution from a simple declarative language to the more complex HCL2 with loops and conditionals.
