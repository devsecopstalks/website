---
title: "#19 - Deleting Resources in the Cloud"
date: 2020-11-23T12:53:39+02:00
lastmod: 2020-11-23T12:53:39+02:00
episode: 19
author: "DevSecOps Talks"
participants: ["Andrey", "Mattias", "Julien"]
aliases:
  - /episodes/deleting-resources/
---

How to decommission resources from your cloud environment to keep it clean? What to do when a resource is created without being in the infrastructure code? Andrey is going through a checklist he uses to delete resources and the utility serverless functions he wrote. Argo CD is a project that does GitOps and automatically deletes resources in Kubernetes namespaces if they are not defined. We talked about the different layers of abstraction for infrastructure as code and where it makes sense to have a Terraform controller in a Kubernetes cluster to manage the application dependencies.

[Discuss the episode or ask us anything on LinkedIn](https://www.linkedin.com/company/devsecops-talks/)

<!--more-->

<!-- Player -->

{{< podbean 3i6g8-f31893 "DEVSECOPS Talks #19 - Deleting Resources in the Cloud" >}}

## Notes

- [AuditD](https://www.elastic.co/beats/auditbeat)
- [GraphQL-mesh](https://graphql-mesh.com/)
- [Argo CD for GitOps](https://argoproj.github.io/argo-cd/)
