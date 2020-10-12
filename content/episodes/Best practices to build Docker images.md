---
title: "Best Practices to Build Docker Images"
date: 2020-09-11T13:18:01+02:00
lastmod: 2020-09-11T13:18:01+02:00
episode: 17
author: 'DevSecOps Talks'
participants: ['Andrey', 'Mattias', 'Julien']
---

Focus on the building containers.
In CI you need to maintain a separate docker engine. 
Passing secret, inspect to see if they still show up in the layers.
Keeping the images updated
Scanning for vulnerabilities
Caching - Have the build step order right
Using multistage build, a container to build another container


<!--more-->

<!-- Player -->

{{< podbean PODBEAN_ID "DevSecOps Talks #_NUM - TITLE" >}}

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
