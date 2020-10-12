---
title: "Best Practices for Building Docker Images"
date: 2020-10-12T13:18:01+02:00
lastmod: 2020-10-12T13:18:01+02:00
episode: 17
author: 'DevSecOps Talks'
participants: ['Andrey', 'Mattias', 'Julien']
---

This is the first episode in the new format - 30 minutes short and crisp episodes, i.e., less water and side discussions, focusing on the topic,  duration under (well, almost under) 30 minutes. We hope you like it!

The topic of this episode is building docker images - automation, security, best practices.

In this episode, we discuss:
Saving money with T3a family
Building Docker images locally and in CI
Setting up deamonless Docker builds for CI and k8s
Using multistage builds to keep your images nice and clean as well as encapsulate the build environment and make it portable
Passing secrets to Docker build and inspecting image layers for secrets (ssh-agent and many more)
Keeping Docker images updated with dependencies and updates
Scanning Docker images for vulnerabilities
Docker image layers caching - doing it right
DockerHub is to delete old images stored for free, and GitHub is ready to host them for you
Docker image naming so you can find all you need to debug quickly

In some of the information overlaps with episode #3 but greatly extends information provided before https://devsecops.fm/episodes/docker-secure-build/

<!--more-->

<!-- Player -->

{{< podbean w79in-ef1a02 "DevSecOps Talks #17 - Best Practices for Building Docker Images" >}}

## Notes

- [Docker BuildKit](https://github.com/moby/buildkit/blob/master/frontend/dockerfile/docs/experimental.md)
- [img](https://github.com/genuinetools/img)
- [kaniko](https://github.com/GoogleContainerTools/kaniko)
- [buildah](https://github.com/containers/buildah)
- [Using Secrets in build](https://docs.docker.com/develop/develop-images/build_enhancements/#new-docker-build-secret-information)
- [Docker Slim](https://github.com/docker-slim/docker-slim)
- [distroless](https://github.com/GoogleContainerTools/distroless)
- [Docker resource comsumption](https://www.docker.com/pricing/resource-consumption-updates)
- [Container registry to self-host](https://github.com/docker/distribution)
- [Awesome Docker](https://awesome-docker.netlify.app/)
