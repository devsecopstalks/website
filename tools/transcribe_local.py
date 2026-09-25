#!/usr/bin/env python3
"""Local transcription on Apple Silicon: Parakeet ASR + VBx diarization via FluidAudio.

The default backend; OpenAI ``gpt-4o-transcribe-diarize`` is the opt-in
fallback. Two CLI passes over a
single 16 kHz mono WAV -- no chunking, because Parakeet transcribes a full
45-minute episode in one pass -- and the results are merged here: FluidAudio has
no combined command, so joining word timings to speaker spans is code this
project owns.

Diarization uses ``process --mode offline`` (VBx clustering) rather than
``sortformer``. Measured on a 33.6-minute, three-host episode: VBx pinned to
three speakers reproduces sortformer's speaker shares (50.3/25.4/24.3% vs
49.7/26.3/23.8%) in 8.7 s instead of 152.8 s, emits no spurious one-word turns,
and -- because the count is pinned -- cannot invent the phantom fourth speaker
both sortformer and OpenAI produced on that episode. It also has no 4-speaker
ceiling, which sortformer does.

``tools/do.sh`` builds the pinned FluidAudio CLI and owns the pin;
``podbean.py`` owns the ``TRANSCRIBE_BACKEND`` switch that selects
between this module and the OpenAI path.
"""

import bisect
import json
import os
import shutil
import subprocess
import tempfile

FLUIDAUDIO_DIR = os.environ.get(
    "FLUIDAUDIO_DIR", os.path.expanduser("~/.cache/fluidaudio/devsecopstalks")
)

# v2 is the benchmarked ASR model (v3 is the CLI default). On four reference
# episodes v2 ran at 119-380x real time with ~13% word divergence from OpenAI.
PARAKEET_MODEL_VERSION = "v2"

# Merge tuning. A diarization boundary rarely lands exactly between two words,
# so a speaker change is nudged to the most plausible nearby split: the biggest
# pause, with a bonus for a sentence end. Without this, turns start mid-sentence
# ("...wouldn't write any" / "code. I actually...").
BOUNDARY_MAX_SHIFT_WORDS = 4
SENTENCE_END_BONUS_S = 0.35
# Only move on real evidence. The diarizer's own boundary is the prior; a
# marginally better-looking split nearby is not a reason to override it. A word
# clamp bounds the damage of a bad move; a time clamp was tried and rejected,
# since a long pause is both the strongest split signal and, by definition, the
# furthest away in time.
MIN_SNAP_IMPROVEMENT_S = 0.05


def resolve_cli():
    """Return the fluidaudiocli path, or raise with build instructions."""
    override = os.environ.get("FLUIDAUDIO_CLI")
    if override:
        if not os.path.exists(override):
            raise RuntimeError(f"FLUIDAUDIO_CLI={override} does not exist")
        return override

    cli = os.path.join(FLUIDAUDIO_DIR, ".build", "release", "fluidaudiocli")
    if not os.path.exists(cli):
        raise RuntimeError(
            f"fluidaudiocli not found at {cli}.\n"
            "There is no Homebrew formula; tools/do.sh builds it from source. "
            "Run tools/do.sh, or set FLUIDAUDIO_CLI to an existing binary."
        )
    return cli


def to_wav(audio_path, verbose=False):
    """Convert audio to the 16 kHz mono PCM WAV both FluidAudio models expect."""
    fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="fluidaudio-")
    os.close(fd)
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-i", audio_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        wav_path, "-loglevel", "error",
    ]
    if verbose:
        print(f"  ffmpeg -> {wav_path}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        os.unlink(wav_path)
        raise RuntimeError(f"ffmpeg failed converting {audio_path}: {e.stderr}") from e
    return wav_path


def _run_cli(cli, args, label, verbose=False):
    """Run one fluidaudiocli subcommand, surfacing its output on failure."""
    if verbose:
        print(f"  {' '.join([os.path.basename(cli)] + args)}")
    result = subprocess.run(
        [cli] + args, capture_output=True, text=True, timeout=3600
    )
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip()[-2000:]
        raise RuntimeError(f"fluidaudiocli {label} failed (exit {result.returncode}):\n{tail}")
    return result


def run_asr(cli, wav_path, out_json, verbose=False):
    """Transcribe the whole file with Parakeet, keeping word-level timings."""
    print(f"Transcribing locally with Parakeet {PARAKEET_MODEL_VERSION}...")
    _run_cli(
        cli,
        ["transcribe", wav_path,
         "--model-version", PARAKEET_MODEL_VERSION,
         "--word-timestamps",
         "--output-json", out_json],
        "transcribe",
        verbose=verbose,
    )
    with open(out_json, "r", encoding="utf-8") as f:
        asr = json.load(f)
    print(
        f"✓ ASR complete ({len(asr.get('wordTimings') or [])} words, "
        f"{asr.get('processingTimeSeconds', 0):.1f}s, {asr.get('rtfx', 0):.0f}x real time)"
    )
    return asr


def run_diarization(cli, wav_path, out_json, num_speakers=None, verbose=False):
    """Diarize with VBx offline clustering, pinning the speaker count when known."""
    args = ["process", wav_path, "--mode", "offline", "--output", out_json]
    if num_speakers:
        args += ["--num-speakers", str(num_speakers)]
        print(f"Diarizing locally (VBx offline, pinned to {num_speakers} speakers)...")
    else:
        print("Diarizing locally (VBx offline, speaker count auto-detected)...")

    _run_cli(cli, args, "process", verbose=verbose)
    with open(out_json, "r", encoding="utf-8") as f:
        dia = json.load(f)

    segments = dia.get("segments") or []
    if not segments:
        raise RuntimeError(f"diarization produced no segments ({out_json})")

    found = dia.get("speakerCount")
    # A pin that was not honoured means the transcript has a different number of
    # voices than the operator said. Surface it rather than trusting the request.
    if num_speakers and found is not None and found != num_speakers:
        print(
            f"⚠ Asked for {num_speakers} speakers but diarization returned {found}. "
            "Speaker labels may merge or split real people; check the transcript."
        )
    print(
        f"✓ Diarization complete ({found if found is not None else '?'} speakers, "
        f"{len(segments)} segments, {dia.get('processingTimeSeconds', 0):.1f}s)"
    )
    return dia


def _segment_speaker(seg):
    """Speaker key for either schema: VBx uses speakerId, sortformer speakerIndex."""
    return seg["speakerId"] if "speakerId" in seg else seg["speakerIndex"]


def _assign_speakers(words, segments):
    """Label each word with the speaker span it overlaps most, else None."""
    segs = sorted(segments, key=lambda s: s["startTimeSeconds"])
    starts = [s["startTimeSeconds"] for s in segs]

    # Running max of end times. Segments may nest or overlap (sortformer emits
    # overlap-aware spans, and VBx does with --overlapping-segments), so the
    # covering segment can sit arbitrarily far back in start order. This lets the
    # backward scan stop exactly when no earlier segment can still reach the word,
    # instead of guessing a fixed lookback.
    max_end, running = [], float("-inf")
    for s in segs:
        running = max(running, s["endTimeSeconds"])
        max_end.append(running)

    labels = []
    for w in words:
        a, b = w["startTime"], w["endTime"]
        # Segments at or past this index start after the word ends.
        j = bisect.bisect_right(starts, b) - 1
        best, best_overlap = None, 0.0
        while j >= 0 and max_end[j] > a:
            s = segs[j]
            overlap = min(b, s["endTimeSeconds"]) - max(a, s["startTimeSeconds"])
            if overlap > best_overlap:
                best, best_overlap = _segment_speaker(s), overlap
            j -= 1
        labels.append(best)

    # If nothing matched at all, the two passes disagree about the timebase (or a
    # schema changed). Filling would then label the whole episode as one speaker,
    # which reads as a plausible transcript instead of an obvious failure.
    if all(lab is None for lab in labels):
        raise RuntimeError(
            "no word overlapped any speaker segment; ASR and diarization "
            "timestamps do not line up (check both ran on the same audio)"
        )

    # Words in the gaps between speech segments carry the previous speaker.
    # Speaker "0" is falsy, so test for None explicitly.
    last = next((x for x in labels if x is not None), None)
    for i, lab in enumerate(labels):
        if lab is None:
            labels[i] = last
        else:
            last = lab
    return labels


def _split_score(words, i):
    """How good a speaker-change point the gap before word i is, in seconds."""
    gap = words[i]["startTime"] - words[i - 1]["endTime"]
    if words[i - 1]["word"].strip().endswith((".", "?", "!")):
        gap += SENTENCE_END_BONUS_S
    return gap


def _snap_boundaries(words, labels):
    """Nudge each speaker change to the best nearby pause or sentence end."""
    bounds = [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]
    if not bounds:
        return labels

    speakers = [labels[0]] + [labels[i] for i in bounds]
    edges = [0] + bounds + [len(labels)]

    for t in range(1, len(edges) - 1):
        # Stay strictly inside the neighbouring boundaries so runs keep their order.
        lo = max(edges[t - 1] + 1, edges[t] - BOUNDARY_MAX_SHIFT_WORDS)
        hi = min(edges[t + 1] - 1, edges[t] + BOUNDARY_MAX_SHIFT_WORDS)
        if lo <= hi:
            # Ties are common: Parakeet quantises timings, so most adjacent words
            # report a gap of exactly 0. Break them towards the diarizer's own
            # boundary, otherwise every tie drags the turn to the left clamp.
            here = edges[t]
            best = max(
                range(lo, hi + 1),
                key=lambda i: (_split_score(words, i), -abs(i - here)),
            )
            # Keep the diarizer's boundary unless the alternative is clearly better.
            if _split_score(words, best) >= _split_score(words, here) + MIN_SNAP_IMPROVEMENT_S:
                edges[t] = best

    snapped = []
    for t, speaker in enumerate(speakers):
        snapped += [speaker] * (edges[t + 1] - edges[t])
    return snapped


def _speaker_label(n):
    """Spreadsheet-style label: A..Z, then AA, AB, ... so 27+ speakers stay valid."""
    label = ""
    while True:
        label = chr(ord("A") + n % 26) + label
        n = n // 26 - 1
        if n < 0:
            return label


def build_turns(asr, dia):
    """Merge word timings and speaker spans into timestamped speaker turns."""
    words = asr.get("wordTimings") or []
    if not words:
        raise RuntimeError(
            "ASR output has no wordTimings; cannot attach speakers "
            "(was --word-timestamps passed?)"
        )
    segments = dia.get("segments") or []
    if not segments:
        raise RuntimeError("diarization output has no segments; cannot attach speakers")

    labels = _snap_boundaries(words, _assign_speakers(words, segments))

    turns = []
    for word, speaker in zip(words, labels):
        if turns and turns[-1]["speaker"] == speaker:
            turns[-1]["words"].append(word["word"].strip())
            turns[-1]["end"] = word["endTime"]
        else:
            turns.append({
                "speaker": speaker,
                "start": word["startTime"],
                "end": word["endTime"],
                "words": [word["word"].strip()],
            })

    # Relabel to the [A]/[B]/[C] convention the OpenAI transcripts used, so the
    # downstream prompts see the same shape. Order is first appearance.
    order = {}
    for turn in turns:
        if turn["speaker"] not in order:
            order[turn["speaker"]] = _speaker_label(len(order))

    return [
        {
            "speaker": order[t["speaker"]],
            "start": round(t["start"], 3),
            "end": round(t["end"], 3),
            "text": " ".join(t["words"]),
        }
        for t in turns
    ]


def format_turns(turns):
    """Render turns as the ``[A]: text`` transcript the pipeline consumes."""
    return "\n".join(f"[{t['speaker']}]: {t['text']}" for t in turns)


def transcribe_local(audio_path, out_base, num_speakers=None, verbose=False):
    """Transcribe and diarize locally. Returns the ``[A]: ...`` transcript text."""
    cli = resolve_cli()
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found; required to convert audio to 16 kHz mono WAV")

    asr_json = f"{out_base}-asr.json"
    dia_json = f"{out_base}-diarization.json"
    turns_json = f"{out_base}-turns.json"

    wav_path = to_wav(audio_path, verbose=verbose)
    try:
        asr = run_asr(cli, wav_path, asr_json, verbose=verbose)
        dia = run_diarization(cli, wav_path, dia_json, num_speakers=num_speakers, verbose=verbose)
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)

    turns = build_turns(asr, dia)

    # Timestamps are kept alongside the text so highlight generation can cite
    # them later without re-running either model.
    with open(turns_json, "w", encoding="utf-8") as f:
        json.dump(turns, f, indent=2)

    transcript = format_turns(turns)
    speakers = sorted({t["speaker"] for t in turns})
    print(
        f"✓ Local transcript: {len(turns)} turns, {len(speakers)} speakers "
        f"({', '.join(speakers)}), {len(transcript)} chars"
    )
    return transcript
