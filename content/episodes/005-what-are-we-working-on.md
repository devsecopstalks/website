---
title: "#5 - What Are We Working On"
date: 2020-04-06T00:00:00+00:00
lastmod: 2020-04-06T00:00:00+00:00
episode: 5
author: "DevSecOps Talks"
participants: ["Andrey", "Mattias", "Julien"]
aliases:
  - /episodes/what-are-we-working-on/
---

We had a few potential topics for this episode but before getting started with them we decided to discuss what technological problems we were solving during the last two weeks. As it turns out there were quite a lot to discuss. Tune in for tips on auditing SSH sessions through a jump host, preventing downloads from AWS S3 even if you got read access, credentials in Git repository, why you should (or should not) use Kubernetes and more.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

{{< podbean w35eg-d87a2b "DEVSECOPS Talks #5 - What Are We Working On" >}}

## Summary

In this free-form early episode of DevSecOps Talks, a casual "what have you been up to" catch-up turns into a sharp exchange on the gap between security in theory and security in practice. One host discovers plaintext service account keys, database passwords, and a production SSH tunnel all committed straight into a Git repository — and the team walks through how to unwind that without breaking delivery. Julien Bisconti argues that security tooling is fundamentally failing developers because it is too hard to use under real delivery pressure. The episode also delivers strong opinions on why teams should not default to Kubernetes, the hidden complexity of S3 encryption with KMS keys, and why Google's BeyondCorp model makes VPNs look like a relic.

## Key Topics

### SSH session logging, bastion hosts, and compliance visibility

The episode opens with a deep dive into SSH session logging for bastion hosts in AWS. One of the hosts explains how AWS Systems Manager Session Manager can be used to access instances without VPNs or direct inbound connectivity — the SSM agent on each instance calls home to AWS, and AWS proxies the connection back. That model is attractive for hybrid and on-prem environments because it removes networking complexity around NAT, port forwarding, and VPN setup. It also provides session logging, IAM-based access control, and command output recording.

But the drawbacks surface quickly. Session Manager logs users in as a generic SSM agent user with `/usr/bin` as the working directory. Documentation is sparse, and Bash is launched in shell mode to support color interpretation, which pollutes session logs with escape characters. A bigger concern is that access control rests entirely on IAM credentials — in an environment with fully dynamic, short-lived credentials that is manageable, but it becomes risky anywhere static keys exist.

The host describes trying to map Session Manager logins to individual users, only to find that it requires static IAM identities with specially named tags containing usernames — a non-starter for environments where everything is dynamic.

That leads into alternative approaches. An AWS blog post describes forcing SSH connections through the Unix `script` utility to record sessions, then uploading logs to S3. But even that is fragile: logs are owned by the user, so technically the user can delete or overwrite them. A more robust path is [tlog](https://github.com/Scribery/tlog), a terminal I/O logger that writes session data in JSON format to the systemd journal, where it cannot be easily tampered with. From there, the CloudWatch agent can export journal data to S3 for long-term storage.

The broader point is that command logging sounds simple in compliance conversations, but in practice it becomes a deep rabbit hole full of bypasses, noise, and design tradeoffs.

### Monitoring user activity without drowning in logs

The hosts compare notes on monitoring shell activity. One host mentions using auditd to track user actions on bastion hosts in a previous environment, but the log volume was overwhelming — even Elasticsearch struggled to keep up with the ingestion rate.

That sparks a discussion around anomaly detection and heuristics. The real challenge is not collecting logs but determining what is unusual and worth investigating. Failed SSH login alerts are mentioned as a useful signal, though another host pushes back: "Should you have SSH with the password at all? You should have a key." The point stands — without careful tuning, even sensible alerts generate noise faster than teams can act on them.

The exchange captures a recurring DevSecOps reality: collecting telemetry is the easy part; turning it into something actionable is where most teams get stuck.

### S3 bucket security, public access controls, and KMS encryption surprises

The conversation shifts to AWS S3 security. Public buckets remain a common source of breaches, but AWS now offers [S3 Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html) — account- and bucket-level settings that prevent public access regardless of individual object ACLs. In Terraform, this is a dedicated resource block.

The more nuanced insight is about encryption. The host explains the difference between S3 server-side encryption with the default AWS-managed key (SSE-S3) and encryption with a customer-managed KMS key (SSE-KMS). With SSE-S3, S3 decrypts objects transparently for any client with read access to the bucket. With a customer-managed KMS key, S3 cannot decrypt the object unless the requester also has `kms:Decrypt` permission on that specific key.

This became a real problem in a cross-account, cross-region workflow involving Go Lambda binaries. Go Lambdas require the deployment artifact to reside in the same region as the function. The team was copying artifacts between accounts and regions, had granted S3 read permissions, but downloads kept failing. CloudTrail logs revealed the real culprit: "I cannot decrypt." The consumers lacked KMS key access. In that case, the fix was switching to SSE-S3 since the artifacts did not require the stronger protection of a customer-managed key.

The host is careful to note that AWS documentation on cross-account S3 access does not prominently flag this encryption interaction — a gap that can cost teams hours of debugging.

### Plaintext secrets in Git: a frighteningly common anti-pattern

One of the most memorable segments comes when a host describes reviewing an application stack and finding service account keys committed in cleartext in the repository root. The repository also contained a large configuration file with usernames, passwords, API credentials for mail services, login providers, and multiple environments (dev, prod) — all in plain text.

But the worst part: for local development, the team SSH-tunneled into the production SQL server, mapping remote port 3306 to local port 3307. An SSH key providing direct access to the production database was sitting right there in the repo.

The reaction is immediate — this is exactly the kind of setup that accumulates when convenience wins over security for too long. But rather than proposing a risky teardown, the host outlines an incremental migration plan:

1. **Dockerize the local development stack** so developers can run everything locally without production keys
2. **Move secrets into the CI/CD pipeline**, injecting them only at build and deploy time
3. **Separate environments** so test clusters get test credentials and production secrets never touch developer machines

Andrey pushes the thinking further: injecting secrets at build time is still risky because anyone who gets the Docker image gets the secrets. The better model is **runtime secret retrieval** — workloads authenticate dynamically at startup and fetch only the secrets they need. HashiCorp Vault is the concrete example: in a Kubernetes environment, a pod uses its Kubernetes service account to authenticate to Vault, obtains a short-lived token, and retrieves static or dynamic secrets. If someone steals the image and runs it outside the cluster, they cannot authenticate and get nothing.

### Vault versus cloud-native secret management

The secrets discussion expands into a broader comparison. Andrey, who has been doing public speaking about Vault and fielding consulting requests around it, frames the choice pragmatically.

For **hybrid-cloud or multi-cloud** environments, Vault is likely the best option because it provides a unified interface for secret management, dynamic credentials, and synchronization across providers.

For **single-cloud commitments** — say, all-in on AWS — native services can cover many of the same use cases: AWS STS for temporary credentials, RDS IAM authentication for database logins, AWS Secrets Manager (which may even be running Vault underneath, as one host speculates), and AWS Certificate Manager for TLS certificates. If the organization is not going multi-cloud, the overhead of running Vault may not be justified.

The recommendation is not ideological. It depends on architecture, portability needs, and operational complexity.

### When Vault works technically but fails organizationally

Julien Bisconti adds an important caveat from experience. He describes deploying Vault in a multi-availability-zone setup with full redundancy — technically solid. But the project "went to a halt completely" when it hit governance questions: who should access what, under which rules, and who owns the policies. It became a political war, and the entire deployment had to be rolled back.

The lesson: security tools are good at automating technical workflows, but if the underlying organizational process is broken, you automate a broken process. Security, monitoring, deployment, and access control are deeply entangled, and tooling alone cannot untangle them.

### Security tooling fails because developers cannot use it

Julien brings the strongest developer-empathy argument of the episode. Developers do not ignore security because they are careless — they bypass it because secure workflows are too awkward under delivery pressure. A manager does not understand why the developer is blocked, pressure mounts, and the result is `// just hardcode that here, I don't care, it works`.

Even simple tasks illustrate the problem. Julien asks: can you generate an SSL certificate with OpenSSL from memory right now? Most engineers cannot — it is something they do every few months and have to look up each time. He references the famous [XKCD comic](https://xkcd.com/1168/) about entering the correct `tar` command with ten seconds left.

This evolves into a philosophical observation. One host identifies as a "tool builder" rather than a "product builder" — someone who enjoys building mechanisms but does not always think deeply about end-user experience. That mindset, common among infrastructure and security engineers, may explain why so many DevSecOps tools are powerful but painful to adopt. The gap is not in capability but in usability.

### VPNs, zero trust, and the BeyondCorp model

Julien argues that VPNs are an increasingly painful abstraction. Even Cisco — the company that essentially built enterprise VPN technology — had to raise capacity limits during the COVID-19 pandemic because their own infrastructure could not handle the load. Split tunneling introduces its own vulnerabilities, and full-tunnel VPN creates a bottleneck for everything.

He points to Google's [BeyondCorp](https://research.google/pubs/pub43231/) model, published in 2014, which established the principle that network location should not determine access. The analogy: do you build a castle with walls where anyone inside has full access, or do you put a guard in every room checking credentials? The latter — zero trust — is harder to implement, but it limits blast radius and removes the binary "in or out" problem.

Andrey connects this to the emerging service mesh ecosystem. Technologies like [Consul Connect](https://developer.hashicorp.com/consul/docs/connect) implement zero-trust networking at the application level with mutual TLS and identity-based authorization. The hosts note that the service mesh space is still fragmented — just as there was a "war of orchestrators" before Kubernetes emerged as the default, there is now a "war of service meshes" still playing out.

### Kubernetes hype versus simpler orchestration

A significant portion of the episode is a productive debate about orchestration choices. Andrey argues strongly against defaulting to Kubernetes. He describes a hybrid-cloud project in Africa running the full HashiCorp stack: Consul for service discovery, configuration, and networking; Nomad for workload scheduling. A team member with relatively little experience got the stack up and running in days.

Andrey outlines the operational weight of Kubernetes: cluster version upgrades where in-place upgrades may skip new security defaults (making full cluster recreation the recommended path), autoscaler configuration layers (pod autoscaler, cluster autoscaler, resource limits), ingress management, YAML sprawl from Helm charts, and a platform that evolves so rapidly it demands continuous learning. He especially warns against running databases in Kubernetes — the statefulness adds pain.

For single-cloud AWS, he argues that ECS is often the better choice: the control plane is free (or nearly so), the per-node overhead is minimal compared to Kubernetes, and AWS handles the operational burden.

Mattias pushes back with a practical counterpoint. Kubernetes provides a consistent platform for diverse workloads — containers, databases, monitoring, custom jobs — all managed through the same interface. Helm charts for common components like nginx-ingress, cert-manager, and external-dns make the ecosystem approachable. The value is in standardization and adaptability.

The hosts also note GKE's pricing evolution: Google introduced a per-cluster management fee (roughly $0.10/hour per control plane) to discourage sprawl and encourage consolidation — a signal that even managed Kubernetes has real costs.

The disagreement is honest but constructive. The shared conclusion: start with what the business needs, then pick the simplest tool that gets you there. "The best battle is the battle you don't fight." And as Julien notes, teams that avoid the Kubernetes default often demonstrate deeper architectural thinking — choosing based on the hype is an insurance policy, but it is not the same as choosing based on needs.

### Slack bots, workflow automation, and the security surface

Near the end, Mattias raises the topic of Slack bots for operational tasks — deployment reporting, status checks, and interactive queries. Andrey reframes the conversation around security: if Slack becomes part of a privileged control plane — for example, a bot that handles privilege escalation by requesting approvals through Slack messages — then request spoofing, account compromise, and weak isolation become serious concerns.

The idea of a privilege-escalation bot is interesting (request access via Slack, get approval from designated approvers, receive time-limited credentials with full audit logging), but the attack surface is real. Slack provides a powerful collaboration platform for building workflows without custom UIs, but once it handles access decisions, security design matters as much as convenience.

## Highlights

### "All the service account keys were in clear text. In the repo."
A host describes opening up a client's application stack and finding cloud service keys, usernames, passwords, API credentials, and an SSH key that tunnels directly into the production SQL server — all committed to Git in plain text. It is the kind of discovery that instantly explains years of hidden risk.

How do you unwind that without breaking delivery? The hosts walk through an incremental migration plan in this episode of DevSecOps Talks.

### "Security tooling is actually not that usable."
Julien Bisconti delivers a sharp truth: developers do not bypass security because they are careless. They do it because secure workflows are too slow, too confusing, and too far removed from how they actually work. When the pressure comes from a manager who does not understand the blocker, the shortcut wins every time.

A candid take on why hardcoded secrets keep showing up in real codebases. Listen to the full discussion on DevSecOps Talks.

### "I really applaud people who don't choose Kubernetes — that means they actually know what they're doing."
One of the spicier platform takes of the episode. The argument is not that Kubernetes is bad, but that defaulting to it without analyzing your actual needs is a sign of hype-driven architecture. If a simpler stack solves the problem, picking the biggest platform just creates more operational burden.

Hear the full Kubernetes-versus-Nomad-versus-ECS debate on DevSecOps Talks.

### "If your process is not good, you're going to automate a bad process."
Julien recounts deploying Vault with full HA and multi-AZ redundancy, only to have the project grind to a halt over organizational politics — who should access what, and who decides. The tooling worked perfectly. The organization did not.

A reminder that DevSecOps maturity is not just about picking better tools. Catch the full story on DevSecOps Talks.

### "Once somebody is inside, they have the keys to the kingdom."
The VPN and zero-trust discussion delivers one of the strongest security arguments of the episode. Julien explains why broad network access — the castle-and-moat model — is the wrong abstraction for modern systems, and why identity-based, fine-grained access control is worth the implementation cost.

If the old perimeter model still shapes how your team thinks about infrastructure security, this part of the episode will resonate. Listen on DevSecOps Talks.

## Resources

- **[AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)** — AWS documentation for Session Manager, which provides secure instance access without SSH keys, open ports, or bastion hosts, with built-in session logging.

- **[tlog — Terminal I/O Logger](https://github.com/Scribery/tlog)** — Open-source terminal session recording tool that logs to systemd journal in JSON format, making sessions searchable and tamper-resistant. Discussed in the episode as a more robust alternative to the Unix `script` command.

- **[AWS S3 Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)** — AWS documentation on account- and bucket-level settings to prevent public access to S3 resources, regardless of individual object ACLs or bucket policies.

- **[Troubleshooting Cross-Account Access to KMS-Encrypted S3 Buckets](https://repost.aws/knowledge-center/cross-account-access-denied-error-s3)** — AWS guidance on the exact issue discussed in the episode: S3 downloads failing because the requester lacks KMS key permissions, even when bucket-level access is granted.

- **[BeyondCorp: A New Approach to Enterprise Security](https://research.google/pubs/pub43231/)** — Google's foundational 2014 paper on zero-trust networking, which established the principle that network location should not determine access. Referenced by Julien in the VPN discussion.

- **[HashiCorp Nomad](https://developer.hashicorp.com/nomad)** — A lightweight workload orchestrator with native Consul and Vault integrations. Discussed as a simpler alternative to Kubernetes, especially for hybrid-cloud and small-team environments.

- **[Consul Service Mesh (Consul Connect)](https://developer.hashicorp.com/consul/docs/connect)** — HashiCorp's service mesh solution providing zero-trust networking through mutual TLS and identity-based authorization. Mentioned as the networking layer in the Africa hybrid-cloud project.

- **[XKCD 1168: tar](https://xkcd.com/1168/)** — The comic Julien references about the impossibility of remembering command-line flags — a humorous illustration of why security tooling needs better usability.
