---
title: "#97 - Shift Left, Get Hacked: Supply Chain Attacks Hit Devs"
date: 2026-04-16T00:14:45+01:00
lastmod: 2026-04-16T00:14:45+01:00
episode: 97
author: "DevSecOps Talks"
participants: ["Paulina", "Mattias", "Andrey"]
---

March 2026 made supply chain attacks feel a lot less theoretical, but what made these incidents different? The hosts discuss compromised publishing credentials, automatic execution hooks like post-install scripts and Python `.pth` files, and how both humans and security tools caught the malicious releases. They also talk through concrete ways to make developer environments harder to abuse.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

 {{<  podbean sb67i-1a9d44e-pb "DEVSECOPS Talks #97 - Shift Left, Get Hacked: Supply Chain Attacks Hit Devs"  >}} 

---

<!-- Video -->

{{< youtube Vz-i7xodtlA >}}

## Summary
Attackers are now shifting left faster than defenders — and they are going straight for the developers. In this full-squad episode, Andrey, Mattias, and Paulina unpack the March 2026 supply chain attack chain that started with Aqua Security's Trivy scanner, cascaded into LiteLLM on PyPI, and was made glaringly obvious to human engineers when the attackers' own coding mistake turned their credential stealer into a fork bomb — though automated detection tools like Sonatype's also flagged the malicious releases within seconds. The hosts also cover the North Korean-attributed Axios NPM compromise and lay out practical remediation steps — from dev containers and version delays to disabling post-install scripts — arguing that the old advice of "just check if the package looks legit" no longer holds when the attackers are compromising the publishers themselves.

## Key Topics

### Supply Chain Attacks Have Shifted Left — Past the Scanners

The hosts observe that supply chain attacks have fundamentally changed direction. Previously, the main concern was malicious code slipping into production through compromised dependencies. Now, attackers are targeting developers and their workstations before code even reaches the CI/CD pipeline. As Mattias puts it, the attackers are "shifting left even more" — striking earlier in the process than the security tools that are supposed to catch them. Andrey agrees that March 2026 felt like the moment supply chain attacks moved "from theoretical to actual danger zone."

This is not the first time DevSecOps Talks has covered supply chain security — episodes [#46](/episodes/46-supply-chain/) and [#53](/episodes/53-supply-chain-again/) explored attack vectors and mitigation frameworks. But what is different now is the sophistication: attackers are not creating suspicious-looking typosquatting packages; they are compromising the signing keys and publishing credentials of legitimate, widely trusted projects.

### The Trivy-to-LiteLLM Attack Chain

On March 1, Aqua Security disclosed that its open-source Trivy vulnerability scanner had been compromised. The attacker group TeamPCP gained access to credentials used by the Trivy GitHub Actions workflow. Aqua initiated credential rotation, but the rotation was not atomic — according to their own post-incident analysis, the attackers may have obtained the refreshed credentials before the old ones were fully revoked.

On March 19, TeamPCP used still-valid credentials to force-push 76 of 77 release tags in the `trivy-action` repository and all seven tags in `setup-trivy`, redirecting trusted references to malicious commits containing a multi-stage credential stealer. Because many CI/CD pipelines reference version tags rather than pinned commit SHAs, organizations unknowingly ran the compromised code.

The Trivy foothold gave TeamPCP the keys to publish arbitrary versions of LiteLLM — a popular Python gateway to multiple LLM providers, downloaded 3.4 million times per day — to PyPI. Compromised versions 1.82.7 and 1.82.8 appeared on March 24, containing a malicious `.pth` file that executed automatically on every Python process startup. The payload harvested SSH keys, cloud tokens, Kubernetes secrets, and `.env` files, attempted lateral movement across Kubernetes clusters, and installed a persistent backdoor.

The hosts highlight the irony: the attackers' own code contained a bug. A flawed conditional in the credential stealer effectively turned it into a fork bomb, crashing systems with out-of-memory errors. This made the compromise immediately visible to human engineers — runaway processes and CPU pegged at 100% — while automated detection tools like Sonatype's flagged the malicious releases within seconds of publication. As Andrey notes, "we actually got lucky there." The compromised packages were caught within hours before PyPI quarantined them.

### The Axios NPM Compromise and State-Sponsored Actors

The episode also covers the Axios NPM supply chain attack, where malicious versions of the extremely popular HTTP client library (over 100 million weekly downloads) were published to the NPM registry on March 31. Google Threat Intelligence Group attributed this attack to UNC1069, a North Korean-nexus, financially motivated threat actor active since at least 2018.

The malicious versions deployed the WAVESHAPER.V2 backdoor across Windows, macOS, and Linux. The versions were live for approximately three hours before being removed.

Paulina notes this makes the old heuristics obsolete — looking at star counts, maintainer reputation, and project age no longer protects you when attackers are going directly after the maintainers themselves.

### Automatic Execution Hooks: A Low-Hanging Attack Vector

The hosts identify automatic code execution during package installation or startup as a common mechanism in these attacks. In the NPM ecosystem, packages can define lifecycle scripts — `postinstall`, `preinstall`, and others — that run automatically after installation. The LiteLLM attack on PyPI used a different mechanism: a malicious `.pth` file, which Python executes automatically on interpreter startup, combined with build-time execution paths. In both cases, malicious code runs before any scanner or manual review can catch it.

Mattias recommends switching to pnpm, which as of version 10 disables lifecycle scripts (postinstall, preinstall, etc.) by default, requiring explicit opt-in via an allowlist. This is a concrete, low-effort step that blocks one of the most commonly exploited attack vectors in the NPM ecosystem. For Python, the hosts note that UV and pip pull from the same PyPI registry but offer different configuration options that may help limit automatic execution.

### Remediation: What Can Teams Actually Do?

The hosts go through a practical list of defensive measures:

**Delay version updates.** Do not install the latest version the moment it drops. NPM supports a `min-release-age` setting in `.npmrc` that refuses to install any package version published less than a specified number of days ago. pnpm 10.16 added `minimumReleaseAge` for the same purpose. A seven-day delay would have blocked both the LiteLLM and Axios attacks, where malicious versions were caught within hours to days.

**Pin versions and review updates.** Dependabot and similar tools are valuable but should not be set to auto-merge on the latest version without review. The hosts caution that automated dependency updates can pull in compromised packages before anyone notices.

**Rotate credentials — and know how to.** Mattias shares a recent experience where his team had to rotate 500 passwords and tokens, with no documentation on how to do it. Credential rotation took weeks. Having documented, tested rotation procedures is essential.

**Isolate development environments.** Mattias advocates strongly for dev containers with temporary tokens as his preferred mitigation. If a compromised package runs inside a container, the blast radius is limited to that container — no host-level SSH keys, no persistent cloud credentials, nothing valuable to steal. The container can simply be destroyed. With AI coding tools able to generate dev container configurations quickly, the hosts argue there is no excuse not to use them.

**Protect credentials on developer machines.** Andrey recommends storing SSH keys in the Mac Secure Enclave or a password manager like 1Password, using temporary credentials for cloud access via AWS SSO or similar tools, and never storing production keys in the development environment.

**Use DNS filtering.** Solutions like NextDNS or Cloudflare Warp can block resolution of known malicious command-and-control domains. When an attacker's payload tries to phone home, DNS filtering can prevent the connection — and these services update their blocklists quickly.

**Watch AI code reviewers as a new vector.** Andrey raises a newer concern: if organizations run LLM-based code reviewers on pull requests — including those from external contributors — attackers can craft prompt injection payloads in their code. The code reviewer, running with a GitHub token potentially scoped beyond the target repository, becomes a vector for lateral movement.

### Security Now Episode 1072: The Detailed Breakdown

Andrey recommends Steve Gibson's Security Now episode 1072 for anyone wanting a thorough technical breakdown of how the Trivy-to-LiteLLM attack chain unfolded, including the Trend Micro analysis and the timeline of credential rotation failures. At over 1,000 episodes, Security Now has been covering security far longer than DevSecOps Talks — "we are approaching 100, they already did 1,000," Andrey quips.

## Highlights

- **Andrey:** "March felt like we are moving supply chain attacks from theoretical to actual danger zone." The Trivy breach proved that even security tools — the scanners meant to protect you — can become the attack vector. If your security scanner is compromised, who watches the watchers?

- **Mattias:** "The attackers are really shifting left even more. The attacks are happening before the code hits the CI/CD pipelines." While defenders talk about shifting security left, attackers are already there — targeting developer workstations and package publishers, not production systems.

- **Paulina:** "We said the official packages maintained by a large crowd are safe to use. But what we're seeing here is that they're going for the maintainer itself." The old heuristics — stars, downloads, active maintenance — no longer protect you when the publisher's own credentials are compromised.

- **Andrey on the LiteLLM bug:** The credential stealer had a coding mistake that turned it into a fork bomb, crashing systems with out-of-memory errors — which made the compromise immediately obvious to engineers on the ground, even as automated tooling was also flagging it. "We actually got lucky there." When your attacker's own bug is one of the loudest alarms, that should worry you about the attacks that don't have bugs.

- **Mattias on dev containers:** "If something happens, it's isolated in the dev container. Anything you can get hold of is only temporary. I can just kill a container and I'm good again." Dev containers with temporary tokens are his top recommendation for containing supply chain damage on developer machines.

- **On the Axios attack:** Google Threat Intelligence attributed the Axios NPM compromise to a North Korean-nexus threat actor. State-sponsored groups are now investing in supply chain attacks targeting the JavaScript and Python ecosystems at scale.

- **Andrey on AI code reviewers:** If you run an LLM-based code reviewer on pull requests from external contributors, you have a new attack surface — crafted prompt injections in the code can hijack the reviewer's GitHub token and poke around your other repositories.

## Resources

- [Aqua Security: Trivy Supply Chain Attack — What You Need to Know](https://www.aquasec.com/blog/trivy-supply-chain-attack-what-you-need-to-know/) — Aqua's own disclosure and post-incident analysis of the Trivy GitHub Actions compromise, including the credential rotation timeline.
- [CrowdStrike: From Scanner to Stealer — Inside the trivy-action Supply Chain Compromise](https://www.crowdstrike.com/en-us/blog/from-scanner-to-stealer-inside-the-trivy-action-supply-chain-compromise/) — Detailed technical breakdown of how TeamPCP weaponized the Trivy scanner to steal CI/CD secrets.
- [Sonatype: Compromised litellm PyPI Package Delivers Multi-Stage Credential Stealer](https://www.sonatype.com/blog/compromised-litellm-pypi-package-delivers-multi-stage-credential-stealer) — Analysis of the malicious `.pth` file in LiteLLM versions 1.82.7 and 1.82.8, including the credential harvesting and lateral movement stages.
- [Google Cloud Blog: North Korea-Nexus Threat Actor Compromises Axios NPM Package](https://cloud.google.com/blog/topics/threat-intelligence/north-korea-threat-actor-targets-axios-npm-package) — Google Threat Intelligence Group's attribution of the Axios compromise to UNC1069 and the WAVESHAPER.V2 backdoor.
- [Security Now #1072: LiteLLM](https://twit.tv/shows/security-now/episodes/1072) — Steve Gibson's detailed breakdown of the Trivy-to-LiteLLM attack chain, recommended by the hosts for anyone wanting the full technical timeline.
- [pnpm: Mitigating Supply Chain Attacks](https://pnpm.io/supply-chain-security) — How pnpm v10 blocks lifecycle scripts by default and its approach to supply chain security.
- [NPM Ignore Scripts Best Practices](https://www.nodejs-security.com/blog/npm-ignore-scripts-best-practices-as-security-mitigation-for-malicious-packages) — Practical guide to disabling post-install scripts in NPM as a security mitigation.
- [Mitigate Supply Chain Security with DevContainers and 1Password](https://www.nodejs-security.com/blog/mitigate-supply-chain-security-with-devcontainers-and-1password-for-nodejs-local-development) — Walkthrough of using dev containers with short-lived credentials to isolate developer workstations from supply chain attacks.
