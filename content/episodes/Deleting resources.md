---
title: 'Deleting Resources In The Cloud'
date: 2020-11-23T12:53:39+02:00
lastmod: 2020-11-23T12:53:39+02:00
episode: 19
author: 'DevSecOps Talks'
participants: ['Andrey', 'Mattias', 'Julien']
---

How to decommission resources from your cloud environment to keep it clean?

What to do when a resource is created without being in the infrastructure code?

Andrey is going through a checklist he uses to delete resources and the utility serverless functions he wrote.

ArgoCD is a project that does GitOps and automatically delete resources in Kubernetes namespaces if they are not defined.

We talked about the different layers of abstraction for infrastructure as code and where it makes sense to have a terraform controller in a Kubernetes cluster to manage the application dependencies.


<!-- Player -->

{{< podbean 3i6g8-f31893 "DEVSECOPS Talks #19-2020 - Deleting Resources In The Cloud" >}}

## Notes

-   [AuditD](https://www.elastic.co/beats/auditbeat)
-   [GraphQL-mesh](https://graphql-mesh.com/)
-   [ArgoCD for GitOps](https://argoproj.github.io/argo-cd/)
