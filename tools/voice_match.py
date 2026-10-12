#!/usr/bin/env python3
"""Name diarized speakers by voice: match per-label embeddings to stored host prints.

FluidAudio's diarization JSON carries a 256-dim speaker embedding on every
segment (one vector per label, repeated). Measured on episodes 111 and 112, the
same host scores 0.91 cosine across episodes and different people 0.18-0.39. A
label therefore matches a host above MATCH_THRESHOLD and is a guest well below
it; the band between is flagged for the operator.

The embedding is per label, so a label that merged two people cannot be split
here. The fix is a re-diarize pinned to the right count
(``transcribe_local.rediarize``). Prints are rebuilt with
``tools/build-host-voices.py`` whenever the FluidAudio pin in ``do.sh`` moves.

``confirm_speakers`` is the operator prompt; everything else is pure.
"""

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field, replace

from transcribe_local import rediarize, segment_speaker, speaker_labels

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
HOST_VOICES_PATH = os.path.join(TOOLS_DIR, "host-voices.json")
DO_SH_PATH = os.path.join(TOOLS_DIR, "do.sh")

HOSTS = ("Andrey Devyatkin", "Mattias Hemmingsson", "Paulina Dubas")
GUEST = "guest"

MATCH_THRESHOLD = 0.8
# Below this a label is simply a guest. Between it and MATCH_THRESHOLD (a label
# that merged a host with someone else lands here) the label is still named a
# guest, but flagged for the operator to confirm.
GUEST_CEILING = 0.55
# A best host this close to the runner-up is a coin toss, not a match.
SECOND_BEST_MARGIN = 0.05

SAME_HOST_PREFIX = "same host as "
SPEAKERS_SUFFIX = "-speakers.json"


class VoicePrintError(RuntimeError):
    """host-voices.json is missing, malformed, or built with another FluidAudio pin."""


class SpeakerConfirmationError(RuntimeError):
    """The voice confirmation cannot finish; ``checkpoint`` names the file to look at."""

    def __init__(self, message, checkpoint=None):
        super().__init__(message)
        self.checkpoint = checkpoint


@dataclass(frozen=True)
class LabelVoice:
    label: str
    embedding: tuple  # unit length
    seconds: float

    @property
    def minutes(self):
        return self.seconds / 60


@dataclass(frozen=True)
class HostVoice:
    name: str
    embedding: tuple  # unit length
    sources: tuple  # ({"episode": ..., "label": ..., "seconds": ...}, ...)


@dataclass(frozen=True)
class SpeakerMatch:
    label: str
    host: str | None  # None = guest
    closest_host: str  # the best-scoring host, matched or not
    score: float  # against closest_host
    second_host: str | None
    second_score: float | None
    minutes: float
    flags: tuple = field(default_factory=tuple)
    overridden: bool = False

    @property
    def name(self):
        return self.host or GUEST


@dataclass(frozen=True)
class Confirmation:
    """The operator's answer: ``accept`` (Enter), ``rediarize`` or ``overrides``."""
    kind: str
    num_speakers: int | None = None
    overrides: dict = field(default_factory=dict)


def _unit(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        raise ValueError("zero-length embedding")
    return tuple(x / norm for x in vec)


def cosine(a, b):
    """Cosine similarity of two unit vectors."""
    if len(a) != len(b):
        raise ValueError(f"embedding dims differ: {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))


def weighted_mean(vectors_and_weights):
    """Unit-length weighted mean of unit vectors; weights are seconds spoken."""
    pairs = list(vectors_and_weights)
    dims = len(pairs[0][0])
    acc = [0.0] * dims
    for vec, weight in pairs:
        if len(vec) != dims:
            raise ValueError(f"embedding dims differ: {len(vec)} vs {dims}")
        for i, x in enumerate(vec):
            acc[i] += x * weight
    return _unit(acc)


def fluidaudio_pin(do_sh=DO_SH_PATH):
    """The FluidAudio commit do.sh builds; the embedding model follows it."""
    with open(do_sh, "r", encoding="utf-8") as f:
        match = re.search(r'^FLUIDAUDIO_COMMIT="([0-9a-f]+)"', f.read(), re.MULTILINE)
    if not match:
        raise VoicePrintError(f"no FLUIDAUDIO_COMMIT pin found in {do_sh}")
    return match.group(1)


def canonical_host(name, hosts=HOSTS):
    """Full host name for a full or first name, any case; None if not a host."""
    key = (name or "").strip().lower()
    for host in hosts:
        if key in (host.lower(), host.split()[0].lower()):
            return host
    return None


def label_embeddings(diarization, asr=None):
    """Per-label voice: duration-weighted mean embedding and seconds spoken.

    With ``asr`` the keys are the ``-turns.json`` labels (``A``, ``B``...), and
    ids that won no word are dropped since no turn carries them. Without it the
    keys are the diarizer's ids (``S1``...), which is what the builder records.
    """
    names = speaker_labels(asr, diarization) if asr is not None else None

    by_id = {}
    for seg in diarization.get("segments") or []:
        sid = segment_speaker(seg)
        emb = seg.get("embedding")
        seconds = seg["endTimeSeconds"] - seg["startTimeSeconds"]
        if not emb or seconds <= 0:
            continue
        by_id.setdefault(sid, []).append((_unit(emb), seconds))

    voices = {}
    for sid, pairs in by_id.items():
        if names is not None and sid not in names:
            continue
        label = names[sid] if names is not None else str(sid)
        voices[label] = LabelVoice(
            label=label,
            embedding=weighted_mean(pairs),
            seconds=sum(seconds for _, seconds in pairs),
        )
    return voices


def load_host_voices(path=HOST_VOICES_PATH, current_pin=None):
    """Load the host prints, refusing ones built with a different FluidAudio pin.

    A model bump moves every embedding, so stale prints would name the wrong
    people with confident scores rather than fail.
    """
    rebuild = (
        "Rebuild it with tools/build-host-voices.py from clean host labels "
        "(see the builder's --help), then re-run."
    )
    if not os.path.exists(path):
        raise VoicePrintError(f"{path} not found. {rebuild}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pin = current_pin or fluidaudio_pin()
    built_with = data.get("fluidaudio_commit")
    if built_with != pin:
        raise VoicePrintError(
            f"{os.path.basename(path)} was built with FluidAudio {built_with or '(unknown)'}, "
            f"but do.sh pins {pin}. Voice prints from another model version do not "
            f"compare. {rebuild}"
        )

    dims = data.get("dims")
    hosts = {}
    for name, entry in (data.get("hosts") or {}).items():
        emb = entry.get("embedding") or []
        if len(emb) != dims:
            raise VoicePrintError(f"{path}: {name} has {len(emb)} dims, file says {dims}")
        hosts[name] = HostVoice(
            name=name,
            embedding=_unit(emb),
            sources=tuple(entry.get("sources") or ()),
        )
    if not hosts:
        raise VoicePrintError(f"{path} holds no host prints. {rebuild}")
    return hosts


def _flag_shared_hosts(matches):
    """Re-derive the same-host flags; an override in the group settles it."""
    groups = {}
    for m in matches:
        if m.host is not None:
            groups.setdefault(m.host, []).append(m)

    out = []
    for m in matches:
        flags = tuple(f for f in m.flags if not f.startswith(SAME_HOST_PREFIX))
        group = groups.get(m.host, [])
        if len(group) > 1 and not any(g.overridden for g in group):
            others = ", ".join(g.label for g in group if g.label != m.label)
            flags += (f"{SAME_HOST_PREFIX}{others}",)
        out.append(replace(m, flags=flags))
    return out


def match_speakers(label_voices, host_voices):
    """Match each label to its closest host above MATCH_THRESHOLD, else a guest.

    Returned in label order. ``flags`` lists why a match needs the operator's
    eye; an empty tuple means it can be accepted as is.
    """
    matches = []
    for label in sorted(label_voices, key=lambda s: (len(s), s)):
        voice = label_voices[label]
        ranked = sorted(
            ((cosine(voice.embedding, h.embedding), name) for name, h in host_voices.items()),
            reverse=True,
        )
        best_score, best_host = ranked[0]
        second_score, second_host = ranked[1] if len(ranked) > 1 else (None, None)
        host = best_host if best_score >= MATCH_THRESHOLD else None
        if host is None:
            flags = (
                (f"below {MATCH_THRESHOLD:.2f}, closest is {best_host}",)
                if best_score >= GUEST_CEILING else ()
            )
        elif second_score is not None and best_score - second_score < SECOND_BEST_MARGIN:
            flags = (f"within {SECOND_BEST_MARGIN:.2f} of {second_host} ({second_score:.2f})",)
        elif second_score is not None and second_score >= MATCH_THRESHOLD:
            # Distinct hosts score well below the bar against each other, so
            # clearing it for two means one label holds two people.
            flags = (f"also matches {second_host} ({second_score:.2f}), likely two people",)
        else:
            flags = ()
        matches.append(SpeakerMatch(
            label=label,
            host=host,
            closest_host=best_host,
            score=best_score,
            second_host=second_host,
            second_score=second_score,
            minutes=voice.minutes,
            flags=flags,
        ))
    return _flag_shared_hosts(matches)


def apply_overrides(matches, overrides):
    """Apply ``{label: host or None}``; an overridden label carries no flags.

    Two labels set to the same host are one person on purpose, so neither keeps
    a same-host flag, and nor does an automatic match the override agrees with.
    """
    unknown = set(overrides) - {m.label for m in matches}
    if unknown:
        raise ValueError(f"unknown speaker label(s): {', '.join(sorted(unknown))}")
    updated = [
        replace(m, host=overrides[m.label], flags=(), overridden=True)
        if m.label in overrides else m
        for m in matches
    ]
    return _flag_shared_hosts(updated)


def unresolved(matches):
    """Matches still flagged; Enter is refused while this is non-empty."""
    return [m for m in matches if m.flags]


def parse_confirmation(text, labels, hosts=HOSTS):
    """Parse the operator's answer to the voice confirmation.

    Empty is Enter (accept), a bare number re-diarizes pinned to it, and
    ``C=guest`` / ``c=mattias`` pairs (comma or space separated) rename labels.
    Raises ValueError with an operator-facing message on anything else.
    """
    text = (text or "").strip()
    if not text:
        return Confirmation("accept")
    if text.isdigit():
        count = int(text)
        if count < 1:
            raise ValueError("speaker count must be at least 1")
        return Confirmation("rediarize", num_speakers=count)

    by_label = {label.lower(): label for label in labels}
    overrides = {}
    for token in re.split(r"[,\s]+", text):
        if not token:
            continue
        label, sep, name = token.partition("=")
        if not sep or not label or not name:
            raise ValueError(
                f"{token!r} is not LABEL=NAME; use e.g. {labels[0] if labels else 'A'}=guest "
                "or a speaker count"
            )
        canonical = by_label.get(label.lower())
        if canonical is None:
            raise ValueError(f"unknown label {label!r}; labels are {', '.join(labels)}")
        if name.lower() == GUEST:
            overrides[canonical] = None
            continue
        host = canonical_host(name, hosts)
        if host is None:
            first_names = ", ".join(h.split()[0] for h in hosts)
            raise ValueError(f"{name!r} is not a host; use {GUEST} or one of {first_names}")
        overrides[canonical] = host
    return Confirmation("overrides", overrides=overrides)


def format_matches(matches):
    """The confirmation table: label, name, closest host, runner-up, minutes, ⚠ reasons."""
    rows = [("Label", "Name", "Closest", "Next best", "Min", "")]
    for m in matches:
        name = m.name + (" (set)" if m.overridden else "")
        closest = f"{m.closest_host} {m.score:.2f}"
        nxt = f"{m.second_host} {m.second_score:.2f}" if m.second_host else "-"
        warn = "⚠ " + "; ".join(m.flags) if m.flags else ""
        rows.append((m.label, name, closest, nxt, f"{m.minutes:.1f}", warn))
    widths = [max(len(r[i]) for r in rows) for i in range(5)]
    lines = []
    for r in rows:
        cells = [r[i].ljust(widths[i]) if i < 4 else r[i].rjust(widths[i]) for i in range(5)]
        lines.append(("  " + "  ".join(cells) + ("  " + r[5] if r[5] else "")).rstrip())
    return "\n".join(lines)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_saved_overrides(speakers_file, diarization_sha):
    """Overrides confirmed on an earlier run against this same diarization, else {}."""
    try:
        saved = _read_json(speakers_file)
    except (OSError, ValueError):
        return {}
    if not isinstance(saved, dict) or saved.get("diarization_sha256") != diarization_sha:
        return {}
    overrides = saved.get("overrides")
    if not isinstance(overrides, dict):
        return {}
    if any(v is not None and v not in HOSTS for v in overrides.values()):
        return {}
    return dict(overrides)


def save_confirmation(speakers_file, diarization_sha, matches, overrides):
    data = {
        "diarization_sha256": diarization_sha,
        "speakers": {m.label: m.host or GUEST for m in matches},
        "overrides": overrides,
    }
    with open(speakers_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def confirm_speakers(audio_path, out_base, input_func=input, host_voices=None,
                     rediarize_func=rediarize):
    """Name each diarized label by voice print and have the operator confirm it.

    Returns ``({label: host full name}, transcript)``: hosts only (a guest
    label is absent), and the transcript is the re-diarized ``[A]: ...`` text
    when the operator pinned a new count, else None. Overrides confirmed for
    the same diarization are re-applied from ``-speakers.json``. Raises
    SpeakerConfirmationError when it cannot finish.
    """
    speakers_file = f"{out_base}{SPEAKERS_SUFFIX}"
    diarization_file = f"{out_base}-diarization.json"
    if host_voices is None:
        try:
            host_voices = load_host_voices()
        except VoicePrintError as e:
            raise SpeakerConfirmationError(str(e), checkpoint=HOST_VOICES_PATH) from e
    try:
        asr = _read_json(f"{out_base}-asr.json")
    except (OSError, ValueError) as e:
        raise SpeakerConfirmationError(
            f"cannot read the saved ASR for voice matching ({e}); transcribe the episode again",
            checkpoint=f"{out_base}-asr.json",
        ) from e

    transcript = None
    reload = True
    while True:
        if reload:
            try:
                diarization = _read_json(diarization_file)
            except (OSError, ValueError) as e:
                raise SpeakerConfirmationError(
                    f"cannot read the diarization ({e}); transcribe the episode again",
                    checkpoint=diarization_file,
                ) from e
            diarization_sha = _sha256_file(diarization_file)
            base = match_speakers(label_embeddings(diarization, asr), host_voices)
            overrides = load_saved_overrides(speakers_file, diarization_sha)
            try:
                matches = apply_overrides(base, overrides)
            except ValueError:
                overrides, matches = {}, base
            if overrides:
                print("(the renames confirmed on an earlier run are applied)")
            reload = False

        open_flags = unresolved(matches)
        print("\nVoices heard (labels as in the transcript):")
        print(format_matches(matches))
        print(
            "Enter accepts; C=guest or C=Mattias renames a label; a number re-diarizes "
            "pinned to that many voices: ",
            end="",
            flush=True,
        )
        try:
            raw = input_func()
        except EOFError:
            if open_flags:
                raise SpeakerConfirmationError(
                    "voice matches need confirming ("
                    + ", ".join(m.label for m in open_flags)
                    + " flagged) and no answer was given; re-run in a terminal",
                    checkpoint=speakers_file,
                ) from None
            print("\n(no input available — accepting the voice matches)")
            raw = ""
        try:
            answer = parse_confirmation(raw, [m.label for m in matches])
        except ValueError as e:
            print(f"⚠ {e}")
            continue

        if answer.kind == "rediarize":
            print(f"Re-diarizing pinned to {answer.num_speakers} voice(s); the ASR is reused…")
            try:
                transcript = rediarize_func(audio_path, out_base, answer.num_speakers)
            except Exception as e:  # noqa: BLE001 - ffmpeg and fluidaudiocli fail differently
                raise SpeakerConfirmationError(
                    f"re-diarization failed: {e}", checkpoint=diarization_file
                ) from e
            reload = True
        elif answer.kind == "overrides":
            overrides = {**overrides, **answer.overrides}
            matches = apply_overrides(base, overrides)
        elif open_flags:
            print(
                "⚠ Not accepted while flagged: "
                + "; ".join(f"{m.label} {', '.join(m.flags)}" for m in open_flags)
                + ". Rename the label or re-diarize with a count."
            )
        else:
            save_confirmation(speakers_file, diarization_sha, matches, overrides)
            print(f"✓ Speakers confirmed: {speakers_file}")
            return {m.label: m.host for m in matches if m.host}, transcript


def hosts_present(speaker_names, hosts=HOSTS):
    """Hosts heard, in ``hosts`` order."""
    heard = set(speaker_names.values())
    return [host for host in hosts if host in heard]
