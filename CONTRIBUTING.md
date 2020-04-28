# Contributing

## Prerequisites

Fork this repository.

The GitHub documentation might help if you are unfamiliar with GitHub flow: https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/github-flow

## Setup

Download Hugo binary or install it as described [here](https://gohugo.io/getting-started/installing/)

```shell
git clone git@github.com:*YOUR_USERNAME*/website.git
cd website
git submodule update --init
```

## Build and serve on localhost

```shell
hugo server
open localhost:1313
```

## How to add new episode

```shell
hugo new episodes/TITLE_OF_SHOW
```

## Submit your changes

More details [creating a pull request from a fork](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request-from-a-fork)
