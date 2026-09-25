---
title: "#110 - AWS Access Denied? Check Your Repo Rename"
date: 2026-09-14T12:00:00+01:00
lastmod: 2026-09-25T16:12:11+01:00
episode: 110
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
aliases:
  - "/episodes/110/"
description: "Could your broken pipeline look like suspicious activity to AWS? This episode examines an account block following repeated access denials, separates the observed outcome from the suspected cause, and explains how to respond to an abuse notice."
subtitle: "A repo rename can break OIDC trust, while an unread AWS abuse notice can let the incident escalate."
readtime: "17 min read"
image: "/images/covers/110.png"
audio_url: "https://mcdn.podbean.com/mf/web/zoc8fs2tyv3f2n95/110-can-broken-github-actions-get-your-aws-account-blocked-.mp3"
---

Could your broken pipeline look like suspicious activity to AWS? This episode examines an account block following repeated access denials, separates the observed outcome from the suspected cause, and explains how to respond to an abuse notice.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

{{< whats-in-this-post >}}

<!-- Player -->

 {{<  podbean j2kez-1b58ea3-pb "DEVSECOPS Talks #110 - AWS Access Denied? Check Your Repo Rename"  >}}

---

<!-- Video -->

## A repository rename can lock your pipeline out of AWS {#the-problem}

Renaming a GitHub repository takes about five seconds. It was never free for your pipeline: the repository name sits inside the subject claim of the OIDC token your workflows present to AWS, so an IAM trust policy pinned to the exact old name could already break on a rename. What changed [on July 15, 2026](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/) is the reach. A rename now also flips the repository onto GitHub's immutable subject format, which staples numeric owner and repository IDs into that same claim. The organization wide pattern that used to shrug off a rename, `repo:your-org/*:*`, stops matching too. `sts:AssumeRoleWithWebIdentity` fails, and every job in that repository that needs AWS credentials fails with it.

A red pipeline you can live with for an afternoon. The second order effect is the expensive one. GitHub's hosted Ubuntu and Windows runners sit on shared Azure address space that threat intelligence vendors already rate badly, and a pull request workflow that retries a denied role assumption on every push can look like the traffic a compromised account produces. We can't see AWS's side of that judgement, but we have seen the combination end with AWS blocking the account, and getting it back was slow and painful.

So there are two problems inside one changelog entry: a trust policy migration nobody scheduled, and a failure mode that escalates past your CI dashboard into your standing with your cloud provider. Both are avoidable, and neither is visible from the announcement.

## How your runner gets into your AWS account {#oidc-trust}

The change only makes sense if the trust path is clear, so start there.

#### Why not just put an access key in GitHub secrets?

Because that key is a long lived credential living in a system whose blast radius you don't control, and it keeps working after it leaks.

CI needs a worker: a piece of compute that runs your job. Either you run self hosted runners, or you use the ones your provider offers. When a GitHub hosted runner needs to do something in your AWS account, run OpenTofu, push an image, call an API, it needs credentials from somewhere. The easy answer is an IAM user, access keys in repository secrets, environment variables in the job. You can do that. You shouldn't.

The better answer is OIDC web federation. You create an IAM role whose trust policy says, in effect: a token issued by GitHub, for this repository, may assume me. GitHub mints a short lived token that describes the workflow, the runner calls `sts:AssumeRoleWithWebIdentity` with it, and the token is the identity. The job still ends up holding real AWS credentials, because [STS returns an access key id, a secret access key and a session token](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html), and those still deserve care in logs. What OIDC removes is the long lived key you would otherwise provision into GitHub secrets and rotate by hand. The same pattern works on GitLab, and against Azure and Google Cloud.

{{< key-point >}}The identity in that trust policy is a string. Change the string, lose the access.{{< /key-point >}}

The string is the token's subject, matched with the `token.actions.githubusercontent.com:sub` condition key. AWS will not let you leave it open: when GitHub's OIDC provider is the trusted principal, IAM checks on policy create and update that the condition is present and that its value is not solely a wildcard, and rejects the policy otherwise. [AWS is blunt about why](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html): if you don't limit `sub` to a specific organization or repository, GitHub Actions from organizations outside your control can assume roles associated with that provider in your account. Pin the organization and the repository, and narrow to a branch or an environment where the workflow allows it.

## What GitHub changed in the subject claim {#subject-claim}

That pinned string is exactly what moved.

#### What does the new subject claim look like?

It carries numeric IDs after the names, separated by `@`: `repo:octocat@123456/my-repo@456789:ref:refs/heads/main` instead of `repo:octocat/my-repo:ref:refs/heads/main`.

GitHub's reasoning is in the [changelog from April 23, 2026](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/). The old subject is built from names, and names can be recycled. If a repository or organization name is freed up and someone else claims it, they can mint tokens carrying the same subject string, and any trust policy still matching that string would hand them a role. IDs are not reassigned, so the new format closes that.

One detail is easy to miss and expensive to get wrong. The changelog picked up an editor's note on June 10, 2026: the delimiter between the name and the ID was originally documented as `-` and is now `@`, because `@` can't appear in a GitHub username or repository name. If you wrote a trust policy against the earlier documentation, it doesn't match anything.

The rollout, from the same source:

- Repositories created on github.com after July 15, 2026 use the immutable format automatically.
- Renames and transfers after that date switch the repository to it.
- Existing repositories keep the old format until someone opts them in, at repository or organization level.
- GitHub Enterprise Server is out of scope. Workflows there are unaffected.

{{< key-point >}}If nobody has created, renamed or transferred a github.com repository since July 15, 2026, and nobody has opted a repository or an organization in, this rollout has not reached your trust policies yet.{{< /key-point >}}

[GitHub's OIDC reference](https://docs.github.com/en/actions/reference/security/oidc) adds one more constraint worth knowing before you design around it: once a repository is on immutable subjects, `owner_id` and `repo_id` are always present in the `repo` segment of `sub`, even when you customize claims with `include_claim_keys`. You can't strip them back out.

## The migration is broad, the attack is narrow {#half-state}

That is a real hole, and the honest reaction to it is still mixed.

#### Is the attack this prevents worth the work it creates?

On its own, probably not, but the format is the default now, and arguing with a default doesn't keep your deploys green.

Work the squatting scenario through. The legacy subject is names all the way down, so it matches again whenever a name comes back into circulation, and that can happen at two levels. Rename a repository and its old name is free inside your own organization, so a repository created under that name next presents the subject the old one used to present, and a trust policy still pinned to that string covers it. Release an organization name and the same thing happens one level up, for whoever registers it next. GitHub's announcement gives both as the reason for the change, and the [OpenID Connect core specification](https://openid.net/specs/openid-connect-core-1_0.html) does say a subject should be locally unique and never reassigned, which a recyclable name is not.

How much that is worth depends on how often you think it happens. It feels theoretical to us. It reads like shortening certificate lifetimes to stop certificate theft: defensible on paper, and a lot of operational work billed to everyone.

The sharper complaint is about the shape of the rollout rather than the format. This is a breaking change delivered into a half state. Some of your repositories issue the new subject, some issue the old one, and which is which depends on when each was created, renamed, transferred or opted in. If your inventory doesn't track the subject format, you'll discover the mismatch when a workflow fails. One repository at a time, usually on a Monday.

{{< key-point >}}You can opt everything in at once and break all of your CI at once. That is at least a failure you scheduled, in one place, with everyone watching.{{< /key-point >}}

The opt in is a toggle in the repository or organization OIDC settings, and `use_immutable_subject` on `PUT /repos/{owner}/{repo}/actions/oidc/customization/sub` or the [equivalent organization endpoint](https://docs.github.com/en/rest/actions/oidc). Do it deliberately, after the trust policies accept both subjects, not to find out who breaks.

## What actually breaks when the subject flips {#what-breaks}

The blast radius is narrower than "our AWS access is gone", which is part of what makes the morning confusing.

#### Which parts of my pipeline stop working?

Only the roles whose `sub` condition no longer matches, and then every step that needed those roles: artifact uploads, image pushes, S3 writes, Bedrock calls.

Access is decided per role, by that role's own trust policy. A role whose condition still matches keeps working. So some jobs fail, some don't, and the first theory in the incident channel is usually about the failing job rather than about identity. The error is an access denied on `AssumeRoleWithWebIdentity`, which reads like a permissions problem, not like a repository rename from last Thursday.

Note where the failure lands. The job stops at the credential step, so it never makes the S3 or Bedrock call at all, and what you see in CloudTrail is a run of failed `AssumeRoleWithWebIdentity`. Denied calls against a service are a separate stream, made with credentials a job already holds. Both can be running in the same account at the same time, and they show up in different places.

Org wide wildcards don't save you either. <mark>`repo:my-org/*:*` is the legacy shape</mark>, and it stops matching a repository that now presents `repo:my-org@123456/my-repo@456789:...`. The immutable equivalent needs the owner ID: `repo:my-org@123456/*:*`. Same trap as the exact string, with a wildcard on the end.

Then there is volume. If the affected workflow runs on pull requests, you don't get one denial, you get a stream of them, from every push on every open branch, for as long as it takes someone to connect the rename to the failures. That stream is what turns a CI problem into the next section's problem.

## Failing pipelines can read as fraud to AWS {#fraud-signal}

Nobody plans for the part where the cloud provider reads your broken pipeline as an intrusion.

#### Why would AWS care that my role assumption is failing?

Because a run of denied calls from an address with a poor reputation resembles someone working through credentials they shouldn't have.

Start with the addresses. [Windows and Ubuntu hosted runners are hosted in Azure](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) and carry the same IP ranges as the Azure datacenters; the macOS runners sit in GitHub's own macOS cloud instead. Either way the ranges are shared with other tenants, and [GitHub documents the consequence itself](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-githubs-ip-addresses): third party threat intelligence services, IP reputation scanners and firewall vendors may flag its IP addresses as malicious or suspicious, because other tenants' activity drags the reputation of the shared ranges down. If you run intrusion detection, you have probably already dismissed a false positive from your own runners. We have seen those flags fire across multiple customers.

Now stack the failures on top. The same flagged addresses are producing denied `AssumeRoleWithWebIdentity` calls from the repository whose subject moved, and, in jobs that still hold working credentials, denied calls against services those credentials can't reach. Bedrock is the one that draws attention, because model access is what attackers currently want. [Sysdig's LLMjacking research](https://www.sysdig.com/blog/llmjacking-stolen-cloud-credentials-used-in-new-ai-attack) documented attackers validating stolen cloud credentials against hosted model providers and reselling the access, and estimated potential costs to the victim of over $46,000 per day. The old pattern was mining cryptocurrency on someone else's compute. The current one is reselling someone else's model tokens.

{{< key-point >}}Denied calls from a flagged runner IP, repeated on every push, could resemble an attacker working through credentials they just bought.{{< /key-point >}}

Keep what we saw separate from what we infer. What we saw firsthand: this chain ended with AWS blocking the account, restoring it was painful, and restoring access to Anthropic models in Bedrock afterwards was a separate fight on top of that. What we infer is why it tripped, because AWS doesn't publish its detection criteria or how far back it looks. Treat the mechanism as a working theory that fits the outcome. The response is the same either way.

## Answer the abuse notice before you have answers {#abuse-notice}

Which brings us to the email nobody wants.

#### What do I do when AWS says there is suspicious activity in my account?

Reply inside the deadline the notice gives you, and if you need longer than that, ask for the extension in the reply.

The notice asks you to look into activity in your account and respond, and it carries its own date. The one we saw gave five days. [AWS's published guidance](https://repost.aws/knowledge-center/aws-abuse-report) puts the expectation at 24 hours, says AWS might block your resources or suspend the account if you don't respond, and says you can exceptionally ask for more time by replying with how much you need and why. Work to whichever date is in front of you, and treat more time as something you request explicitly. A short note saying "received, investigating, detail to follow" is worth sending on its own, and it is not an extension.

{{< key-point >}}Acknowledging the notice and asking for more time are two different messages. If you need the second one, write it.{{< /key-point >}}

Do the work properly too. Confirm there is no actual fraud, and confirm you have the logs to show it. If the denials really are your own runners hitting a stale trust policy, the CloudTrail trail of `AssumeRoleWithWebIdentity` failures is your evidence, not your embarrassment.

Silence costs more than the ticket. The support case is not the only channel: your account manager starts calling people because they assume the message never landed, and a quiet CI misconfiguration turns into an escalation with your management in it.

None of that works if the mail lands in an inbox nobody is watching. Two pieces of account hygiene do most of the work here. Don't register accounts to a personal address with plus notation, `someone+aws-prod@gmail.com` and friends, because exactly one person receives those and they take holidays. [AWS recommends a group address for root user credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html) for that reason: a business managed address that forwards to several people, so contact from AWS doesn't wait for someone to come back from vacation. Then fill in the [alternate contacts](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-update-contact-alternate.html), billing, operations and security, which can each be a distribution list and can be set across an organization from the management account.

## Migrate the trust policy without an outage {#migration}

With the alerting path fixed, the migration itself is mechanical, as long as you do it in the right order.

#### How do I switch a trust policy without breaking the workflow?

Accept both subjects first, make the change second, remove the old subject last.

Start by checking what each repository presents today. CloudTrail records the subject on `AssumeRoleWithWebIdentity` events as `subjectFromWebIdentityToken`, [the value STS reads from the token's `sub` claim](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html). Owner and repository names each followed by `@` and digits mean that repository is already on the immutable format.

Replacing the allowed subject up front breaks the workflow immediately, because the repository is still issuing the old subject until the rename or the opt in actually lands. The sequence that doesn't break anything:

1. Add the subject the repository will present after the move, alongside the one it presents today, keeping the same branch or environment restriction on both.
2. Do the rename, the transfer, or the opt in.
3. Run the workflow and confirm authentication succeeds on the new subject.
4. Remove the old subject.

[Microsoft's migration guide for Entra Workload ID](https://learn.microsoft.com/en-us/entra/workload-id/workload-identities-github-immutable-subjects) walks the same dual subject pattern. The cloud is different, the ordering is identical.

Treat the move as one way. GitHub documents the opt in, and documents no supported way back to the legacy subject.

{{< key-point >}}The dual subject window is the only safety net on offer. Plan the migration as one way traffic.{{< /key-point >}}

Two things make this go wrong at scale. First, the inventory: it is every role that trusts GitHub, not the obvious deploy role, and it includes the org wide wildcards. A partial sweep gives you a partial outage later, on whichever repository someone renames next. Second, the string you are preauthorizing. The changelog points to a preview endpoint that shows what a repository's subject claim prefix will look like under the new format, and that preview describes the repository as it is now. A rename changes the name component, and a transfer changes the owner component and its ID, so the subject you allow has to carry the name the repository will have and the owner ID of the organization it is moving to, with the branch or environment restriction still on the end. Read the pieces off the endpoint rather than assembling IDs by hand, especially given the `-` to `@` correction in June.

If your trust policies live in OpenTofu or Terraform modules, this is a small pull request per module and a big one for whoever owns them all. That is the real cost of the change, and it is worth naming in the sprint rather than absorbing it as an incident.

## What this means for teams {#what-this-means}

The change itself is a one line edit in a JSON document. What it exposes is whether anyone on your team could connect a Monday morning access denied to a Thursday afternoon repository rename, and whether the mail AWS sends when it gets nervous reaches someone who can act on it. Those two gaps are worth more than the format.

This week:

- Inventory every IAM role whose trust policy references `token.actions.githubusercontent.com`, including wildcard subjects, and note which repositories each one covers.
- Pick one non critical repository, run the dual subject migration end to end, and time it. That number is your estimate for the rest.
- Check the root user email and the billing, operations and security alternate contacts on every account, and give the vendor change feeds an owner in the same pass: the GitHub changelog changed your CI rules here, and the AWS mail only arrived afterwards. Neither should land in an inbox nobody reads.
- Tell whoever is most likely to rename a repository that a rename now changes cloud access, and agree that it goes through the migration sequence first.

## Common questions, answered {#faq}

### How do I tell whether a repository is already using immutable subject claims? {#faq-check-format}

Look at the subject a successful role assumption presented: CloudTrail records it on `AssumeRoleWithWebIdentity` events as `subjectFromWebIdentityToken`, the value the [STS API returns](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html) from the token's `sub` claim. If the owner and repository names are each followed by `@` and digits, that repository is on the immutable format.

The repository and organization OIDC settings show whether someone opted in, and GitHub's preview endpoint returns what the subject claim prefix will become.

### Do I need to change anything if we have not renamed any repositories? {#faq-no-rename}

Not urgently, as long as nothing else moved either. An existing github.com repository keeps the legacy subject until it is renamed, transferred, or opted in at repository or organization level, so trust policies for untouched repositories keep working.

Transfers are the easy one to miss, because nobody thinks of them as a rename: moving a repository to another owner after July 15, 2026 switches it to the immutable format too, and it changes the owner ID in the subject as well as the name. New repositories are the other exception. Anything created on github.com since July 15, 2026 issues the immutable subject, so a trust policy copied from an older repository won't match it and the first workflow run fails on role assumption. GitHub Enterprise Server is unaffected.

### Can we turn the immutable subject format off? {#faq-opt-out}

Plan to migrate rather than to opt out. GitHub documents the opt in and documents no supported way to put a repository back on the legacy subject, which is why the migration runs one way.

What the announcement doesn't settle is whether an organization can hold the line some other way, so don't build a plan on that hope. The dual subject condition costs one extra line and survives either answer.

## Related episodes {#related-episodes}

- [Episode 107, Continuous Integration in 2026: What Still Matters](/episodes/107-continuous-integration-in-2026-what-still-matters/) covers the CI groundwork underneath this one: runners, what belongs in a pipeline, and how the mainline stays green.
- [Episode 97, Shift Left, Get Hacked: Supply Chain Attacks Hit Devs](/episodes/097-shift-left-get-hacked-supply-chain-attacks-hit-devs/) is the case for why stolen publishing and CI credentials are worth this much care.
- [Episode 81, Keeping Secrets Safe](/episodes/081-keeping-secrets-safe/) is the wider view of secret handling: which secrets are at risk, and which tools fit humans, CI/CD and workloads.

## Resources {#resources}

- [Immutable subject claims for GitHub Actions OIDC tokens, GitHub Changelog](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/) settles the dates and the format: published April 23, 2026, the July 15, 2026 cutover for new repositories, renames and transfers, the repository and organization opt in, and the June 10, 2026 editor's note changing the delimiter to `@`.
- [OpenID Connect reference, GitHub Docs](https://docs.github.com/en/actions/reference/security/oidc) settles both subject formats side by side, the fact that `owner_id` and `repo_id` cannot be removed once a repository is on immutable subjects, and that GitHub Enterprise Server is excluded.
- [REST API endpoints for GitHub Actions OIDC, GitHub Docs](https://docs.github.com/en/rest/actions/oidc) settles how to opt in programmatically, including the `use_immutable_subject` body parameter at repository and organization level.
- [AssumeRoleWithWebIdentity, AWS STS API Reference](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html) settles what the call returns and that the logged `SubjectFromWebIdentityToken` is the token's `sub` claim, which is how you read a repository's current subject format.
- [Create a role for OpenID Connect federation, AWS IAM User Guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html) settles what AWS requires and rejects in a GitHub trust policy, with worked `StringEquals` and `StringLike` examples.
- [About GitHub's IP addresses, GitHub Docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-githubs-ip-addresses) settles that reputation vendors flag GitHub's shared ranges as malicious or suspicious, and why.
- [Review and respond to an AWS abuse report, AWS re:Post](https://repost.aws/knowledge-center/aws-abuse-report) settles the 24 hour response expectation, the possibility of blocked resources or suspension, and how to request an extension.
- [LLMjacking: stolen cloud credentials used in a new AI attack, Sysdig](https://www.sysdig.com/blog/llmjacking-stolen-cloud-credentials-used-in-new-ai-attack) settles what attackers do with stolen cloud credentials against hosted models, and the estimated potential cost to the victim.
