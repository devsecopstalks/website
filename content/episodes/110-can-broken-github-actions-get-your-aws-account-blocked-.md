---
title: "#110 - Can Broken GitHub Actions Get Your AWS Account Blocked?"
date: 2026-09-14T12:00:00+01:00
lastmod: 2026-09-14T12:00:00+01:00
episode: 110
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/110/"
---

Why would a security improvement break a working deployment? Andrey questions the operational cost of GitHub’s OIDC change, while Mattias explains how repository renames can break AWS access. The hosts share a real incident involving a blocked account and discuss how to prepare for the change.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean j2kez-1b58ea3-pb "DEVSECOPS Talks #110 - Can Broken GitHub Actions Get Your AWS Account Blocked?"  >}}

---

<!-- Video -->

## Summary {#summary}

Summer break is over, and the hosts come back with a change that quietly broke things while everyone was on holiday. GitHub now bakes immutable owner and repository IDs into the `sub` claim of its Actions OIDC tokens — and Andrey's verdict is blunt: the attack it prevents "feels theoretical to me," but the headache of updating every IAM trust policy is not. Worse, the failure mode isn't just a red pipeline. Andrey explains how failed `AssumeRoleWithWebIdentity` calls, coming from GitHub runner IPs that sit on Azure ranges already flagged by threat-intelligence vendors, can look enough like a compromised account that AWS opens an abuse case — and the hosts have seen accounts get blocked over it.

## Key Topics {#key-topics}

### OIDC in 60 seconds: why you shouldn't be storing AWS keys in GitHub secrets {#oidc-basics}

Andrey lays the foundation before getting to the change, because the whole problem only makes sense if you know how the trust works.

CI needs a **worker** — a piece of compute that executes your job. Either you run self-hosted runners, or you use the ones your provider offers. When a GitHub-hosted runner needs to do something in your AWS account — run Terraform, push an image, call an API — it needs credentials.

The bad option: create a static IAM user, put the access keys in GitHub secrets, pass them as environment variables. As the hosts put it — you *can* do it, you just shouldn't.

The better option is **OIDC (OpenID Connect)** web federation. You create an IAM role whose trust policy says, in effect: *a token issued by GitHub, for this repository, may assume me*. GitHub's OIDC provider mints a short-lived token that identifies the workflow, the runner calls `sts:AssumeRoleWithWebIdentity` with it, and the token itself is the identity. No long-lived secret is shared with the runner at all. The same pattern works on GitLab, and on Azure and Google Cloud.

The condition in that trust policy matches on the token's **subject (`sub`) claim**, historically something like `repo:my-org/my-repo:ref:refs/heads/main`. Andrey's warning is about leaving that condition too loose — his shorthand on the mic was that you *can* put a `*` in there and then "every GitHub worker in the world will be able to assume it."

The mechanics are narrower than that, and worth getting right. AWS won't let you ship the worst case: when GitHub's OIDC provider is the trusted principal, IAM checks on create and update that a `token.actions.githubusercontent.com:sub` condition exists and that its value isn't solely a wildcard, and rejects the policy otherwise. A *scoped* wildcard is still legal and still scoped — but write it against the right format. `repo:my-org/*:*` is the **legacy-format** version: it trusts every repository in your organization and nobody else's, and it only keeps working while those repositories are still issuing legacy subjects. Once a repository is on immutable subjects, the organization segment carries the owner ID too, so the immutable-format equivalent is `repo:my-org@123456/*:*` — and the legacy pattern stops matching that repository entirely. Same trap as the rename story below, just with a wildcard instead of an exact string. The real danger is the one Andrey's point lands on: every segment of the subject you leave unpinned is a segment you're trusting blindly, and AWS's own guidance is explicit that a `sub` condition not limited to a specific organization or repository lets GitHub Actions from outside your control assume the role. Pin the organization and repository, and narrow further by branch or environment where you can.

### What GitHub actually changed {#the-change}

Andrey reads the announcement on air. GitHub Actions OIDC tokens now include **immutable identities** in the default `sub` claim for new repositories.

The old format used only mutable names:

```
repo:octocat/my-repo:ref:refs/heads/main
```

The new format appends the numeric owner ID and repository ID, separated by `@`:

```
repo:octocat@123456/my-repo@456789:ref:refs/heads/main
```

GitHub's rationale: the OIDC specification says subject claims should be locally unique and never reassigned. If a repository or organization name is recycled, whoever claims the freed name could mint tokens carrying the same `sub` — and any cloud trust policy still matching on that string would hand them a role.

The rollout details matter more than the format. All of them apply to **GitHub.com only** — the changelog states the change does not affect GitHub Enterprise Server:

- **GitHub.com repositories created after July 15, 2026** automatically use the new immutable format.
- **Renames and transfers on GitHub.com after July 15, 2026** also switch to the new format.
- **Existing repositories are unaffected** unless an admin explicitly opts in, through the OIDC settings UI or the REST API.
- **GHES is out of scope.** If your workflows run on Enterprise Server, nothing changes for them.

A correction on the dates the hosts wrestled with on the mic: the changelog went out on **April 23, 2026**, not the 20th — and it picked up an editor's note on **June 10, 2026**, which is likely the "June" date Andrey half-remembered. That note is worth knowing about: the delimiter between the name and the ID was originally documented as `-` and is now `@`, chosen because `@` can't appear in a GitHub username or repository name. If you wrote a trust policy against the earlier documentation, check it.

One more detail from the docs the hosts didn't cover: once a repository is on immutable subjects, the owner ID and repo ID are **always** present in the `repo` segment of `sub`, even if you customize which claims go into it. You can't opt them back out.

### Andrey's objection: a theoretical threat, a very real migration {#is-it-worth-it}

Andrey isn't convinced the trade is worth it. Working through the squatting scenario live, he points out that for someone to impersonate Mattias' repository, the organization name has to match too — so you'd somehow already need to be inside Mattias' organization.

(The scenario GitHub is actually guarding against is namespace *recycling*: an org or user account gets deleted or renamed, the name becomes available, and someone else registers it. Rare — but by design, a `sub` claim built on names can't tell the difference.)

His analogy is pointed: this is like shortening the lifetime of SSL certificates to stop certificate theft. "No one ever steals SSL certificate nowadays," he says — you've created a lot of headache for everyone to close a hole nobody was walking through. From a pure security standpoint it's a good thing. But now you have to go update all your roles.

The analogy is worth a technical caveat, though. Certificates aren't secret — the server hands its certificate to every client in the TLS handshake, so there is nothing to steal. What short lifetimes actually limit is the window in which a **compromised private key** or a **mis-issued certificate** stays valid, and that matters because revocation has never worked reliably at internet scale. [Let's Encrypt's own explanation](https://letsencrypt.org/docs/cert-lifetimes/) puts exactly those two reasons first, ahead of the push toward automation. So the comparison is a rhetorical shortcut rather than a matched case. The complaint underneath it still stands on its own terms: broad operational cost imposed now, against an attack path that looks remote — that is Andrey's verdict on the OIDC change, and it doesn't need the certificate parallel to hold up.

He's harder on the *implementation* than on the idea. It's a breaking change shipped into a half state: some of your repositories will have the new format, some won't, and which is which depends on when each one was created, renamed, or transferred. You can opt in across the board — and, as Andrey notes drily, break all your CI for all your repositories at once. Maybe that's a good idea. Maybe not.

### How it bites: rename a repository, break your pipeline {#how-it-bites}

Mattias walks through the concrete failure. You rename a GitHub.com repository — an ordinary, low-drama thing to do. The rename flips that repository to the new subject format. Your IAM trust policy still matches the old string. The `AssumeRoleWithWebIdentity` call fails, and the runner can no longer assume roles whose trust policies no longer match the repository's subject.

Note the scope: it's the roles with stale conditions that lock you out, not your whole account. A role whose `sub` condition still matches — or one the workflow reaches some other way — stays assumable. That partial blast radius is part of what makes the incident confusing to read at 9 a.m.: some jobs break, some don't.

Everything the affected role was doing now fails: uploading artifacts, pushing images, writing to S3, invoking Bedrock models. And if those jobs run on every pull request, you don't get one failure — you get a steady stream of access-denied events, on repeat, for as long as it takes someone to notice.

### The part nobody sees coming: AWS decides you've been hacked {#aws-fraud-signal}

This is where the episode stops being a changelog summary. Mattias asks whether anything *else* can happen when things start failing in AWS, and Andrey has the story.

A number of security firms list Azure IP ranges as fraudulent — GitHub-hosted runners sit on Azure infrastructure, and there have been enough cases of stolen GitHub credentials being used to run malicious workloads on those runners that the addresses ended up on reputation blocklists. GitHub documents this behavior itself: third-party threat-intelligence services and firewall vendors may flag its runner IPs as malicious or suspicious, and because the infrastructure is shared, other users' activity influences those reputation scores. If you run any kind of intrusion detection, you've probably already seen false positives from your own runners. Andrey has seen it across multiple customers.

Now stack the two together. Calls arrive from an IP with a bad reputation, repeatedly failing `AssumeRoleWithWebIdentity` — or repeatedly failing to call Bedrock. Andrey's read is that this resembles a real compromise from the outside, and he notes what attackers actually do with stolen GitHub credentials has shifted: they used to mine Bitcoin, now they resell model tokens.

The hosts are careful to separate what they've observed from what they're inferring. What they've observed is firsthand and not in doubt: this chain backfired, **AWS blocked the account**, and restoring it was very painful. Andrey adds a coda worth planning for — getting your access to Anthropic models restored afterwards is a separate fight on top of getting the account back.

What they're inferring is *why* it tripped. Andrey's theory is that the combination reads as a fraud signal to AWS. Mattias flags his own version explicitly as speculation — AWS reviews accounts continuously and looks back over some window of days he doesn't know the length of, and, in his words, "I'm guessing that they have some triggers on like Bedrock maybe is failing." AWS doesn't publish its detection criteria or its lookback window, so treat that as a working hypothesis that fits the outcome, not as documented behavior. The practical advice is the same either way.

### What to do when the abuse ticket arrives {#response-playbook}

The hosts run through the response. You get a support ticket from AWS: there's activity in your account, please investigate and reply, or we shut it down.

1. **Check the account for real.** Confirm there's no actual fraud, and that you have the logs to show it.
2. **Reply immediately, even before you have answers.** Acknowledge the message and say you're investigating and will follow up.

Asked why step two matters, Paulina's answer is "otherwise they close it" — and she's right that that's on the table. AWS's abuse-notice guidance says that if you don't respond, AWS might block your resources or suspend the account. Andrey adds the consequence that arrives sooner: if you go silent, your account manager starts reaching out to people because they're worried the message never landed, and things escalate quickly from there. Both are real outcomes of ignoring the ticket, and the escalation usually gets there first.

AWS's own guidance is also tighter than the five-day window mentioned in the episode: its documentation puts the response expectation at **24 hours**, and says you can exceptionally request more time by replying with how much you need and why. Either way, the lesson holds: reply first, investigate second.

### What to check now {#what-to-check}

Pulled together from the discussion:

- If you haven't created, renamed, or transferred a GitHub.com repository since July 15, 2026, **you may still be on the old format entirely** — everything works, and you have time. GHES users are unaffected regardless.
- GitHub ships a preview endpoint so you can see what a repository's subject claim will become *before* you touch your cloud trust policies. Use it.
- Migrate the trust policy in stages rather than swapping the string. Replacing the allowed subject up front breaks the workflow immediately, because the repository is still issuing the old subject until the rename lands. The sequence that doesn't break anything: **(1)** widen the condition to accept both exact subjects — old and new — side by side; **(2)** perform the rename, transfer, or opt-in; **(3)** run the workflow and confirm authentication succeeds on the new subject; **(4)** remove the old subject. Microsoft's migration guide for Entra Workload ID walks the same dual-subject pattern, and the logic is identical on AWS.
- Inventory *every* role that trusts GitHub, not just the obvious deploy role — and include the org-wide wildcards, since a legacy-format `repo:my-org/*:*` won't match a repository that has moved to `repo:my-org@123456/...`. Only the roles with stale `sub` conditions will break, so a partial sweep leaves you with a partial outage later.
- Don't discover this through an AWS abuse ticket.

## Highlights {#highlights}

- **Andrey on GitHub's new OIDC subject claims:** "The problem that they're solving, it feels theoretical to me." His analogy — it's like shortening SSL certificate lifetimes to stop certificate theft, when nobody steals certificates anymore. The comparison is loose (certificates are public; short lifetimes exist to cap the damage from compromised private keys and mis-issuance), but the complaint under it holds: good security hygiene on paper, a lot of trust policies to rewrite in practice. Listen to episode #110 for the full argument.

- **Rename a repo, break your cloud:** Any GitHub.com repository renamed or transferred after July 15, 2026 silently switches to the new immutable `sub` format. Your IAM trust policy still matches the old string, so `AssumeRoleWithWebIdentity` fails and your runner can no longer assume roles whose trust policies no longer match the repository's subject — no artifact uploads, no S3 writes, no Bedrock calls through those roles, while anything with a matching condition keeps working. Org-wide wildcards don't save you either: `repo:my-org/*:*` is the legacy shape and won't match `repo:my-org@123456/...`. Mattias walks through exactly how it fails. Tune in before your next rename.

- **Andrey on the failure nobody plans for:** GitHub runners sit on Azure IP ranges that threat-intel vendors have flagged. Add a pipeline hammering `AssumeRoleWithWebIdentity` and failing every time, and from the outside it starts to resemble a compromised account. "We've seen cases where all that thing actually backfired and AWS blocked accounts." Catch the episode for how this chain reaction actually plays out.

- **On what attackers do with stolen CI credentials now:** "People used to mine Bitcoin. Now they actually resell tokens." That shift is why the hosts suspect failed Bedrock calls from a flagged IP read as fraud to AWS — a theory that fits what happened to them, not published detection behavior. Listen for the rest of the story.

- **The support-ticket rule the hosts want you to remember:** When AWS asks about suspicious activity, reply *before* you have answers. Paulina points out the account can get closed — AWS's own docs confirm suspension is on the table — and Andrey adds the faster consequence: your account manager starts chasing people because they think the message never reached you. AWS's guidance says respond within 24 hours. Tune in for the full response playbook.

- **Andrey on half-finished breaking changes:** "First of all, you're introducing the breaking change and then you're leaving it in a like half state." Some of your repositories get the new format, some don't, and which is which depends on when each was created or renamed. You *can* opt everything in at once — and break all your CI simultaneously. Listen to episode #110 for why that might actually be the better option.

## Resources {#resources}

- [Immutable subject claims for GitHub Actions OIDC tokens — GitHub Changelog](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/) — The announcement Andrey reads on air, published April 23, 2026, with a June 10, 2026 editor's note correcting the name/ID delimiter to `@`. Source of the July 15, 2026 cutover date and of the note that the change applies to GitHub.com only, not GitHub Enterprise Server.

- [OpenID Connect reference — GitHub Docs](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims) — The full claim reference: the `repo:OWNER@OWNER-ID/REPO@REPO-ID:...` format, how to opt in via the settings UI or REST API, the preview endpoint for checking a repository's future subject claim, and the note that owner and repo IDs can't be removed once immutable subjects are on.

- [Configuring OpenID Connect in Amazon Web Services — GitHub Docs](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws) — How to build the IAM identity provider and role trust policy correctly, including the `sub` conditions the hosts warn against leaving unscoped.

- [Create a role for OpenID Connect federation — AWS IAM User Guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html) — AWS's GitHub-specific guidance: IAM rejects a trust policy whose `token.actions.githubusercontent.com:sub` condition is missing or solely a wildcard, and spells out that failing to pin the organization and repository lets outside GitHub Actions assume the role. Also the reference for what actually breaks — access is decided per role, by that role's own trust policy. Includes worked `StringEquals` and `StringLike` examples.

- [About GitHub's IP addresses — GitHub Docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-githubs-ip-addresses) — GitHub's own acknowledgement that third-party threat intelligence and firewall vendors flag its runner IPs as malicious or suspicious, and that shared infrastructure means other users' activity drags down the reputation score. The documentation behind Andrey's "naughty list."

- [Review and respond to an AWS abuse report — AWS re:Post](https://repost.aws/knowledge-center/aws-abuse-report) — AWS Trust & Safety's process, including the 24-hour response expectation, the possibility of blocked resources or account suspension if you don't reply, and how to request an extension.

- [Migrate GitHub Actions federated credentials to immutable subjects — Microsoft Learn](https://learn.microsoft.com/en-us/entra/workload-id/workload-identities-github-immutable-subjects) — The dual-subject migration sequence: accept both old and new subjects, make the change, validate, then remove the old one. Written for Entra Workload ID, but the ordering is what matters and it transfers directly to an AWS trust policy.

- [Episode #107 — Continuous Integration in 2026: What Still Matters](/episodes/107-continuous-integration-in-2026-what-still-matters/) — The CI groundwork this episode builds on, including runners, pipeline gating, and the FivexL workflows that use OIDC-based AWS credentials.
