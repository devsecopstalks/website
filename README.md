# DevSecOps Talks podcast

<div align="center">
    <br/>
    <br/>
    <br/>
	<img src="static/images/logo.png" alt="DevSecOps Talks Logo">
    <br/>
    <br/>
    <br/>
    <br/>
    <br/>
</div>

## We talk like no one is listening except that we record it

This is the show by and for DevSecOps practitioners who are trying to survive information overload, get through marketing nonsense, do right technology bets, help their organizations to deliver value and last but not the least to have some fun. Tune in for talks about technology, ways of working and news from DevSecOps.

We created this podcast because we realized that we were not the only ones to struggle with security on a daily basis.
It is also difficult to find information without marketing content or a product pitch.
We don't intend to sell anything, now or later.

This show is not sponsored by any technology vendor and we are trying to be as unbiased as possible.
We talk like no one is listening! For good or bad 😉.

### What is DevSecOps

As DevOps improved the collaboration between developers (dev) and operations (ops),
DevSecOps includes security aspects into the development and operation of applications.
It adds the dimension of security to a DevOps culture.

Enjoy the talks and feel free to participate.

## Contribute

### Setup

Download Hugo binary or install it as described [here](https://gohugo.io/getting-started/installing/)

```shell
git clone git@github.com:devsecopstalks/website.git
cd website
git submodule update --init
```

### Build and serve on localhost

```shell
hugo server
open localhost:1313
```

### How to add new episode

```shell
hugo new episodes/"TITLE OF SHOW.md"
```

## Podcast release process

### Preparations
* Discuss the topic for the podcast in [Next Episode thread](https://devsecops.fm/episodes/next-episode/)
* Prepare agenda
* Setup Zencast/Zoom links and send them out in the intvitation to participants

### Postproduction
* Collect all mp3 files (usually done automatically via Zencastr) and store them on [Google drive](https://drive.google.com/drive/u/0/folders/1Fg3pSPTydOijaT9ojtvZu6cOf9BSopCx)
* Process them into one, add intro and closing, align volume, cut what shouldn't be there (Mattias knows how, need to document more)
* Upload file to Podbean (Login details are in Bitwarden)
* Add new episode on Podbean as draft, do not publish at the moment
* Update website - add new episode, write description, add show notes, link podcast from Podbean
* Post a link to Gitter
* Everyone to review description for grammar mistakes, accuracy etc. Add show notes
* Make sure that description on Podbean matches description on the website after review and edits plus edit the following line `Visit https://devsecops.fm to see show notes and https://gitter.im/devsecopstalks/community to join a discussion`
* Share podcast on Podbean
* Visit podcast episode webpage and subscribe for Disqus updates
* Hit social media
