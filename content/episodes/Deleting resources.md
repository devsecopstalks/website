---
title: 'Deleting Resources'
date: 2020-09-23T12:53:39+02:00
lastmod: 2020-09-23T12:53:39+02:00
episode: 18
author: 'DevSecOps Talks'
participants: ['Andrey', 'Mattias', 'Julien']
---

How to decomission resources from your cloud environment in order to keep it clean?

What to do when a resource is created without being in the infrastructure code ?

Andrey is going through a checklist he is using in order to deleting resources and the utility severless functions he wrote.

ArgoCD is a project that does GitOps and automatically delete resources in a kubernetes namespaces if they are not defined.

We talked about the different layers of abstraction for infrastructure as code and where it make sense to have a terraform controller in a kubernetes cluster to manage the application dependencies.


<!-- Player -->

{{< podbean PODBEAN_ID "DevSecOps Talks #_NUM - TITLE" >}}

## Notes

-   [AuditD](ANDREY CAN ADD THE LINK HERE)
-   [GraphQL-mesh](https://graphql-mesh.com/)
-   [ArgoCD for GitOps](https://argoproj.github.io/argo-cd/)
