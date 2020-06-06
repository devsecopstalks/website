---
title: "Terraform in CI"
date: 2020-06-05T08:24:41+02:00
lastmod: 2020-06-05T08:24:41+02:00
episode: 1
author: 'DevSecOps Talks'
participants: ['Andrey', 'Mattias', 'Julien']
---

How do you start to implement a CI pipeline when dealing with infrastructure as code implemented via Terraform?
What are the security concerns when the credentials to the whole kingdom are used in an automated process?
In this episode, we discuss the various security and feasibility aspects of using Terraform in a CI pipeline.

<!--more-->
We start the episode by catching up with what we've been working on.
Feel free to skip to 11:52 if you want to go directly to the topic.
Having an automated process to deploy and manage infrastructure has advantages such as fast feedback and collaboration.
The code for the infrastructure is treated like an application that is versioned, tested and deployed.

<!-- Player -->

{{< podbean nt2wv-ded704 "DevSecOps Talks #9 - Terraform in CI" >}}

## Notes

- [Atlantis - Terraform Pull Request Automation ](https://www.runatlantis.io/)
- [HashiCorp Announces Free Tier for Terraform SaaS](https://www.hashicorp.com/resources/hashicorp-announces-terraform-saas-free-tier/)
- [Terraform Backend Types](https://www.terraform.io/docs/backends/types/index.html)
- [Handling Secrets in Terraform state](https://www.terraform.io/docs/extend/best-practices/sensitive-state.html)
