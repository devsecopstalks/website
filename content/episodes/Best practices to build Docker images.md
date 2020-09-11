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

- [Hugo web site generator](https://gohugo.io)
