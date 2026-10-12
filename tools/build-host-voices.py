#!/usr/bin/env python3
"""Build tools/host-voices.json from diarization labels the operator has named.

    uv run python build-host-voices.py 111:S1=Mattias 112:S2=Mattias 111:S2=Paulina 112:S1=Andrey
    uv run python build-host-voices.py ... 110:S2        # unnamed = held-out check
    uv run python build-host-voices.py ... --write

Labels are the diarizer ids (``S1``) in ``out/episodeNNN-diarization.json``,
not the ``[A]`` turn labels. Prints the minutes and the cosine matrix first and
writes only with --write: the clusters must be checked by ear before a voice is
named, and a merged label (two people under one id) poisons a print.

Rebuild after every FluidAudio pin bump in do.sh; matching refuses stale prints.
"""

import argparse
import json
import os
import re
import sys

import voice_match as vm

DEFAULT_OUT_DIR = os.path.join(vm.TOOLS_DIR, "out")


def parse_source(spec):
    """``111:S2=Paulina`` or ``episode111:S2`` -> (episode, label, host full name or None)."""
    m = re.fullmatch(r"(?:episode)?(\d+):([^=]+)(?:=(.+))?", spec)
    if not m:
        raise argparse.ArgumentTypeError(f"{spec!r} is not EPISODE:LABEL[=HOST]")
    host = m.group(3)
    if host is not None:
        canonical = vm.canonical_host(host)
        if canonical is None:
            raise argparse.ArgumentTypeError(f"{host!r} is not one of {', '.join(vm.HOSTS)}")
        host = canonical
    return f"episode{int(m.group(1)):03d}", m.group(2), host


def load_sources(specs, out_dir):
    """Resolve each source to its LabelVoice, reading each episode once."""
    cache, sources = {}, []
    for episode, label, host in specs:
        if episode not in cache:
            path = os.path.join(out_dir, f"{episode}-diarization.json")
            with open(path, "r", encoding="utf-8") as f:
                cache[episode] = vm.label_embeddings(json.load(f))
        voices = cache[episode]
        if label not in voices:
            raise SystemExit(f"{episode} has no label {label}; it has {', '.join(sorted(voices))}")
        sources.append((episode, label, host, voices[label]))
    return sources


def source_name(episode, label):
    return f"{episode.removeprefix('episode').lstrip('0')}:{label}"


def build_prints(sources):
    """One print per named host: duration-weighted mean across its sources."""
    by_host = {}
    for episode, label, host, voice in sources:
        if host:
            by_host.setdefault(host, []).append((episode, label, voice))
    return {
        host: {
            "embedding": vm.weighted_mean((v.embedding, v.seconds) for _, _, v in items),
            "sources": [
                {"episode": ep, "label": lab, "seconds": round(v.seconds, 1)}
                for ep, lab, v in items
            ],
        }
        for host, items in by_host.items()
    }


def report(sources, prints):
    names = [source_name(ep, lab) for ep, lab, _, _ in sources]
    width = max(len(n) for n in names + ["source"])

    print("Sources:")
    for (ep, lab, host, voice), name in zip(sources, names):
        print(f"  {name.ljust(width)}  {voice.minutes:5.1f} min  {host or '(held out)'}")

    print("\nCosine similarity between sources:")
    print(" " * (width + 2) + " ".join(n.rjust(7) for n in names))
    for (_, _, _, a), name in zip(sources, names):
        row = " ".join(f"{vm.cosine(a.embedding, b.embedding):7.2f}" for _, _, _, b in sources)
        print(f"  {name.ljust(width)}{row}")

    if not prints:
        return
    hosts = sorted(prints)
    print("\nProposed host clusters:")
    for host in hosts:
        members = [(ep, lab, v) for ep, lab, h, v in sources if h == host]
        pairs = [
            vm.cosine(a.embedding, b.embedding)
            for i, (_, _, a) in enumerate(members) for _, _, b in members[i + 1:]
        ]
        within = f"within {min(pairs):.2f}-{max(pairs):.2f}" if pairs else "single source"
        listed = ", ".join(source_name(ep, lab) for ep, lab, _ in members)
        print(f"  {host}: {listed} ({within})")

    print("\nEvery source against each print (matched at >= "
          f"{vm.MATCH_THRESHOLD:.2f}):")
    print(" " * (width + 2) + " ".join(h.rjust(9) for h in hosts) + "  closest")
    for (_, _, host, voice), name in zip(sources, names):
        scores = {h: vm.cosine(voice.embedding, prints[h]["embedding"]) for h in hosts}
        best = max(scores, key=scores.get)
        verdict = best if scores[best] >= vm.MATCH_THRESHOLD else "guest"
        row = " ".join(f"{scores[h]:9.2f}" for h in hosts)
        print(f"  {name.ljust(width)}{row}  {verdict}")

    print("\nBetween prints:")
    for i, a in enumerate(hosts):
        for b in hosts[i + 1:]:
            print(f"  {a} vs {b}: {vm.cosine(prints[a]['embedding'], prints[b]['embedding']):.2f}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sources", nargs="+", type=parse_source,
                        help="EPISODE:LABEL=HOST to build from, or EPISODE:LABEL to only compare")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR,
                        help="directory holding episodeNNN-diarization.json (default: tools/out)")
    parser.add_argument("--output", default=vm.HOST_VOICES_PATH, help="file to write")
    parser.add_argument("--write", action="store_true",
                        help="write the prints; without it only the report is printed")
    args = parser.parse_args(argv)

    sources = load_sources(args.sources, args.out_dir)
    prints = build_prints(sources)
    report(sources, prints)

    if not args.write:
        print("\nNothing written; re-run with --write once the clusters are confirmed.")
        return 0
    missing = [h for h in vm.HOSTS if h not in prints]
    if missing:
        print(f"\nError: no source names {', '.join(missing)}; every host needs a print.")
        return 1
    dims = {len(p["embedding"]) for p in prints.values()}
    data = {
        "fluidaudio_commit": vm.fluidaudio_pin(),
        "dims": dims.pop(),
        "hosts": {
            host: {
                "embedding": [round(x, 6) for x in prints[host]["embedding"]],
                "sources": prints[host]["sources"],
            }
            for host in vm.HOSTS
        },
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"\n✓ Wrote {args.output} ({', '.join(vm.HOSTS)}, {data['dims']} dims)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
