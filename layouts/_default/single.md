---
title: "{{ .Title }}"
date: {{ .Date.Format "2006-01-02" }}
episode: {{ .Params.episode }}
---

{{ .RawContent }}