---
title: "#4 - Docker Runtime Security"
date: 2020-03-24T00:00:00+00:00
lastmod: 2020-03-24T00:00:00+00:00
episode: 4
author: "DevSecOps Talks"
participants: ["Andrey", "Mattias", "Julien"]
aliases:
  - /episodes/docker-runtime-security/
---

In this episode, Mattias is trying to convince Andrey and Julien that running Docker containers in Kubernetes is more secure than virtual machines. How did it go? We agreed to disagree.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

{{< podbean ycpvc-d7494b "DEVSECOPS Talks #4 - Docker Runtime Security" >}}

## Summary

Mattias makes a bold claim: Docker containers are more secure than virtual machines. Andrey and Julien push back hard — and by the end, the three hosts explicitly agree to disagree. Along the way, they dig into why container breakouts are harder than people assume, how Lambda micro VMs can be exploited through warm TMP folders, why "containers do not contain" without extra kernel controls, and whether good monitoring matters more for security than any isolation technology. Recorded during COVID-19 lockdowns in 2020, the debate captures a moment when the container-vs-VM argument was far from settled.

## Key Topics

### Docker vs. VM security: technology vs. ways of working

Mattias opens the main debate by arguing that Docker containers are more secure than VMs in practice. His reasoning: containers are smaller, more focused, and more ephemeral than traditional virtual machines, which reduces attack surface. In a typical VM, you find mail agents, host-based intrusion detection, syslog, monitoring tools, and other services all coexisting with the application. In a container, you ideally run only the application itself.

Andrey pushes back immediately. He argues Mattias is comparing operational models, not technology. A well-run VM can also be immutable and minimal — you redeploy from a new image the same way you replace a container. Likewise, a badly built container can be long-lived, bloated, and full of unnecessary tools. Andrey has seen enterprises that run containers for months, SSH into them, and treat them like VMs.

Mattias concedes the point but maintains that the standard approach differs: VMs are typically kept running longer with more tools, while the standard approach for containers in Kubernetes is to rotate them and keep a smaller footprint. Andrey counters that most Docker images run as root by default, giving attackers more privilege than they would have on a typical VM where processes run under limited service accounts. This is one of the sharpest exchanges in the episode — better tooling does not fix insecure defaults.

The hosts eventually agree that both technologies can be secured well, but do not reach consensus on which is easier. Andrey summarizes it cleanly: containers make it "a little bit easier" to do the right thing because they narrow the focus to the application rather than the entire operating system, but it is absolutely possible to reach the same security level with VMs.

### Why container breakout is not as trivial as people imply

Mattias challenges the common assumption that containers are unsafe because "you can break out of them." He points out that every container breakout CVE he has reviewed requires significant preconditions: either running an attacker-controlled image or running in privileged mode. You cannot take a standard Ubuntu container image, run a single command, and escape. The threat is real but requires chained attacks, not a single exploit.

Julien and Andrey accept the premise but note that the comparison matters. VM isolation is fundamentally stronger at the hypervisor level. Container breakout may be hard, but it is architecturally easier than VM escape. The discussion reframes the question: runtime security is less about one isolation boundary and more about how many obstacles an attacker must pass through.

### Micro VMs, Firecracker, and Lambda attack vectors

Andrey brings up an important middle ground between containers and VMs: micro VMs. AWS Lambda runs on Firecracker, an open-source micro VM monitor. Lambdas are ephemeral, have read-only file systems, minimal tooling, and no access to source code or settings — making them quite secure by design.

But Andrey describes a real attack path researchers have demonstrated. The `/tmp` directory in Lambda is writable. If an attacker exploits a vulnerability to get code execution within the Lambda, and the Lambda is kept warm (invoked within 15 minutes so it stays in memory), the `/tmp` folder persists between invocations. An attacker can download tools incrementally across multiple Lambda runs, building up capability over time. From there, they can explore IAM permissions, exfiltrate data by encoding it in resource tags, or even override the Lambda function itself.

The point is that even well-designed ephemeral environments have attack paths when defenders are not paying attention. Security depends on hardening and monitoring, not just on the isolation primitive.

### Containers do not contain: AppArmor, Seccomp, and policy controls

Julien delivers the episode's sharpest technical point: "Containers do not contain." They are primarily Linux namespace isolation and need additional kernel controls — AppArmor profiles and Seccomp filters — to properly restrict what applications can do at runtime. Without those extra layers, a container running as root is effectively root on the host machine, and a container with host network access is the same as running directly on the server.

This shifts security responsibility in uncomfortable ways. In VM environments, operations and security teams traditionally handle access controls. In containerized environments, developers are often expected to define security profiles for their workloads — but they may not know which system calls or privileges their applications need. Julien describes this as a fundamental organizational gap: the people writing the workload and the people securing the workload are rarely working hand in hand.

Mattias suggests that platform teams can solve this by enforcing policies centrally. He references tools like Open Policy Agent to set standards for what gets deployed into a cluster, rather than relying on every developer to configure security correctly.

### Kubernetes makes monitoring and response easier

Mattias makes a strong case for container platforms as detection and response environments. He describes working with Falco, a runtime security tool, and highlights a powerful capability: if someone opens a shell inside a container, Falco can detect that behavior and the container is killed automatically. That kind of automated response is natural in an environment built around disposable workloads. On a VM, shells are a normal part of operations, making the same detection much harder to act on.

Julien extends this into a broader argument about monitoring and security being inseparable. He argues that when monitoring is poor, access control becomes chaotic — developers need broad production access just to debug issues. But with strong observability, teams can use feature flags, targeted routing, and centralized logging instead of SSH-ing into production. Good monitoring reduces the need for risky access patterns.

Julien offers a practical example: instead of blocking developers from opening shells in containers, observe that they are doing it and ask why. If they need logs, build a secure log access API. If they need to debug, improve the observability tooling. Monitoring turns security violations into product requirements.

### Minimizing container images

Julien mentions using DockerSlim (now SlimToolkit) to strip unnecessary components from container images, reducing attack surface without requiring deep knowledge of every dependency. It is not a complete security solution, but it is an easy first step that removes much of the bloat containers inherit from their base images.

For organizations with compliance requirements, Julien notes that third-party security vendors provide validated runtime solutions — useful for audit purposes where you need a third party to confirm that the running workload matches what was built internally.

### Bundling dependencies with the application

Mattias raises a concern about how containerization changes dependency management. In older models, operations maintained the web server (Apache, Nginx) separately from the application. In containers, the web server, runtime, and application are bundled together. That means patching the web server requires rebuilding and redeploying the entire container, even when the application code has not changed.

Andrey reframes this as a different packaging model, not a new problem. With Java WAR files deployed to Tomcat, you already had dependency coupling — you just managed it differently. Containers actually improve the situation in one way: each application owns its own dependency lifecycle instead of sharing an application server. One application can upgrade independently without affecting others on the same host.

Both hosts note that dedicated application servers are fading. Modern applications in Go, Python, and Node.js often handle HTTP directly, removing the need for a separate web server entirely. The ingress controller in Kubernetes handles routing at the cluster level, which is a separate concern from the application.

### The hosts agree to disagree

The episode ends without consensus. Mattias remains firmly convinced that containers, run properly in Kubernetes, are more secure than VMs. Julien's final position: "Containers can be as secure as VMs, but they need more work to get there." Andrey advocates for a layered approach — use both VMs and containers, with container security focused on application concerns and VM security focused on operational and resource isolation. He also notes that CoreOS, once the go-to minimal container OS, had recently been discontinued by IBM, leaving teams to find alternatives like Fedora CoreOS.

## Highlights

### "Containers do not contain."

Julien delivers the episode's most quotable line, reminding listeners that containers are mostly Linux namespacing — not real isolation boundaries. Without AppArmor, Seccomp, and careful configuration, a container is far less restrictive than people assume. A sharp reality check for anyone treating "containerized" as synonymous with "secure."
Listen to the full episode on [DevSecOps Talks](https://devsecops.fm/) to hear why container security is never just about packaging.

### "If somebody pops a shell in a container, that container is killed."

Mattias describes working with Falco and highlights a capability that captures the strongest pro-container argument: disposable workloads change the incident response model entirely. On a VM, a shell is normal. In a container, it is an alarm — and the platform can act on it automatically.
Listen to the episode to hear how the hosts connect runtime detection, monitoring, and automated response.

### "Most of the Docker images out there are running as root."

Just when the debate leans in Docker's favor, Mattias himself brings it crashing back. On VMs, running as root is rare. In containers, it is the default. Better tooling does not fix insecure defaults — and this remains one of the most practical risks in container environments.
Hear the full back-and-forth on [DevSecOps Talks](https://devsecops.fm/).

### "We have to separate apples from bananas — the technology from the ways of working."

Mattias draws a sharp line that reframes the entire debate. Are containers actually more secure, or are teams comparing modern container practices against outdated VM operations? A useful reminder that architecture arguments often hide workflow arguments underneath.
Listen to the full conversation for the spirited disagreement that follows.

### "Monitoring very much goes hand in hand with security."

Julien makes the case that bad observability leads directly to bad access control. When developers cannot see what is happening in production safely, they need more privileges, more access, and more risky workarounds. Fix the monitoring, and many security problems solve themselves.
Listen to the episode on [DevSecOps Talks](https://devsecops.fm/) to hear why observability might be the most underrated security control.

### "Containers can be as secure as VMs, but they need more work."

Julien's final verdict — delivered over Mattias's loud objections — perfectly captures the episode's unresolved tension. The hosts explicitly agree to disagree, making this one of the more honest security debates you will hear on a podcast.
Catch the full exchange on [DevSecOps Talks](https://devsecops.fm/).

## Resources

- **[Falco](https://falco.org/)** — CNCF-graduated runtime security tool that detects anomalous behavior in containers and Kubernetes using eBPF. Mentioned by Mattias for its ability to automatically kill containers when suspicious activity like shell access is detected.

- **[Firecracker](https://firecracker-microvm.github.io/)** — Open-source micro VM monitor built by AWS, powering Lambda and Fargate. Discussed by Andrey as an example of ephemeral, hardened execution environments and their attack surfaces.

- **[SlimToolkit (formerly DockerSlim)](https://slimtoolkit.org/)** — Tool for analyzing and minimizing container images, automatically generating AppArmor and Seccomp profiles. Mentioned by Julien as a practical way to reduce attack surface without deep security expertise.

- **[Open Policy Agent (OPA)](https://www.openpolicyagent.org/)** — General-purpose policy engine for enforcing security and operational policies across Kubernetes clusters. Referenced by Mattias for centrally enforcing deployment standards.

- **[AppArmor](https://gitlab.com/apparmor/apparmor/-/wikis/home)** — Linux kernel security module that restricts application capabilities through mandatory access control profiles. Discussed by Julien as an essential add-on for meaningful container isolation.

- **[Seccomp (Secure Computing Mode)](https://docs.kernel.org/userspace-api/seccomp_filter.html)** — Linux kernel facility that restricts which system calls a process can make. Used by Docker and Kubernetes to reduce the container attack surface by blocking unnecessary syscalls.

- **[Fedora CoreOS](https://fedoraproject.org/coreos/)** — Successor to CoreOS Container Linux (discontinued 2020), a minimal, auto-updating operating system designed for running containerized workloads. Relevant context for Andrey's mention of CoreOS being killed by IBM.
