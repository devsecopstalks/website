---
title: "#3 - Docker Secure Build"
date: 2020-03-24T00:00:00+00:00
lastmod: 2020-03-24T00:00:00+00:00
episode: 3
author: "DevSecOps Talks"
participants: ["Andrey", "Mattias", "Julien"]
aliases:
  - /episodes/docker-secure-build/
---

Building Docker images is not as straightforward as one would like sometimes. In this episode we talk about how you can build more secure and lightweight container images, ready-made for production.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

{{< podbean cffda-d6b1a4 "DEVSECOPS Talks #3 - Docker Secure Build" >}}

## Summary

In this early DevSecOps Talks episode, Mattias, Andrey, and Julien dig into Docker security as a supply chain problem — and quickly dismantle the assumption that a signed container means you know what is inside. Julien pushes back sharply: signing only gives a "semantic guarantee" that an image is what it claims to be, not that it is safe. Mattias argues that containers were designed to be convenient, not secure by default, while Andrey points out that containerization has fundamentally changed the patching game — once the OS, web server, and application are packaged together, every security fix becomes a rebuild-and-redeploy exercise. The hosts make the case for layered scanning, slim runtime images, multi-stage builds, and continuous rebuilding as the practical path to running containers safely in production.

## Key Topics

### Container images vs. running containers

The conversation starts by separating two distinct parts of container security: the image and the running container.

Mattias explains that a container image can be treated much like any other file or archive — a zip or tar file sitting on disk. Because of that, teams can sign images cryptographically to verify origin and integrity, similar to how Node.js developers sign releases with their private keys. That gives consumers confidence that the image came from a known source and has not been tampered with.

But Julien pushes back on a common misunderstanding: signing does not mean the contents are inherently safe. As he puts it, you get a "semantic guarantee that this image is what it's pretending to be" — but not proof that everything inside is secure. Authenticity is not the same as security.

The hosts frame this as a trust problem. In a production cluster, teams often want to prevent engineers or workloads from pulling arbitrary images and running them without controls. Signed images and curated registries help, but they do not eliminate the need for careful validation.

### Trust, Docker Hub, and the container supply chain

A major part of the episode focuses on how much trust teams should place in public images, including those from Docker Hub.

Andrey raises the practical reality: if you are running four different languages, you cannot build and maintain base images for all of them. It is much easier to grab the latest Node.js, Python, Ruby, or Java images from Docker Hub and build from there. Julien and Mattias acknowledge that reality, but caution against treating "official" or branded images as automatically secure.

Julien walks through the different trust levels on Docker Hub:

- Images from unknown individuals are the hardest to trust
- Organization-backed images (Red Hat, CloudBees, etc.) provide more accountability based on brand recognition
- Even reputable images can contain known vulnerabilities — scanning a Jenkins image from Docker Hub can reveal a surprising number of CVEs
- A trusted source can still introduce problems, whether by mistake or through malicious intent

That leads into a broader discussion of supply chain attacks. Julien references real examples where Node.js libraries on npm were taken over by malicious parties after the original maintainer walked away. The same risk applies to container images.

Julien points out that large organizations sometimes go as far as rebuilding all dependencies from source — he mentions having heard of teams that do not pull jar files from Maven Central but build their own from source to verify exactly what they are shipping. While that is not feasible for every team, the principle stands: reduce blind trust and increase verification where the environment demands it.

### Why container security is not just image signing

The discussion then shifts from image authenticity to runtime security.

Mattias explains that containers rely on Linux kernel primitives — namespaces for process isolation, along with controls for networking, memory, and disk. These low-level APIs are useful for resource sharing and scaling, but they were not originally designed as strong security boundaries. As he puts it, "the container does not contain things, it's just an abstraction." Container breakout vulnerabilities matter because an attacker who can exploit the runtime or host interface may reach beyond the container itself.

This leads to one of the episode's sharpest observations from Mattias: containers became popular because they are efficient and convenient to operate — you can bin-pack them on the same hardware and run far more applications per server. But from a security perspective, "it was not designed to be secure by default, it was designed to be convenient." That gap between convenience and security is what teams must actively address through scanning, hardening, and runtime controls.

### CVE scanning: registries, dependencies, and source code

The hosts spend a good amount of time discussing scanning tools and where each fits in the security pipeline.

Mattias notes that most container registries now offer built-in vulnerability scanning, sometimes called container analysis APIs. Julien suggests a practical AWS-based pattern: if you do not want to pay for Docker Hub premium but still want to use public images, you can pull from Docker Hub, push into AWS Elastic Container Registry (ECR), and take advantage of its built-in CVE scanning. Then you restrict your production orchestrators to pull only from ECR.

Julien draws an important distinction between types of scanning:

- **Registry scanning** examines what packages are installed in the image at the OS level. The registry unpacks the image, identifies installed packages, and flags known CVEs.
- **Dependency scanning** tools like Snyk, Dependabot, and similar platforms check application dependency manifests (package.json, requirements.txt, pom.xml) against CVE databases. They are protecting against supply chain vulnerabilities in libraries, not scanning custom application code.
- **Static analysis and linters** can catch some obvious security issues in application source code, but as Andrey notes, they mainly catch "easy targets" and default patterns.

Julien initially states that registry scans do not cover source code, then corrects himself to clarify the distinction more precisely: registries scan installed OS packages, while separate tools scan programming language dependencies. Neither deeply analyzes your own custom code. That leaves an unknown component in the stack that teams need to address through other means — code review, testing, and secure development practices.

Andrey also mentions using Anchore, which he describes as the foundation for many of these CVE scanning capabilities.

### The shift from OS patching to image rebuilding

One of the most practical insights comes from Andrey, who compares containers to older operational models.

In traditional environments, teams could patch the operating system or update components like Nginx independently of the application. With containers, those layers are packaged together. If a new Nginx vulnerability is disclosed, the team needs to rebuild and redeploy the entire image that contains both the web server and the application code.

This changes patching from an infrastructure task into an application delivery task. Security updates are no longer something ops handles in isolation — they flow through the same build-and-deploy pipeline as feature code.

The hosts argue that this is why security must be a concern from the earliest stages. As Andrey puts it, referencing Julien's earlier point: security belongs in the first commit, because that is when it is cheapest and easiest to get right. A green build today does not guarantee a safe deployment tomorrow if new CVEs are published against the packages already running in production.

### Slim images, distroless approaches, and DockerSlim

Mattias argues strongly for reducing container contents to the bare minimum. He highlights DockerSlim (now SlimToolkit), a project he uses frequently that strips images down to only the components essential for the application. In his example, a Maven-based application image dropped from roughly 600 MB to 140 MB — with no bash shell or other standard OS tooling left in the result.

Julien reinforces the security rationale: "the less code you have, the less vulnerability you have, and that's what you want in production." He mentions Alpine Linux and Google's distroless images as complementary approaches that aim for the same goal — minimal OS footprint in production containers.

The common theme is that production containers should not carry build tools, shells, package managers, or debugging utilities. Every unnecessary binary is a potential attack surface. The best production image is not the one easiest to build, but the one that contains the least unnecessary code.

### Multi-stage builds and separate build vs. runtime images

The hosts spend considerable time on one of the most practical Docker security patterns: multi-stage builds.

Julien explains the concept of build stages — using an intermediate container with all build dependencies to compile the application, then copying only the final artifact into a much smaller production image. This separation means the production image does not need compilers, package managers, or the full dependency tree.

Andrey confirms this maps directly to Docker's multi-stage build feature: "You just build your Docker build in one stage and then just copy build results to the next stage." He also points out the developer experience benefit — since the build environment is defined inside the Dockerfile itself, developers do not need to set up different language toolchains on their local machines when working across multiple microservices.

Julien adds a performance angle: pulling a pre-built container image with cached dependencies is often much faster than resolving and fetching all dependencies from scratch. He has seen Maven builds that took 20 minutes purely because they had to re-fetch all artifacts every time. Pre-building and caching the dependency layer can dramatically improve total build-to-production time.

### Continuous rebuilding and reducing attacker persistence

Andrey recommends reducing the lifetime of deployed images by rebuilding base images and all derived containers regularly — potentially every week — pulling in the latest patches each time. While this adds operational overhead, it shortens the window of exposure and makes it significantly harder for attackers to maintain persistence in stale environments.

Julien frames this as a recurring maintenance budget that every engineering team must accept. As he puts it, "if you don't spend at least one day per week updating the stuff, it's going to accumulate over a year or something. And then you have to spend two weeks fixing all that." The compound interest on security debt is steep.

### Tags, digests, signing, and private registries

Near the end of the episode, Mattias raises a practical deployment question: how should teams store and reference images securely? He contrasts mutable tags (which can be overwritten on Docker Hub) with immutable SHA-based digests, image signing, and private registries — and admits there are so many options it is hard to know where to start.

Julien recommends implementing all of these controls, but not all at once. He advocates for an incremental approach: define your security objectives, then build toward them layer by layer. Start with what gives the most immediate protection and expand from there.

The hosts do not present a single silver bullet. Instead, they emphasize defense in depth: scanning at every level (code dependencies, container base images, production images), signing for authenticity, private registries for access control, and infrastructure-level enforcement.

### Build pipeline security and handling secrets

The episode closes by touching on a problem the hosts agree deserves its own dedicated discussion: securing the build system itself.

Mattias points out that the build server has access to source code, credentials, signing keys, registries, and deployment systems. If an attacker compromises it, they can inject malicious code during the build process — effectively poisoning everything downstream.

The hosts then discuss the challenge of passing credentials into container builds for private dependencies. Andrey notes that recent Docker versions support passing SSH agents and secrets more safely during builds. He recommends using short-lived credentials (like AWS STS tokens with 15-minute expiration) so that even if credentials leak into image layers, they are already expired by the time anyone could exploit them. He also mentions using IMG, a daemonless image builder, as an alternative to Docker that avoids the need for a Docker daemon during builds.

Julien takes a different approach to runtime secrets: encrypting them with KMS and storing them in a cloud bucket, then fetching them only at container startup. He observes that the real cloud vendor lock-in is never the runtime — "it's always the IAM" — because authorization and access control mechanisms are deeply cloud-specific and difficult to migrate.

Julien adds that handling build secrets often becomes an awkward "dance" of fetching credentials, granting temporary access, and cleaning up afterward. It works, but it remains operationally clumsy.

The hosts agree that build server hardening and the connection between security and cost management (which Julien briefly mentions as natural partners, since understanding who has access to what benefits both) are topics worthy of their own future episodes.

## Highlights

### "You don't know what's inside — you only have a semantic guarantee."
Julien cuts through a common assumption in container security: signing an image proves origin, not safety. That distinction shapes the entire episode, as the hosts explore why authenticity, trust, and actual security are three separate problems.
Listen to this episode of DevSecOps Talks for a grounded discussion on what image signing can — and cannot — guarantee.

### "Containers were designed to be convenient, not secure by default."
Mattias makes one of the sharpest points of the episode: containers became popular because they are efficient and easy to operate, not because they provide strong isolation. The container "does not contain things, it's just an abstraction." That is why runtime hardening and vulnerability management still matter so much.
Listen to DevSecOps Talks to hear why container adoption created as many security questions as it solved.

### "Official on Docker Hub doesn't mean secure — scan a Jenkins image and you'd be surprised."
Julien challenges the idea that a branded or official image should be trusted blindly. Even well-known organization-backed images can contain a surprising number of CVEs, and reputable sources can still introduce malicious changes — intentionally or by mistake.
Listen to this DevSecOps Talks episode for a practical conversation about defining trust in your container supply chain.

### "The less code you have, the less vulnerability you have."
Julien sums up a recurring theme: smaller runtime images are not just cleaner — they are fundamentally safer. From DockerSlim shrinking a 600 MB Maven image to 140 MB, to Alpine and distroless approaches, the hosts argue for removing everything production does not absolutely need.
Listen to DevSecOps Talks to hear why image size and security are more connected than many teams realize.

### "Nginx gets a CVE? Now you have to rebuild your entire app."
Andrey highlights how containerization merged the OS patching cycle with the application delivery cycle. In the old world, ops could patch Nginx without touching the app. In the container world, every security update means a full image rebuild and redeploy — making security an application delivery concern, not just an infrastructure one.
Listen to this DevSecOps Talks episode for a practical take on why modern patching must flow through the CI/CD pipeline.

### "If you don't spend one day a week updating, you'll spend two weeks fixing it later."
Julien describes dependency and image maintenance as a non-negotiable recurring budget. Skip the updates and the security debt compounds fast — turning routine maintenance into an emergency remediation project.
Listen to DevSecOps Talks for an honest take on the operational cost of staying secure in containerized environments.

### "The real lock-in is never the runtime — it's always the IAM."
In a brief but pointed aside about handling secrets in containers, Julien observes that authorization and access control are the truly cloud-specific parts of any architecture. Runtime workloads can move; IAM policies cannot.
Listen to this DevSecOps Talks episode for a candid discussion on where the real complexity lies in cloud-native security.

## Resources

- **[SlimToolkit (formerly DockerSlim)](https://slimtoolkit.org/)** — Open-source tool that minifies container images by removing non-essential components, reducing image size and attack surface without code changes. Mentioned by Mattias in the episode.

- **[Google Distroless Container Images](https://github.com/GoogleContainerTools/distroless)** — Minimal container base images from Google that contain only the application and its runtime dependencies, stripping out shells, package managers, and OS utilities.

- **[Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)** — Official Docker documentation on using multiple build stages to produce smaller, cleaner production images by separating the build environment from the runtime image.

- **[Docker Content Trust](https://docs.docker.com/engine/security/trust/)** — Docker's built-in mechanism for cryptographic signing and verification of image integrity and publisher identity using Notary.

- **[Amazon ECR Image Scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html)** — AWS documentation on scanning container images for OS and language package vulnerabilities in Elastic Container Registry, mentioned by Julien as a practical alternative to paid Docker Hub scanning.

- **[Snyk Container](https://docs.snyk.io/scan-with-snyk/snyk-container)** — Developer security tool for scanning container images and application dependencies for known vulnerabilities, with remediation guidance and base image upgrade recommendations.

- **[Anchore Container Scanning](https://anchore.com/container-vulnerability-scanning/)** — SBOM-powered container vulnerability scanning platform, referenced by Andrey as the engine behind many registry-level CVE scanning capabilities.

- **[Alpine Linux Docker Image](https://hub.docker.com/_/alpine)** — Minimal 5 MB base image built on musl libc and BusyBox, widely used as a lightweight, security-conscious alternative to full Linux distribution base images.
