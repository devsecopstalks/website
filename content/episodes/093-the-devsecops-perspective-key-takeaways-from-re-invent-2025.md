---
title: "#93 - The DevSecOps Perspective: Key Takeaways From Re:Invent 2025"
date: 2026-03-05T22:59:07+00:00
lastmod: 2026-03-05T22:59:07+00:00
episode: 93
author: "DevSecOps Talks"
participants: ["Mattias", "Andrey"]
---

Andrey and Mattias share a fast re:Invent roundup focused on AWS security. What do VPC Encryption Controls, post-quantum TLS, and org-level S3 block public access change for you? Which features should you switch on now, like ECR image signing, JWT checks at ALB, and air-gapped AWS Backup? Want simple wins you can use today?

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean hkvh9-1a62a54-pb "DEVSECOPS Talks #93 - The DevSecOps Perspective: Key Takeaways From Re:Invent 2025"  >}} 

---

<!-- Video -->

{{< youtube YtQ2svENQzk >}}

## Summary
In this episode, Andrey and Mattias deliver a security-heavy recap of AWS re:Invent 2025 announcements, while noting that Paulina is absent and wishing her a speedy recovery. Out of more than 500 releases surrounding the event, the hosts narrow the list to roughly 20 features they consider immediately actionable for security-conscious teams. The discussion covers encryption enforcement, post-quantum readiness, access control, backup resilience, detection tooling, and organization-wide guardrails, with a recurring theme that many of these features are simple "turn it on and forget it" wins.

## Key Topics

### AWS re:Invent Through a Security Lens
The hosts frame the episode as the DevSecOps Talks version of a re:Invent recap. Andrey, who also led a re:Invent recap webinar at his consultancy 5XL, jokes that despite the podcast covering development, security, and operations, this episode's selection of announcements "smells more like security only." He warns listeners that if security is not their thing, they may be slightly disappointed, but encourages them to stay tuned anyway.

During the 5XL webinar, AI was the most popular topic among attendees, with particular interest in Amazon S3 Vectors, a new storage option that lets teams store vector embeddings (numerical representations of data used by large language models) directly in S3. Andrey notes it is cost-efficient as a backbone for RAG (Retrieval-Augmented Generation) architectures, though it currently lacks hybrid search capabilities.

### VPC Encryption Control
One of the first announcements discussed is VPC encryption control for Amazon VPC, a pre-re:Invent release that lets teams audit and enforce encryption in transit within and across VPCs in a region. Andrey highlights how painful it has traditionally been to verify internal traffic encryption: teams had to set up traffic mirroring sessions, deploy instances, and use tools like Wireshark to inspect packets manually. This new feature supports two modes, monitor (to audit encryption status via VPC flow logs) and enforce (to require hardware-based AES-256 encryption), making compliance proof dramatically easier for frameworks like HIPAA, PCI DSS, and FedRAMP.

Mattias adds that compliance expectations are expanding beyond just public endpoints. Encryption inside the VPC is increasingly becoming the baseline expectation. Andrey points out a common pattern where teams terminate TLS at the load balancer but leave traffic between the load balancer and backend targets unencrypted, creating a security gap that this feature can now detect and enforce against.

### Post-Quantum Cryptography
The hosts discuss the rapid expansion of post-quantum TLS support across AWS services, now covering S3, ALB, NLB, Private CA, and others. These services use ML-KEM (Module Lattice-Based Key Encapsulation Mechanism), one of NIST's first standardized post-quantum algorithms.

Andrey explains the urgency behind this: state-level actors and other adversaries are already collecting encrypted traffic today, banking on future quantum computers being powerful enough to break current encryption standards, a strategy known as "Harvest Now, Decrypt Later." He notes that operational quantum computing appears closer than ever, with multiple perspectives suggesting it may be "around the corner." Enabling post-quantum ciphers today protects traffic against that future decryption risk, and the hosts recommend enabling it everywhere, especially for sensitive data crossing the public internet.

### S3 Security Controls and Access Management
Several S3-related updates stand out. Andrey calls out attribute-based access control (ABAC) for S3 buckets, which was previously unavailable for S3 specifically. ABAC allows access decisions based on resource tags rather than only enumerating specific IAM actions, making policies more flexible and easier to maintain. The limitation is that it must be enabled bucket by bucket, which Andrey acknowledges is necessary to avoid breaking existing security models, even if organization-wide default would be preferable.

The hosts spend particular time on S3 Block Public Access at the organization level. Previously, teams could block public access per bucket or per account. Now this can be enforced across an entire AWS Organization via an organizational policy. Andrey calls this "well overdue" and states bluntly that in 2026, there is no good reason to have a public S3 bucket. Both hosts present this as a definitive "turn it on and forget it" control.

### Backups, Air-Gapping, and Ransomware Resilience
AWS Backup receives significant attention. The hosts discuss the ability to use logically air-gapped AWS Backup Vault as a primary backup target, meaning organizations can send initial backups directly to isolated vaults without needing a secondary copy operation. This is especially relevant for teams where ransomware is on the threat model. Mattias strongly recommends enabling AWS Backup for anyone running workloads on AWS, regardless of the air-gapping feature.

Andrey emphasizes the importance of keeping backups in a separate account from production workloads, so that a compromised workload account cannot reach the recovery data. Additional backup-related announcements include KMS customer-managed key support for air-gapped vaults (providing better policy flexibility) and GuardDuty malware protection for backup artifacts, which can now scan EC2, EBS, and S3 backups for malware.

### Managed Container Image Signing from Amazon ECR
Amazon ECR now offers managed image signing, which the hosts welcome as a significant simplification. Previously, teams had to set up their own signing infrastructure (often using tools like AWS Signer or Notation). Andrey notes this requires AWS Signer availability in your region, so teams should verify regional support before relying on it.

### Dynamic Data Masking in Aurora PostgreSQL
Aurora PostgreSQL now supports dynamic data masking through the `pg_columnmask` extension, allowing teams to configure column-level masking policies so that queries return masked values instead of raw sensitive data. Mattias compares it to similar capabilities in databases like Snowflake and highlights its value when integrating with external partners who need data access without seeing PII.

When the idea of using masked production data for testing comes up, Andrey's response is direct: "Maybe don't do that." Still, both hosts agree that masking at the database layer is a strong defense-in-depth control because it prevents accidental data exposure at the API or frontend layers, where leaks more commonly occur.

### JWT Verification in ALB and Network Firewall Proxy
The hosts review two updates aimed at securing service-to-service communication and outbound traffic. JWT verification is now supported natively in AWS Application Load Balancer for machine-to-machine authentication, eliminating the need for custom Lambda-based solutions that teams previously had to build and maintain.

AWS Network Firewall has also gained a web proxy capability (in public preview). Andrey has not explored it in depth yet, but reads it as an extension that could help inspect both internet-bound traffic and traffic heading toward internal corporate data centers, potentially useful for organizations with complex hybrid network architectures.

### REST API Streaming in API Gateway
Although the episode is security-focused, the hosts include one developer-oriented announcement at Mattias's request: REST API streaming support in Amazon API Gateway. This enables progressive response payload streaming, which is particularly relevant for LLM integration where responses are generated token by token. Mattias notes that modern applications increasingly need to stream larger payloads rather than returning small JSON responses in a single shot.

### Centralized Observability with CloudWatch
CloudWatch's unified management for operational, security, and compliance data is discussed as a potentially powerful cross-account aggregation feature. Mattias sees value in having all data sources visible in one place without building custom log aggregation pipelines through Lambdas. However, he immediately warns about CloudWatch data ingest costs, noting that access logs alone generate massive data volumes and the pricing can add up quickly. The feature is in public preview.

### Control Tower, Organizations, and Guardrails at Scale
A batch of updates centers on making governance easier to adopt. These include: dedicated controls for AWS Control Tower that can be applied without a full Control Tower deployment, automatic enrollment in Control Tower, required tags via organization stack policies, Amazon Inspector organization-wide management, and billing transfer across multiple AWS Organizations (which Andrey believes is primarily aimed at AWS resellers).

Mattias states directly that everyone should use Control Tower. Andrey notes that several of these features feel like capabilities teams would have expected to exist already, but welcomes their arrival nonetheless.

### Detection and Threat Response
Detection emerges as a recurring theme throughout the episode. Specific announcements include CloudTrail Insights for data events (which requires logging data events, itself an expensive proposition), extended threat detection for EC2 and ECS in GuardDuty using AI-powered analysis, and the public preview of an AWS Security Agent designed to continuously secure applications from design to deployment.

Andrey recommends GuardDuty as a baseline "gap stopper" that works out of the box with minimal setup. He acknowledges it can become noisy over time and that teams may eventually want more sophisticated tooling, but for getting started, it delivers immediate value.

Mattias frames the broader trend well: incidents are inevitable, so what matters is how quickly teams can detect and respond. He notes that the majority of AWS's recent security announcements are focused on exactly this, adding more inspection, alerting, and detection capabilities to cloud environments.

### Identity and IAM Improvements
Several IAM-related features round out the announcements. The AWS source VPC ARN condition key for IAM policies allows teams to scope permissions based on the originating VPC, which Andrey calls "super duper useful" for attribute-based policy enforcement. AWS IAM outbound identity federation lets organizations use AWS identities to authenticate against external services via JWT, essentially using AWS as an identity platform. Mattias compares it to how teams already connect GitHub and other services to AWS in the other direction.

The new `aws login` CLI command provides short-lived credentials for IAM users, but Andrey questions whether teams should be using IAM users at all when AWS IAM Identity Center (formerly AWS SSO) is available. He frames `aws login` as better than storing static credentials locally, but still a second-best option.

AWS Secrets Manager also announced managed external secrets, allowing teams to manage secrets from external providers alongside AWS-native secrets, which the hosts flag as a useful operational convenience.

### MCP Servers and AI on AWS
The public preview of the AWS MCP (Model Context Protocol) server takes a different architectural approach from traditional locally-hosted MCP servers. Rather than running a local proxy that translates LLM requests into API calls, AWS provides remote endpoints that agents can call directly over HTTPS. This means AI agents can interact with AWS services without hosting anything locally.

Andrey notes that the IAM model is currently complex: teams need separate permissions to call the MCP server itself and additional permissions to perform the underlying AWS actions. AWS is actively working to streamline this. The hosts also mention the AWS Knowledge MCP server, which provides documentation access via the same remote pattern.

### Boris: AI for AWS Change Awareness
Toward the end of the episode, Andrey reveals a personal project he had planned to keep under wraps for a few more weeks. Boris (getboris.ai) is an AI-driven product built to solve a problem Andrey faces daily as an AWS consultant: keeping up with the constant stream of AWS announcements and figuring out which ones matter for specific customers.

Boris connects to an organization's AWS environment, understands what services and configurations are in use, and then filters the daily AWS RSS feed to surface only the announcements relevant to that particular organization, along with explanations of how each feature could benefit them. Mattias calls the concept "brilliant" and connects it to the same challenge in security, where teams are overwhelmed by a constant firehose of news and feature updates.

Andrey also announces that Boris has been accepted into the Tehnopol AI Accelerator in Tallinn, Estonia, selected from more than 100 applicants. Tehnopol is one of Estonia's leading technology parks and startup support organizations. The hosts tease a future dedicated episode about Boris now that it is out of stealth mode.

## Highlights
- **Andrey setting expectations:** "The selection of announcements smells more like security only. If security is your thing, stay tuned in. If it's not really, well, it's still interesting, but I'm just trying to manage your possible disappointment."
- **Andrey on VPC encryption:** Proving internal encryption used to require traffic mirroring, Wireshark, and manual inspection. The new VPC encryption control replaces all of that with a toggle.
- **Andrey on public S3 buckets:** "In 2026 there is no good reason to have a public S3 bucket. Just turn it on, forget about it."
- **Andrey on masked data for testing:** When the idea comes up, his response is blunt: "Maybe don't do that."
- **Mattias on detection:** "What you can control is how you react when it's going to happen. Detection is really where I put effort." He argues teams should enable detection features "as fast as possible."
- **Mattias on Control Tower:** "Everybody should use Control Tower." No hedging.
- **Andrey on Boris:** Reveals that his AI startup watches the AWS release feed and tells each customer which announcements actually matter to their environment. Mattias's reaction: "This is brilliant."
- **Accelerator news:** Boris accepted into the Tehnopol AI Accelerator in Tallinn, selected from more than 100 companies, announced live on the episode.

## Resources
- [AWS VPC Encryption Controls announcement](https://aws.amazon.com/blogs/aws/introducing-vpc-encryption-controls-enforce-encryption-in-transit-within-and-across-vpcs-in-a-region/) — AWS blog post detailing the monitor and enforce modes for VPC encryption in transit.
- [AWS Post-Quantum Cryptography overview](https://aws.amazon.com/security/post-quantum-cryptography/) — AWS's landing page explaining their post-quantum strategy and which services support ML-KEM.
- [Harvest Now, Decrypt Later explained (Palo Alto Networks)](https://www.paloaltonetworks.com/cyberpedia/harvest-now-decrypt-later-hndl) — Clear explanation of the HNDL threat model that motivates post-quantum adoption.
- [AWS re:Invent 2025 Security Announcements (HanaByte)](https://www.hanabyte.com/aws-reinvent-2025-security-announcements/) — Comprehensive third-party recap of all security-related re:Invent 2025 announcements.
- [re:Invent 2025 Security Recap (Chris Farris)](https://www.chrisfarris.com/post/reinvent2025/) — Independent security-focused re:Invent recap with commentary on practical implications.
- [Dynamic Data Masking for Aurora PostgreSQL](https://aws.amazon.com/blogs/database/protect-sensitive-data-with-dynamic-data-masking-for-amazon-aurora-postgresql/) — AWS blog on setting up `pg_columnmask` for column-level data masking.
- [Understanding IAM for Managed AWS MCP Servers](https://aws.amazon.com/blogs/security/understanding-iam-for-managed-aws-mcp-servers/) — AWS Security blog explaining the dual-permission model for MCP server access.
- [Tehnopol AI Accelerator](https://ai.tehnopol.ee/en/) — The AI Accelerator program in Tallinn, Estonia, that accepted Boris into its latest batch.

Now I have enough research. Let me write the improved article.

## Summary
In this episode, Andrey and Mattias deliver a security-heavy recap of AWS re:Invent 2025 announcements, while noting that Paulina is absent and wishing her a speedy recovery. Out of the 500+ releases surrounding re:Invent, they narrow the list down to roughly 20 features that security-conscious teams can act on today — covering encryption, access control, detection, backups, container security, and organization-wide guardrails. Along the way, Andrey reveals a new AI-powered product called Boris that watches the AWS release firehose so you don't have to.

## Key Topics

### AWS re:Invent Through a Security Lens
The hosts frame the episode as the DevSecOps Talks version of a re:Invent recap, complementing a FivexL webinar held the previous month. Despite the podcast's name covering development, security, and operations, the selected announcements lean heavily toward security. Andrey is upfront about it: if security is your thing, stay tuned; otherwise, manage your expectations.

At the FivexL webinar, attendees were asked to prioritize areas of interest across compute, security, and networking. AI dominated the conversation, and people were also curious about Amazon S3 Vectors — a new S3 storage class purpose-built for vector embeddings used in RAG (Retrieval-Augmented Generation) architectures that power LLM applications. It is cost-efficient but lacks hybrid search at this stage.

### VPC Encryption and Post-Quantum Readiness
One of the first and most praised announcements is **VPC Encryption Control for Amazon VPC**, a pre-re:Invent release that lets teams audit and enforce encryption in transit within and across VPCs. The hosts highlight how painful it used to be to verify internal traffic encryption — typically requiring traffic mirroring, spinning up instances, and inspecting packets with tools like Wireshark. This feature offers two modes: *monitor* mode to audit encryption status via VPC flow logs, and *enforce* mode to block unencrypted resources from attaching to the VPC.

Mattias adds that compliance expectations are expanding. It used to be enough to encrypt traffic over public endpoints, but the bar is moving toward encryption everywhere, including inside the VPC. The hosts also call out a common pattern: offloading SSL at the load balancer and leaving traffic to targets unencrypted. VPC encryption control helps catch exactly this kind of blind spot.

The discussion then shifts to **post-quantum cryptography (PQC)** support rolling out across AWS services including S3, ALB, NLB, AWS Private CA, KMS, ACM, and Secrets Manager. AWS now supports ML-KEM (Module Lattice-Based Key Encapsulation Mechanism), a NIST-standardized post-quantum algorithm, along with ML-DSA (Module Lattice-Based Digital Signature Algorithm) for Private CA certificates.

The rationale: state-level actors are already recording encrypted traffic today in a "harvest now, decrypt later" strategy, betting that future quantum computers will crack current encryption. Andrey notes that operational quantum computing feels closer than ever, making it worthwhile to enable post-quantum protections now — especially for sensitive data traversing public networks.

### S3 Security Controls and Access Management
Several S3-related updates stand out. **Attribute-Based Access Control (ABAC) for S3** allows access decisions based on resource tags rather than only enumerating specific actions in policies. This is a powerful way to scope permissions — for example, granting access to all buckets tagged with a specific project — though it must be enabled on a per-bucket basis, which the hosts note is a drawback even if necessary to avoid breaking existing security models.

The bigger crowd-pleaser is **S3 Block Public Access at the organization level**. Previously available at the bucket and account level, this control can now be applied across an entire AWS Organization. The hosts call it well overdue and present it as the ultimate "turn it on and forget it" control: in 2026, there is no good reason to have a public S3 bucket.

### Container Image Signing
**Amazon ECR Managed Image Signing** is a welcome addition. ECR now provides a managed service for signing container images, leveraging AWS Signer for key management and certificate lifecycle. Once configured with a signing rule, ECR automatically signs images as they are pushed. This eliminates the operational overhead of setting up and maintaining container image signing infrastructure — previously a significant barrier for teams wanting to verify image provenance in their supply chains.

### Backups, Air-Gapping, and Ransomware Resilience
AWS Backup gets significant attention. The hosts discuss **air-gapped AWS Backup Vault support as a primary backup target**, positioning it as especially relevant for teams where ransomware is on the threat list. These logically air-gapped vaults live in an Amazon-owned account and are locked by default with a compliance vault lock to ensure immutability.

The strong recommendation: enable AWS Backup for any important data, and keep backups isolated in a separate account from your workloads. If an attacker compromises your production account, they should not be able to reach your recovery copies. Related updates include **KMS customer-managed key support for air-gapped vaults** for better encryption flexibility, and **GuardDuty Malware Protection for AWS Backup**, which can scan backup artifacts for malware before restoration.

### Data Protection in Databases
**Dynamic data masking in Aurora PostgreSQL** draws praise from both hosts. Using the new `pg_columnmask` extension, teams can configure column-level masking policies so that queries return masked data instead of actual values — for example, replacing credit card numbers with wildcards. The data in the database remains unmodified; masking happens at query time based on user roles.

Mattias compares it to capabilities already present in databases like Snowflake and highlights how useful it is when sharing data with external partners or other teams. When the idea of using masked production data for testing comes up, the hosts gently push back — don't do that — but both agree that masking at the database layer is a strong control because it reduces the risk of accidental data exposure through APIs or front-end applications.

### Identity, IAM, and Federation Improvements
The episode covers several IAM-related features. **AWS IAM Outbound Identity Federation** allows federating AWS identities to external services via JWT, effectively letting you use AWS identity as a platform for authenticating to third-party services — similar to how you connect GitHub or other services to AWS today, but in the other direction.

The **AWS Login CLI command** provides short-lived credentials for IAM users who don't have AWS IAM Identity Center (SSO) configured. The hosts see it as a better alternative than storing static IAM credentials locally, but also question whether teams should still be relying on IAM users at all — their recommendation is to set up IAM Identity Center and move on.

The **AWS Source VPC ARN condition key** gets particular enthusiasm. It allows IAM policies to check which VPC a request originated from, enabling conditions like "allow this action only if the request comes from this VPC." For teams doing attribute-based access control in IAM, this is a significant addition.

**AWS Secrets Manager Managed External Secrets** is another useful feature that removes a common operational burden. Previously, rotating third-party SaaS credentials required writing and maintaining custom Lambda functions. Managed external secrets provides built-in rotation for partner integrations — Salesforce, BigID, and Snowflake at launch — with no Lambda functions needed.

### Better Security at the Network and Service Layer
**JWT verification in AWS Application Load Balancer** simplifies machine-to-machine and service-to-service authentication. Teams previously had to roll their own Lambda-based JWT verification; now it is supported out of the box. The recommendation is straightforward: drop the Lambda and use the built-in capability.

**AWS Network Firewall Proxy** is in public preview. While the hosts have not explored it deeply, their read is that it could help with more advanced network inspection scenarios — not just outgoing internet traffic through NAT gateways, but potentially also traffic heading toward internal corporate data centers.

### Developer-Oriented: REST API Streaming
Although the episode is mainly security-focused, the hosts include **REST API streaming in Amazon API Gateway** as a nod to developers. This enables progressive response payload streaming, which is especially relevant for LLM use cases where streaming tokens to clients is the expected interaction pattern. Mattias notes that applications are moving beyond small JSON payloads — streaming is becoming table stakes as data volumes grow.

### Centralized Observability and Detection
**CloudWatch unified management** for operational, security, and compliance data promises cross-account visibility from a single pane of glass, without requiring custom log aggregation pipelines built from Lambdas and glue code. The hosts are optimistic but immediately flag the cost: CloudWatch data ingest pricing can escalate quickly when dealing with high-volume sources like access logs. Deep pockets may be required.

Detection is a recurring theme throughout the episode. The hosts discuss **CloudTrail Insights for data events** (useful if you are already logging data-plane events — another deep-pockets feature), **extended threat detection for EC2 and ECS in GuardDuty** using AI-powered analysis to correlate security signals across network activity, runtime behavior, and API calls, and the **public preview of AWS Security Agent** for automated security investigation.

On GuardDuty specifically, the recommendation is clear: if you don't have it enabled, go enable it — it gives you a good baseline that works out of the box across your services with minimal setup. You can always graduate to more sophisticated tooling later, but GuardDuty is the gap-stopper you start with.

Mattias drives the broader point home: incidents are inevitable, and what you can control is how fast you detect and respond. AWS is clearly investing heavily in the detection side, and teams should enable these capabilities as fast as possible.

### Control Tower, Organizations, and Guardrails at Scale
Several updates make governance easier to adopt at scale:
- **Dedicated controls for AWS Control Tower** without requiring a full Control Tower deployment — you can now use Control Tower guardrails à la carte.
- **Automatic enrollment in Control Tower** — a feature the hosts feel should have existed already.
- **Required tags in Organizations stack policies** — enforcing tagging standards at the organization level.
- **Amazon Inspector organization-wide management** — centralized vulnerability scanning across all accounts.
- **Billing transfer for AWS Organizations** — useful for AWS resellers managing multiple organizations.
- **Delete protection for CloudWatch Log Groups** — a small but important safeguard.

Mattias says plainly: everyone should use Control Tower.

### MCP Servers and AWS's Evolving AI Approach
The conversation shifts to the **public preview of AWS MCP (Model Context Protocol) servers**. Unlike traditional locally-hosted MCP servers that proxy LLM requests to API calls, AWS is taking a different approach with remote, fully managed MCP servers hosted on AWS infrastructure. These allow AI agents and AI-native IDEs to interact with AWS services over HTTPS without running anything locally.

AWS launched four managed MCP servers — AWS, EKS, ECS, and SageMaker — that consolidate capabilities like AWS documentation access, API execution across 15,000+ AWS APIs, and pre-built agent workflows. However, the IAM model is still being worked out: you currently need separate permissions to call the MCP server and to perform the underlying AWS actions it invokes. The hosts treat this as interesting but still evolving.

### Boris: AI for AWS Change Awareness
Toward the end of the episode, Andrey reveals a personal project: **Boris** ([getboris.ai](https://www.getboris.ai/)), an AI-powered DevOps teammate he has been building. Boris connects to the systems an engineering team already uses and provides evidence-based answers and operational automation.

The specific feature Andrey has been working on takes the AWS RSS feed — where new announcements land daily — and cross-references it against what a customer actually has running in their AWS Organization. Instead of manually sifting through hundreds of releases, Boris sends a digest highlighting only the announcements relevant to your environment and explaining how you would benefit.

Mattias immediately connects this to the same problem in security: teams are overwhelmed by the constant flow of feature updates and vulnerability news. Having an AI that filters and contextualizes that information is, in his words, "brilliant."

Andrey also announces that Boris has been accepted into the **Tehnopol AI Accelerator** in Tallinn, Estonia — a program run by the Tehnopol Science and Business Park that supports early-stage AI startups — selected from more than 100 companies.

## Highlights
- **Setting expectations:** "The selection of announcements smells more like security only. If security is your thing, stay tuned in. If it's not really, well, it's still interesting, but I'm just trying to manage your possible disappointment."
- **On VPC encryption control:** The hosts describe how proving internal encryption used to require traffic mirroring, Wireshark, and significant pain — this feature makes it a configuration toggle.
- **On public S3 buckets:** "In 2026 there is no good reason to have a public S3 bucket. Just turn it on and forget about it."
- **On production data for testing:** When someone floats using masked production data for testing — "Maybe don't do that."
- **On detection over prevention:** "You cannot really prevent something from happening in your environment. What you can control is how you react when it's going to happen. Detection is really where I put effort."
- **On Boris:** When Andrey describes how Boris watches the AWS release feed and tells you which announcements actually matter for your environment, Mattias's reaction: "This is brilliant."
- **On getting started with AWS security:** "If you are a startup building on AWS and compliance is important, it's quite easy to get it working. All the building blocks and tools are available for you to do the right things."

## Resources
- [Introducing VPC Encryption Controls](https://aws.amazon.com/blogs/aws/introducing-vpc-encryption-controls-enforce-encryption-in-transit-within-and-across-vpcs-in-a-region/) — AWS blog post explaining monitor and enforce modes for VPC encryption in transit.
- [AWS Post-Quantum Cryptography](https://aws.amazon.com/security/post-quantum-cryptography/) — AWS overview of post-quantum cryptography migration, including ML-KEM support across S3, ALB, NLB, KMS, and Private CA.
- [S3 Block Public Access Organization-Level Enforcement](https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-s3-block-public-access-organization-level-enforcement/) — Announcement for enforcing S3 public access blocks across an entire AWS Organization.
- [Amazon ECR Managed Container Image Signing](https://aws.amazon.com/blogs/containers/streamline-container-image-signatures-with-amazon-ecr-managed-signing/) — Guide to setting up managed image signing with ECR and AWS Signer.
- [GuardDuty Extended Threat Detection for EC2 and ECS](https://aws.amazon.com/blogs/aws/amazon-guardduty-adds-extended-threat-detection-for-amazon-ec2-and-amazon-ecs/) — How GuardDuty uses AI/ML to correlate security signals and detect multi-stage attacks on compute workloads.
- [Dynamic Data Masking for Aurora PostgreSQL](https://aws.amazon.com/blogs/database/protect-sensitive-data-with-dynamic-data-masking-for-amazon-aurora-postgresql/) — How to configure column-level data masking with the pg_columnmask extension.
- [Understanding IAM for Managed AWS MCP Servers](https://aws.amazon.com/blogs/security/understanding-iam-for-managed-aws-mcp-servers/) — AWS Security Blog post explaining the IAM permission model for remote MCP servers.
- [B.O.R.I.S — Your AI DevOps Teammate](https://www.getboris.ai/) — The AI-powered product discussed in the episode that tracks AWS announcements and matches them to your environment.

Now I have enough research. Let me write the improved article.

## Summary
In this episode, Andrey and Mattias deliver a security-heavy recap of AWS re:Invent 2025 announcements, while noting that Paulina is absent and wishing her a speedy recovery. Out of the 500+ releases surrounding re:Invent, they narrow the list down to roughly 20 features that security-conscious teams can act on today — covering encryption, access control, detection, backups, container security, and organization-wide guardrails. Along the way, Andrey reveals a new AI-powered product called Boris that watches the AWS release firehose so you don't have to.

## Key Topics

### AWS re:Invent Through a Security Lens
The hosts frame the episode as the DevSecOps Talks version of a re:Invent recap, complementing a FivexL webinar held the previous month. Despite the podcast's name covering development, security, and operations, the selected announcements lean heavily toward security. Andrey is upfront about it: if security is your thing, stay tuned; otherwise, manage your expectations.

At the FivexL webinar, attendees were asked to prioritize areas of interest across compute, security, and networking. AI dominated the conversation, and people were also curious about Amazon S3 Vectors — a new S3 storage class purpose-built for vector embeddings used in RAG (Retrieval-Augmented Generation) architectures that power LLM applications. It is cost-efficient but lacks hybrid search at this stage.

### VPC Encryption and Post-Quantum Readiness
One of the first and most praised announcements is **VPC Encryption Control for Amazon VPC**, a pre-re:Invent release that lets teams audit and enforce encryption in transit within and across VPCs. The hosts highlight how painful it used to be to verify internal traffic encryption — typically requiring traffic mirroring, spinning up instances, and inspecting packets with tools like Wireshark. This feature offers two modes: *monitor* mode to audit encryption status via VPC flow logs, and *enforce* mode to block unencrypted resources from attaching to the VPC.

Mattias adds that compliance expectations are expanding. It used to be enough to encrypt traffic over public endpoints, but the bar is moving toward encryption everywhere, including inside the VPC. The hosts also call out a common pattern: offloading SSL at the load balancer and leaving traffic to targets unencrypted. VPC encryption control helps catch exactly this kind of blind spot.

The discussion then shifts to **post-quantum cryptography (PQC)** support rolling out across AWS services including S3, ALB, NLB, AWS Private CA, KMS, ACM, and Secrets Manager. AWS now supports ML-KEM (Module Lattice-Based Key Encapsulation Mechanism), a NIST-standardized post-quantum algorithm, along with ML-DSA (Module Lattice-Based Digital Signature Algorithm) for Private CA certificates.

The rationale: state-level actors are already recording encrypted traffic today in a "harvest now, decrypt later" strategy, betting that future quantum computers will crack current encryption. Andrey notes that operational quantum computing feels closer than ever, making it worthwhile to enable post-quantum protections now — especially for sensitive data traversing public networks.

### S3 Security Controls and Access Management
Several S3-related updates stand out. **Attribute-Based Access Control (ABAC) for S3** allows access decisions based on resource tags rather than only enumerating specific actions in policies. This is a powerful way to scope permissions — for example, granting access to all buckets tagged with a specific project — though it must be enabled on a per-bucket basis, which the hosts note is a drawback even if necessary to avoid breaking existing security models.

The bigger crowd-pleaser is **S3 Block Public Access at the organization level**. Previously available at the bucket and account level, this control can now be applied across an entire AWS Organization. The hosts call it well overdue and present it as the ultimate "turn it on and forget it" control: in 2026, there is no good reason to have a public S3 bucket.

### Container Image Signing
**Amazon ECR Managed Image Signing** is a welcome addition. ECR now provides a managed service for signing container images, leveraging AWS Signer for key management and certificate lifecycle. Once configured with a signing rule, ECR automatically signs images as they are pushed. This eliminates the operational overhead of setting up and maintaining container image signing infrastructure — previously a significant barrier for teams wanting to verify image provenance in their supply chains.

### Backups, Air-Gapping, and Ransomware Resilience
AWS Backup gets significant attention. The hosts discuss **air-gapped AWS Backup Vault support as a primary backup target**, positioning it as especially relevant for teams where ransomware is on the threat list. These logically air-gapped vaults live in an Amazon-owned account and are locked by default with a compliance vault lock to ensure immutability.

The strong recommendation: enable AWS Backup for any important data, and keep backups isolated in a separate account from your workloads. If an attacker compromises your production account, they should not be able to reach your recovery copies. Related updates include **KMS customer-managed key support for air-gapped vaults** for better encryption flexibility, and **GuardDuty Malware Protection for AWS Backup**, which can scan backup artifacts for malware before restoration.

### Data Protection in Databases
**Dynamic data masking in Aurora PostgreSQL** draws praise from both hosts. Using the new `pg_columnmask` extension, teams can configure column-level masking policies so that queries return masked data instead of actual values — for example, replacing credit card numbers with wildcards. The data in the database remains unmodified; masking happens at query time based on user roles.

Mattias compares it to capabilities already present in databases like Snowflake and highlights how useful it is when sharing data with external partners or other teams. When the idea of using masked production data for testing comes up, the hosts gently push back — don't do that — but both agree that masking at the database layer is a strong control because it reduces the risk of accidental data exposure through APIs or front-end applications.

### Identity, IAM, and Federation Improvements
The episode covers several IAM-related features. **AWS IAM Outbound Identity Federation** allows federating AWS identities to external services via JWT, effectively letting you use AWS identity as a platform for authenticating to third-party services — similar to how you connect GitHub or other services to AWS today, but in the other direction.

The **AWS Login CLI command** provides short-lived credentials for IAM users who don't have AWS IAM Identity Center (SSO) configured. The hosts see it as a better alternative than storing static IAM credentials locally, but also question whether teams should still be relying on IAM users at all — their recommendation is to set up IAM Identity Center and move on.

The **AWS Source VPC ARN condition key** gets particular enthusiasm. It allows IAM policies to check which VPC a request originated from, enabling conditions like "allow this action only if the request comes from this VPC." For teams doing attribute-based access control in IAM, this is a significant addition.

**AWS Secrets Manager Managed External Secrets** is another useful feature that removes a common operational burden. Previously, rotating third-party SaaS credentials required writing and maintaining custom Lambda functions. Managed external secrets provides built-in rotation for partner integrations — Salesforce, BigID, and Snowflake at launch — with no Lambda functions needed.

### Better Security at the Network and Service Layer
**JWT verification in AWS Application Load Balancer** simplifies machine-to-machine and service-to-service authentication. Teams previously had to roll their own Lambda-based JWT verification; now it is supported out of the box. The recommendation is straightforward: drop the Lambda and use the built-in capability.

**AWS Network Firewall Proxy** is in public preview. While the hosts have not explored it deeply, their read is that it could help with more advanced network inspection scenarios — not just outgoing internet traffic through NAT gateways, but potentially also traffic heading toward internal corporate data centers.

### Developer-Oriented: REST API Streaming
Although the episode is mainly security-focused, the hosts include **REST API streaming in Amazon API Gateway** as a nod to developers. This enables progressive response payload streaming, which is especially relevant for LLM use cases where streaming tokens to clients is the expected interaction pattern. Mattias notes that applications are moving beyond small JSON payloads — streaming is becoming table stakes as data volumes grow.

### Centralized Observability and Detection
**CloudWatch unified management** for operational, security, and compliance data promises cross-account visibility from a single pane of glass, without requiring custom log aggregation pipelines built from Lambdas and glue code. The hosts are optimistic but immediately flag the cost: CloudWatch data ingest pricing can escalate quickly when dealing with high-volume sources like access logs. Deep pockets may be required.

Detection is a recurring theme throughout the episode. The hosts discuss **CloudTrail Insights for data events** (useful if you are already logging data-plane events — another deep-pockets feature), **extended threat detection for EC2 and ECS in GuardDuty** using AI-powered analysis to correlate security signals across network activity, runtime behavior, and API calls, and the **public preview of AWS Security Agent** for automated security investigation.

On GuardDuty specifically, the recommendation is clear: if you don't have it enabled, go enable it — it gives you a good baseline that works out of the box across your services with minimal setup. You can always graduate to more sophisticated tooling later, but GuardDuty is the gap-stopper you start with.

Mattias drives the broader point home: incidents are inevitable, and what you can control is how fast you detect and respond. AWS is clearly investing heavily in the detection side, and teams should enable these capabilities as fast as possible.

### Control Tower, Organizations, and Guardrails at Scale
Several updates make governance easier to adopt at scale:
- **Dedicated controls for AWS Control Tower** without requiring a full Control Tower deployment — you can now use Control Tower guardrails à la carte.
- **Automatic enrollment in Control Tower** — a feature the hosts feel should have existed already.
- **Required tags in Organizations stack policies** — enforcing tagging standards at the organization level.
- **Amazon Inspector organization-wide management** — centralized vulnerability scanning across all accounts.
- **Billing transfer for AWS Organizations** — useful for AWS resellers managing multiple organizations.
- **Delete protection for CloudWatch Log Groups** — a small but important safeguard.

Mattias says plainly: everyone should use Control Tower.

### MCP Servers and AWS's Evolving AI Approach
The conversation shifts to the **public preview of AWS MCP (Model Context Protocol) servers**. Unlike traditional locally-hosted MCP servers that proxy LLM requests to API calls, AWS is taking a different approach with remote, fully managed MCP servers hosted on AWS infrastructure. These allow AI agents and AI-native IDEs to interact with AWS services over HTTPS without running anything locally.

AWS launched four managed MCP servers — AWS, EKS, ECS, and SageMaker — that consolidate capabilities like AWS documentation access, API execution across 15,000+ AWS APIs, and pre-built agent workflows. However, the IAM model is still being worked out: you currently need separate permissions to call the MCP server and to perform the underlying AWS actions it invokes. The hosts treat this as interesting but still evolving.

### Boris: AI for AWS Change Awareness
Toward the end of the episode, Andrey reveals a personal project: **Boris** ([getboris.ai](https://www.getboris.ai/)), an AI-powered DevOps teammate he has been building. Boris connects to the systems an engineering team already uses and provides evidence-based answers and operational automation.

The specific feature Andrey has been working on takes the AWS RSS feed — where new announcements land daily — and cross-references it against what a customer actually has running in their AWS Organization. Instead of manually sifting through hundreds of releases, Boris sends a digest highlighting only the announcements relevant to your environment and explaining how you would benefit.

Mattias immediately connects this to the same problem in security: teams are overwhelmed by the constant flow of feature updates and vulnerability news. Having an AI that filters and contextualizes that information is, in his words, "brilliant."

Andrey also announces that Boris has been accepted into the **Tehnopol AI Accelerator** in Tallinn, Estonia — a program run by the Tehnopol Science and Business Park that supports early-stage AI startups — selected from more than 100 companies.

## Highlights
- **Setting expectations:** "The selection of announcements smells more like security only. If security is your thing, stay tuned in. If it's not really, well, it's still interesting, but I'm just trying to manage your possible disappointment."
- **On VPC encryption control:** The hosts describe how proving internal encryption used to require traffic mirroring, Wireshark, and significant pain — this feature makes it a configuration toggle.
- **On public S3 buckets:** "In 2026 there is no good reason to have a public S3 bucket. Just turn it on and forget about it."
- **On production data for testing:** When someone floats using masked production data for testing — "Maybe don't do that."
- **On detection over prevention:** "You cannot really prevent something from happening in your environment. What you can control is how you react when it's going to happen. Detection is really where I put effort."
- **On Boris:** When Andrey describes how Boris watches the AWS release feed and tells you which announcements actually matter for your environment, Mattias's reaction: "This is brilliant."
- **On getting started with AWS security:** "If you are a startup building on AWS and compliance is important, it's quite easy to get it working. All the building blocks and tools are available for you to do the right things."

## Resources
- [Introducing VPC Encryption Controls](https://aws.amazon.com/blogs/aws/introducing-vpc-encryption-controls-enforce-encryption-in-transit-within-and-across-vpcs-in-a-region/) — AWS blog post explaining monitor and enforce modes for VPC encryption in transit.
- [AWS Post-Quantum Cryptography](https://aws.amazon.com/security/post-quantum-cryptography/) — AWS overview of post-quantum cryptography migration, including ML-KEM support across S3, ALB, NLB, KMS, and Private CA.
- [S3 Block Public Access Organization-Level Enforcement](https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-s3-block-public-access-organization-level-enforcement/) — Announcement for enforcing S3 public access blocks across an entire AWS Organization.
- [Amazon ECR Managed Container Image Signing](https://aws.amazon.com/blogs/containers/streamline-container-image-signatures-with-amazon-ecr-managed-signing/) — Guide to setting up managed image signing with ECR and AWS Signer.
- [GuardDuty Extended Threat Detection for EC2 and ECS](https://aws.amazon.com/blogs/aws/amazon-guardduty-adds-extended-threat-detection-for-amazon-ec2-and-amazon-ecs/) — How GuardDuty uses AI/ML to correlate security signals and detect multi-stage attacks on compute workloads.
- [Dynamic Data Masking for Aurora PostgreSQL](https://aws.amazon.com/blogs/database/protect-sensitive-data-with-dynamic-data-masking-for-amazon-aurora-postgresql/) — How to configure column-level data masking with the pg_columnmask extension.
- [Understanding IAM for Managed AWS MCP Servers](https://aws.amazon.com/blogs/security/understanding-iam-for-managed-aws-mcp-servers/) — AWS Security Blog post explaining the IAM permission model for remote MCP servers.
- [B.O.R.I.S — Your AI DevOps Teammate](https://www.getboris.ai/) — The AI-powered product discussed in the episode that tracks AWS announcements and matches them to your environment.
