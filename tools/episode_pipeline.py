"""
Codex transcript correction, the title and teaser picks, and the Claude Code +
Codex adversarial review loop for episode articles.
Checkpoints use the ``out_base`` passed by callers (e.g. ``podbean.py`` → ``out/episodeNNN``).
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
EPISODES_DIR = os.path.join(TOOLS_DIR, "..", "content", "episodes")
REPO_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
PROMPTS_DIR = os.path.join(TOOLS_DIR, "prompts")
CONTEXT_FILE = os.path.join(TOOLS_DIR, "podcast-context.md")
STYLE_FILE = os.path.join(TOOLS_DIR, "writing-style.md")
TONE_FILE = os.path.join(TOOLS_DIR, "blog-tone-of-voice.md")

MAX_REVIEW_ITERATIONS = 10
CODEX_MODEL = os.environ.get("CODEX_MODEL", "gpt-6-astra")
CODEX_TIMEOUT_S = int(os.environ.get("CODEX_TIMEOUT_S", "900"))
# Drafting a long episode with web research ran past 15 minutes.
CLAUDE_TIMEOUT_S = int(os.environ.get("CLAUDE_TIMEOUT_S", "2400"))

with open(CONTEXT_FILE, "r", encoding="utf-8") as _f:
    _CONTENT_CONTEXT = _f.read()

with open(STYLE_FILE, "r", encoding="utf-8") as _f:
    _WRITING_STYLE = _f.read()

with open(TONE_FILE, "r", encoding="utf-8") as _f:
    _TONE_OF_VOICE = _f.read()


def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ and inject context, writing style and tone."""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    return (
        template.replace("{{CONTEXT}}", _CONTENT_CONTEXT)
        .replace("{{STYLE}}", _WRITING_STYLE)
        .replace("{{TONE}}", _TONE_OF_VOICE)
    )


DRAFT_PROMPT = load_prompt("draft")
REVISE_PROMPT = load_prompt("revise")
REVIEW_PROMPT = load_prompt("review")
TITLES_PROMPT = load_prompt("titles")
DESCRIPTIONS_PROMPT = load_prompt("descriptions")
GUESTS_PROMPT = load_prompt("guests")


class PipelineStop(Exception):
    """A step cannot finish; the run stops here. ``checkpoint`` names the file to fix or delete."""

    def __init__(self, message: str, checkpoint: str = ""):
        super().__init__(message)
        self.checkpoint = checkpoint


def _review_ends_good_to_go(review_text: str) -> bool:
    """True when Codex ended the review with exactly GOOD_TO_GO on the last line."""
    return review_text.strip().splitlines()[-1].strip() == "GOOD_TO_GO"


def run_claude(prompt: str, verbose=False, allow_web=False, fatal: bool = True) -> str:
    """Run Claude Code CLI with the given prompt on stdin. Returns output text."""
    if not shutil.which("claude"):
        message = "Error: 'claude' CLI not found. Install Claude Code."
        if fatal:
            print(message)
            sys.exit(1)
        raise RuntimeError(message)

    cmd = [
        "claude",
        "--print",
        "--model", "claude-opus-5",
        "--add-dir", EPISODES_DIR,
        "--add-dir", REPO_ROOT,
    ]
    if allow_web:
        cmd += ["--allowedTools", "WebSearch", "WebFetch"]
    cmd += ["-p", "Process the input provided on stdin."]

    if verbose:
        print(f"Running claude CLI ({len(prompt)} chars)...")

    result = subprocess.run(
        cmd,
        input=prompt,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        timeout=CLAUDE_TIMEOUT_S,
    )

    if result.returncode != 0:
        message = f"Claude failed (exit {result.returncode})"
        if fatal:
            print(message)
            print(f"stdout: {result.stdout[:2000]}")
            sys.exit(1)
        raise RuntimeError(f"{message}: {result.stdout[:2000]}")

    output = result.stdout.strip()
    if not output:
        message = "Claude returned empty response"
        if fatal:
            print(message)
            sys.exit(1)
        raise RuntimeError(message)

    return output


def codex_base_cmd(output_file: str, output_schema: str | None = None) -> list[str]:
    """``codex exec`` in a read-only sandbox, writing its last message to ``output_file``."""
    cmd = ["codex", "exec", "--sandbox", "read-only", "-C", REPO_ROOT, "--model", CODEX_MODEL, "-o", output_file]
    if output_schema:
        cmd += ["--output-schema", output_schema]
    return cmd


def run_codex(prompt: str, stdin_text: str = "", verbose=False, output_schema: str | None = None) -> str:
    """Run OpenAI Codex CLI in non-interactive mode. Returns output text.

    ``output_schema`` is a JSON Schema file; Codex then answers with one JSON object.
    """
    if not shutil.which("codex"):
        print("Error: 'codex' CLI not found. Install with: npm install -g @openai/codex")
        sys.exit(1)

    if verbose:
        print(f"Running codex exec (prompt: {len(prompt)} chars, stdin: {len(stdin_text)} chars)...")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        cmd = codex_base_cmd(tmp_path, output_schema)
        if stdin_text:
            cmd.append(prompt)
            input_data = stdin_text
        else:
            cmd.append("-")
            input_data = prompt

        result = subprocess.run(
            cmd,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if not verbose else None,
            text=True,
            timeout=CODEX_TIMEOUT_S,
        )

        if result.returncode != 0:
            print(f"Codex failed (exit {result.returncode})")
            if result.stderr:
                print(result.stderr[:3000])
            sys.exit(1)

        with open(tmp_path, "r", encoding="utf-8") as f:
            output = f.read().strip()

        if not output:
            print("Codex returned empty response")
            sys.exit(1)

        return output
    except subprocess.TimeoutExpired:
        # TimeoutExpired includes the full argv (and prompt) when printed.
        print(
            f"Error: Codex timed out after {CODEX_TIMEOUT_S}s. "
            "Re-run to resume from checkpoints; increase CODEX_TIMEOUT_S if needed.",
            file=sys.stderr,
        )
        sys.exit(1)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def load_raw_companion_markdown(audio_path: str) -> tuple[str, list[str]]:
    """Load ``{stem}*.md`` show notes next to the audio file in raw/."""
    from pathlib import Path

    p = Path(audio_path).resolve()
    stem = p.stem
    parent = p.parent
    paths = sorted(parent.glob(f"{stem}*.md"))
    if not paths:
        return "", []

    chunks: list[str] = []
    names: list[str] = []
    for md_path in paths:
        try:
            text = md_path.read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"⚠ Could not read {md_path}: {e}")
            continue
        if not text:
            continue
        chunks.append(f"### {md_path.name}\n\n{text}")
        names.append(md_path.name)

    if not chunks:
        return "", []
    return "\n\n".join(chunks), names


def extract_article(text: str) -> str:
    """Drop any preamble before the article's first ``##`` heading."""
    match = re.search(r"^## ", text, flags=re.MULTILINE)
    if match:
        article = text[match.start():].strip() + "\n"
    else:
        print("⚠ Output has no '## ' heading — using as-is")
        article = text

    if len(article) < 500:
        print(f"⚠ Article very short ({len(article)} chars)")

    return article


def _extract_json_object(text: str) -> dict:
    """Parse a JSON object from model output, tolerating fenced JSON."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group(0))

    if not isinstance(data, dict):
        raise ValueError("guest lookup output must be a JSON object")
    return data


SHOW_HOSTS = ("Andrey Devyatkin", "Paulina Dubas", "Mattias Hemmingsson")
AUTHOR_HOST = "Andrey Devyatkin"


def normalize_guest_context(data: dict) -> dict:
    """Normalize guest lookup data to the stable checkpoint schema."""
    status = str(data.get("status") or "").strip().lower()
    if status not in ("no_guests", "verified", "needs_operator"):
        status = "verified" if data.get("guests") else "no_guests"

    guests: list[dict] = []
    for raw_guest in data.get("guests") or []:
        if not isinstance(raw_guest, dict):
            continue
        full_name = str(raw_guest.get("full_name") or "").strip()
        if not full_name:
            continue
        participant_name = str(raw_guest.get("participant_name") or full_name).strip()
        links = raw_guest.get("links") or []
        clean_links: list[dict] = []
        for raw_link in links:
            if not isinstance(raw_link, dict):
                continue
            url = str(raw_link.get("url") or "").strip()
            if not url:
                continue
            clean_links.append(
                {
                    "label": str(raw_link.get("label") or url).strip(),
                    "url": url,
                    "type": str(raw_link.get("type") or "").strip(),
                }
            )
        guests.append(
            {
                "full_name": full_name,
                "participant_name": participant_name or full_name,
                "role": str(raw_guest.get("role") or "").strip(),
                "company": str(raw_guest.get("company") or "").strip(),
                "professional_summary": str(raw_guest.get("professional_summary") or "").strip(),
                "links": clean_links,
                "confidence": str(raw_guest.get("confidence") or "").strip(),
                "needs_operator": bool(raw_guest.get("needs_operator")),
                "question": str(raw_guest.get("question") or "").strip(),
                # Announcement tags; linkedin_name is what follows the "@". Empty
                # means the profile was not confirmed, so the guest is credited untagged.
                "linkedin_url": str(raw_guest.get("linkedin_url") or "").strip(),
                "linkedin_name": str(raw_guest.get("linkedin_name") or "").strip(),
                "x_handle": str(raw_guest.get("x_handle") or "").strip().lstrip("@"),
                "threads_handle": str(raw_guest.get("threads_handle") or "").strip().lstrip("@"),
            }
        )

    if not guests and status != "needs_operator":
        status = "no_guests"
    elif status == "no_guests":
        status = "verified"

    hosts_present = _normalize_hosts_present(data.get("hosts_present"))
    return {
        "status": status,
        "guests": guests,
        "hosts_present": hosts_present,
        "andrey_present": AUTHOR_HOST in hosts_present,
        "notes": str(data.get("notes") or "").strip(),
    }


def guest_full_names(guest_context: dict | None) -> list[str]:
    """Guests' full names in checkpoint order, skipping entries without one."""
    return [
        str(g.get("full_name") or "").strip()
        for g in (guest_context or {}).get("guests") or []
        if isinstance(g, dict) and str(g.get("full_name") or "").strip()
    ]


def _normalize_hosts_present(raw) -> list[str]:
    """Current hosts by full name, in SHOW_HOSTS order; unknown names are dropped, not tagged."""
    wanted = set()
    for name in raw if isinstance(raw, list) else []:
        key = str(name).strip().casefold()
        for host in SHOW_HOSTS:
            if key in (host.casefold(), host.split()[0].casefold()):
                wanted.add(host)
    return [host for host in SHOW_HOSTS if host in wanted]


def load_guest_context(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return normalize_guest_context(json.load(f))


def save_guest_context(path: str, guest_context: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(normalize_guest_context(guest_context), f, indent=2, ensure_ascii=False)
        f.write("\n")


def guest_context_to_prompt_text(guest_context: dict) -> str:
    """Format verified guest context for article/title/description prompts."""
    guest_context = normalize_guest_context(guest_context)
    guests = guest_context.get("guests", [])
    if not guests:
        return ""

    names = ", ".join(g["full_name"] for g in guests)
    lines = [
        "## Guest Context",
        "",
        f"Detected guest(s): {names}.",
        (
            "These are guests because they are speakers other than Andrey, Mattias, "
            "or Paulina. Repeat guests are still guests."
        ),
        "Use the verified professional details below for factual context only.",
        "Introduce each guest once, by full name and credentials, in the article's problem section.",
        "When generating titles, every title option must include all guest full names.",
        "When generating podcast descriptions, mention the guest full names.",
        "Include relevant guest links, companies, projects, or profiles in Resources.",
        "",
    ]
    for guest in guests:
        role = guest.get("role", "")
        company = guest.get("company", "")
        summary = guest.get("professional_summary", "")
        heading_bits = [guest["full_name"]]
        detail = ", ".join(x for x in (role, company) if x)
        if detail:
            heading_bits.append(f"({detail})")
        lines.append(f"- {' '.join(heading_bits)}")
        if summary:
            lines.append(f"  Professional context: {summary}")
        for link in guest.get("links", []):
            label = link.get("label") or link.get("url")
            url = link.get("url")
            link_type = link.get("type", "")
            suffix = f" [{link_type}]" if link_type else ""
            lines.append(f"  Link: {label}{suffix} — {url}")
    return "\n".join(lines)


def normalize_operator_guest_notes(
    operator_notes: str,
    previous_guest_context: dict | None = None,
    verbose: bool = False,
) -> dict:
    """Normalize free-form operator guest notes into the guest checkpoint schema."""
    print("Normalizing operator guest context with Claude Code...")
    previous_json = json.dumps(
        normalize_guest_context(previous_guest_context or {}),
        ensure_ascii=False,
        indent=2,
    )
    prompt = f"""Normalize operator-provided guest clarification for the DevSecOps Talks publishing pipeline.

The operator text is authoritative for the intended guest names. Extract clean full names only into
`full_name` and `participant_name`; do not include roles, companies, titles, or links in those fields.
Put roles/titles into `role`, organizations/projects into `company`, and URLs into `links`.

Use web search for every operator-provided guest to find and verify relevant public professional
sources. Prefer official personal sites, company profile/team pages, LinkedIn profiles, GitHub
profiles, conference speaker bios, project documentation, and other authoritative professional
pages. Include the best relevant sources in `links`, especially LinkedIn when you can confidently
identify the right profile. Do not invent URLs or include uncertain profile matches.

If verification is not possible, still return the operator-provided names with `confidence` set to
"medium" or "low".
Do not ask follow-up questions unless the operator text is genuinely impossible to split into guests.

Return exactly one JSON object and nothing else. Do not wrap it in markdown.

Schema:

{{
  "status": "no_guests|verified|needs_operator",
  "guests": [
    {{
      "full_name": "Full Name",
      "participant_name": "Full Name",
      "role": "Professional role or title",
      "company": "Company or project, if known",
      "professional_summary": "One or two factual professional sentences.",
      "links": [
        {{
          "label": "Source label",
          "url": "https://example.com/",
          "type": "official|company|linkedin|github|conference|project|operator"
        }}
      ],
      "confidence": "high|medium|low|operator",
      "needs_operator": false,
      "question": ""
    }}
  ],
  "notes": "Short note about uncertainty, or empty string."
}}

Previous ambiguous guest context:
{previous_json}

Operator-provided guest notes:
{operator_notes}
"""
    output = run_claude(prompt, verbose=verbose, allow_web=True, fatal=False)
    guest_context = normalize_guest_context(_extract_json_object(output))
    guests = guest_context.get("guests", [])
    if guests:
        print("✓ Normalized guests: " + ", ".join(g["full_name"] for g in guests))
    return guest_context


def detect_guests(
    transcript: str,
    editorial_guidance: str = "",
    raw_notes: str = "",
    verbose: bool = False,
) -> dict:
    """Identify and research episode guests using Claude Code with web search."""
    print("Detecting and researching episode guests with Claude Code...")

    parts: list[str] = [GUESTS_PROMPT]
    if editorial_guidance:
        parts.append(f"\n\n## Editorial Guidance\n{editorial_guidance}")
    if raw_notes:
        parts.append(
            "\n\n--- SHOW NOTES (companion .md files from raw/, same filename prefix as the audio) ---\n"
            f"{raw_notes}"
        )
    parts.append(f"\n\n--- TRANSCRIPT ---\n{transcript}\n")

    output = run_claude("".join(parts), verbose=verbose, allow_web=True)
    guest_context = normalize_guest_context(_extract_json_object(output))
    guests = guest_context.get("guests", [])
    if guests:
        print("✓ Guests: " + ", ".join(g["full_name"] for g in guests))
    else:
        print("✓ No guests detected")
    return guest_context


TRANSCRIPT_CORRECT_PROMPT = load_prompt("transcript-correct")
TRANSCRIPT_REVIEW_PROMPT = load_prompt("transcript-review")
TRANSCRIPT_CORRECT_SCHEMA = os.path.join(PROMPTS_DIR, "transcript-correct-schema.json")
TRANSCRIPT_REVIEW_SCHEMA = os.path.join(PROMPTS_DIR, "transcript-review-schema.json")
TRANSCRIPT_REVIEW_ROUNDS = 5
TRANSCRIPT_EXTENSION_ROUNDS = 5
CORRECTED_TURNS_SUFFIX = "-turns-corrected.json"


def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def transcript_units(turns: list[dict]) -> list[dict]:
    """The machine turns as numbered units: index, diarization label, start, end, text."""
    return [
        {
            "index": i,
            "label": str(turn.get("speaker") or ""),
            "start": float(turn.get("start") or 0),
            "end": float(turn.get("end") or 0),
            "text": " ".join(str(turn.get("text") or "").split()),
        }
        for i, turn in enumerate(turns or [], 1)
    ]


def numbered_turn_line(index: int, speaker: str, text: str, start: float | None = None) -> str:
    """``[17] [11:45] [B]: text``; the time is left out when there is none."""
    stamp = f" [{format_timestamp(start)}]" if start is not None else ""
    return f"[{index}]{stamp} [{speaker or '?'}]: {text}"


def numbered_turns_text(units: list[dict], current: dict[int, dict] | None = None) -> str:
    """The units as numbered lines, with the rewritten speaker and text when given."""
    lines = []
    for unit in units:
        turn = current[unit["index"]] if current else unit
        speaker = turn.get("speaker") or unit["label"]
        lines.append(numbered_turn_line(unit["index"], speaker, turn["text"], unit.get("start")))
    return "\n".join(lines)


def transcript_correction_context(
    guest_context: dict, reference_text: str = "", speaker_names: dict | None = None
) -> str:
    """Guest research, speakers named by voice and the spelling reference, shared by both sessions."""
    guest_context = normalize_guest_context(guest_context)
    guest_text = guest_context_to_prompt_text(guest_context) or "No guests on this episode."
    parts = [f"--- GUEST RESEARCH ---\n{guest_text}"]
    if guest_context.get("notes"):
        parts.append(f"Research notes: {guest_context['notes']}")
    if guest_context.get("hosts_present"):
        parts.append("Hosts on this episode: " + ", ".join(guest_context["hosts_present"]))
    if speaker_names:
        known = "\n".join(f"{label} = {name}" for label, name in sorted(speaker_names.items()))
        parts.append(f"--- KNOWN SPEAKERS (named by voice; keep these) ---\n{known}")
    else:
        parts.append("--- KNOWN SPEAKERS ---\nNone: name every label.")
    if reference_text:
        parts.append(
            "--- PROVIDED TRANSCRIPT (spelling reference only; never copy its wording) ---\n"
            f"{reference_text}"
        )
    return "\n\n".join(parts)


def run_codex_json(prompt: str, stdin_text: str, schema_file: str, checkpoint: str = "", verbose=False) -> dict:
    """One schema-enforced Codex answer as a dict; any failure raises PipelineStop."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            codex_base_cmd(tmp_path, schema_file) + [prompt],
            input=stdin_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if not verbose else None,
            text=True,
            timeout=CODEX_TIMEOUT_S,
        )
        if result.returncode != 0:
            raise PipelineStop(
                f"Codex failed (exit {result.returncode}): {(result.stderr or '')[:2000]}",
                checkpoint=checkpoint,
            )
        with open(tmp_path, "r", encoding="utf-8") as f:
            return _extract_json_object(f.read())
    except subprocess.TimeoutExpired:
        raise PipelineStop(
            f"Codex timed out after {CODEX_TIMEOUT_S}s (raise CODEX_TIMEOUT_S to allow longer)",
            checkpoint=checkpoint,
        ) from None
    except ValueError as e:
        raise PipelineStop(f"Codex returned no JSON object: {e}", checkpoint=checkpoint) from e
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def parse_rewritten_turns(answer: dict, expected: list[int]) -> dict[int, dict]:
    """The rewriter's turns by index; ValueError unless exactly ``expected`` came back."""
    turns = answer.get("turns") if isinstance(answer, dict) else None
    if not isinstance(turns, list):
        raise ValueError("the answer has no turns list")
    if len(turns) != len(expected):
        raise ValueError(f"{len(turns)} turns returned, {len(expected)} expected")
    parsed: dict[int, dict] = {}
    for turn in turns:
        if not isinstance(turn, dict) or not isinstance(turn.get("index"), int):
            raise ValueError(f"turn without an integer index: {str(turn)[:120]}")
        if not isinstance(turn.get("text"), str) or not str(turn.get("speaker") or "").strip():
            raise ValueError(f"turn {turn['index']} lacks a speaker or text")
        if turn["index"] in parsed:
            raise ValueError(f"turn {turn['index']} returned twice")
        parsed[turn["index"]] = {"speaker": turn["speaker"].strip(), "text": " ".join(turn["text"].split())}
    if sorted(parsed) != sorted(expected):
        missing = sorted(set(expected) - set(parsed))
        extra = sorted(set(parsed) - set(expected))
        raise ValueError(f"indexes differ (missing {missing[:10]}, unexpected {extra[:10]})")
    return parsed


def parse_transcript_review(answer: dict, scope: list[int]) -> dict[int, str]:
    """Flagged turns as {index: problem}; ValueError on a malformed or out-of-scope answer."""
    if not isinstance(answer, dict) or answer.get("status") not in ("good", "issues"):
        raise ValueError("status must be 'good' or 'issues'")
    turns = answer.get("turns")
    if not isinstance(turns, list):
        raise ValueError("the answer has no turns list")
    flagged: dict[int, str] = {}
    for turn in turns:
        if not isinstance(turn, dict) or turn.get("index") not in scope:
            raise ValueError(f"flagged turn is not one under review: {str(turn)[:120]}")
        flagged[turn["index"]] = str(turn.get("problem") or "").strip() or "(no reason given)"
    if (answer["status"] == "good") != (not flagged):
        raise ValueError(f"status {answer['status']!r} with {len(flagged)} flagged turn(s)")
    return flagged


def _checked_codex_json(prompt, stdin_text, schema_file, parse, label, checkpoint, verbose=False):
    """Ask once more, with the reason, when an answer fails ``parse``; stop on a second failure."""
    answer = run_codex_json(prompt, stdin_text, schema_file, checkpoint, verbose=verbose)
    try:
        return parse(answer)
    except ValueError as e:
        print(f"⚠ {label} answer rejected ({e}); asking again")
        retry = f"{prompt}\n\nYour previous answer was rejected: {e}. Answer again, following the rules."
        answer = run_codex_json(retry, stdin_text, schema_file, checkpoint, verbose=verbose)
        try:
            return parse(answer)
        except ValueError as e2:
            raise PipelineStop(f"{label} answer rejected twice: {e2}", checkpoint=checkpoint) from e2


def _apply_speaker_names(units, turns: dict[int, dict], speaker_names: dict | None) -> dict[int, dict]:
    """Labels named by voice keep that name, whatever the rewriter returned."""
    for unit in units:
        name = (speaker_names or {}).get(unit["label"])
        if name and unit["index"] in turns:
            turns[unit["index"]]["speaker"] = name
    return turns


def rewrite_transcript(units, context, speaker_names=None, checkpoint="", verbose=False) -> dict[int, dict]:
    """The first rewrite of every turn."""
    print(f"Correcting {len(units)} transcript turns with Codex...")
    stdin_text = f"{context}\n\n--- TURNS ---\n{numbered_turns_text(units)}\n"
    turns = _checked_codex_json(
        TRANSCRIPT_CORRECT_PROMPT, stdin_text, TRANSCRIPT_CORRECT_SCHEMA,
        lambda a: parse_rewritten_turns(a, [u["index"] for u in units]),
        "transcript rewrite", checkpoint, verbose=verbose,
    )
    return _apply_speaker_names(units, turns, speaker_names)


def revise_transcript_turns(
    units, current, flagged, context, speaker_names=None, checkpoint="", verbose=False
) -> dict[int, dict]:
    """``current`` with only the flagged turns rewritten again from the original."""
    print(f"Revising {len(flagged)} flagged transcript turn(s) with Codex...")
    by_index = {u["index"]: u for u in units}
    blocks = []
    for index in sorted(flagged):
        unit = by_index[index]
        blocks.append(
            f"Original: {numbered_turn_line(index, unit['label'], unit['text'], unit.get('start'))}\n"
            f"Current: {numbered_turn_line(index, current[index]['speaker'], current[index]['text'])}\n"
            f"Reviewer: {flagged[index]}"
        )
    stdin_text = f"{context}\n\n--- REVISE ONLY THESE TURNS ---\n" + "\n\n".join(blocks) + "\n"
    prompt = (
        TRANSCRIPT_CORRECT_PROMPT
        + "\n\nThis is a revision. Return only the turns under REVISE ONLY THESE TURNS, "
        "redone from the original text so the reviewer's problem is fixed."
    )
    revised = _checked_codex_json(
        prompt, stdin_text, TRANSCRIPT_CORRECT_SCHEMA,
        lambda a: parse_rewritten_turns(a, sorted(flagged)),
        "transcript revision", checkpoint, verbose=verbose,
    )
    return {**current, **_apply_speaker_names(units, revised, speaker_names)}


def review_transcript(units, current, context, scope, checkpoint="", verbose=False) -> tuple[dict, dict[int, str]]:
    """A second Codex session's verdict on the turns in ``scope``: (answer, flagged)."""
    print(f"Reviewing {len(scope)} corrected transcript turn(s) with Codex...")
    scope_text = "all" if len(scope) == len(units) else ", ".join(str(i) for i in scope)
    stdin_text = (
        f"{context}\n\n--- TURNS TO REVIEW ---\n{scope_text}\n\n"
        f"--- ORIGINAL TURNS ---\n{numbered_turns_text(units)}\n\n"
        f"--- CORRECTED TURNS ---\n{numbered_turns_text(units, current)}\n"
    )
    kept = {}

    def parse(answer):
        flagged = parse_transcript_review(answer, scope)
        kept["answer"] = answer
        return flagged

    flagged = _checked_codex_json(
        TRANSCRIPT_REVIEW_PROMPT, stdin_text, TRANSCRIPT_REVIEW_SCHEMA, parse,
        "transcript review", checkpoint, verbose=verbose,
    )
    return kept["answer"], flagged


def _write_rewrite(path, current: dict[int, dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"index": i, **current[i]} for i in sorted(current)], f, indent=2, ensure_ascii=False)
        f.write("\n")


def _load_rewrite(path, units) -> dict[int, dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_rewritten_turns({"turns": json.load(f)}, [u["index"] for u in units])
    except (OSError, ValueError) as e:
        raise PipelineStop(f"saved transcript rewrite is unusable ({e}); delete it", checkpoint=path) from e


def _write_review(path, round_no, answer, flagged, current) -> None:
    lines = [f"# Transcript review {round_no}", "", f"{len(flagged)} turn(s) flagged.", ""]
    for index in sorted(flagged):
        lines.append(f"- [{index}] {current[index]['speaker']}: {flagged[index]}")
    lines += ["", "```json", json.dumps(answer, indent=2, ensure_ascii=False), "```", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _load_review(path, scope) -> dict[int, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            blocks = re.findall(r"```json\n(.*?)\n```", f.read(), flags=re.S)
        if not blocks:
            raise ValueError("no JSON block")
        return parse_transcript_review(json.loads(blocks[-1]), scope)
    except (OSError, ValueError) as e:
        raise PipelineStop(f"saved transcript review is unusable ({e}); delete it", checkpoint=path) from e


def _load_round_limit(limit_file: str) -> int:
    """The extended round cap the operator chose, or the default."""
    try:
        with open(limit_file, "r", encoding="utf-8") as f:
            saved = f.read().strip()
    except OSError:
        return TRANSCRIPT_REVIEW_ROUNDS
    if not saved.isdigit():
        raise PipelineStop(f"{limit_file} holds {saved!r}, not a round count; fix or delete it", checkpoint=limit_file)
    return max(int(saved), TRANSCRIPT_REVIEW_ROUNDS)


def prompt_transcript_review_cap(rounds, flagged, current, limit_file, input_func=input) -> bool:
    """Ask at the cap: True runs more rounds, False keeps the reviewed version as is.

    No input stops the run, so no flagged turn becomes quotable unattended.
    """
    print(f"\n⚠ {rounds} transcript review rounds; {len(flagged)} turn(s) still flagged:")
    for index in sorted(flagged):
        print(f"  [{index}] {current[index]['speaker']}: {current[index]['text'][:160]}")
        print(f"       → {flagged[index]}")
    while True:
        print(
            f"'e' to run {TRANSCRIPT_EXTENSION_ROUNDS} more rounds, or 's' to keep this version "
            "(flagged turns stay but cannot be quoted): ",
            end="",
            flush=True,
        )
        try:
            choice = input_func().strip().lower()
        except EOFError:
            raise PipelineStop(
                f"transcript review hit {rounds} rounds with turns still flagged and no answer "
                "was given; re-run in a terminal to extend or keep",
                checkpoint=limit_file,
            ) from None
        if choice in ("e", "s"):
            return choice == "e"
        print("Invalid choice, try again.")


def render_corrected_transcript(turns: list[dict]) -> str:
    """``Name: text`` per turn: the transcript every later step reads."""
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in turns if t.get("text"))


def load_corrected_turns(out_base: str) -> list[dict] | None:
    """The accepted corrected turns, or None before the correction step finished."""
    try:
        with open(f"{out_base}{CORRECTED_TURNS_SUFFIX}", "r", encoding="utf-8") as f:
            turns = json.load(f)
    except (OSError, ValueError):
        return None
    return turns if isinstance(turns, list) and turns else None


def correction_checkpoints(out_base: str) -> list[str]:
    """Every file the correction step writes, for a caller that discards the step."""
    patterns = (
        CORRECTED_TURNS_SUFFIX,
        "-transcript-rewrite-*.json",
        "-transcript-review-*.md",
        "-transcript-review-limit.txt",
    )
    base = glob.escape(out_base)
    return sorted({p for pattern in patterns for p in glob.glob(f"{base}{pattern}")})


def correct_transcript(
    out_base: str,
    turns: list[dict],
    guest_context: dict,
    reference_text: str = "",
    speaker_names: dict | None = None,
    verbose: bool = False,
    input_func=input,
) -> list[dict]:
    """Rewrite, review and revise the transcript until the reviewer passes it or the operator keeps it.

    ``turns`` are the machine turns (``speaker`` is the diarization label) and
    ``speaker_names`` maps labels to names known by voice. Writes
    ``-turns-corrected.json`` and ``{out_base}.txt`` as ``Name: text`` lines.
    """
    final_file = f"{out_base}{CORRECTED_TURNS_SUFFIX}"
    corrected = load_corrected_turns(out_base)
    if corrected:
        print(f"✓ Loaded corrected transcript from {final_file}")
    else:
        corrected = _run_transcript_correction(
            out_base, transcript_units(turns), guest_context, reference_text, speaker_names, verbose, input_func
        )
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(corrected, f, indent=2, ensure_ascii=False)
            f.write("\n")
        flagged = sum(1 for t in corrected if t.get("flagged"))
        suffix = f" ({flagged} flagged turn(s) cannot be quoted)" if flagged else ""
        print(f"✓ Corrected transcript saved to {final_file}{suffix}")
    with open(f"{out_base}.txt", "w", encoding="utf-8") as f:
        f.write(render_corrected_transcript(corrected) + "\n")
    return corrected


def _run_transcript_correction(
    out_base, units, guest_context, reference_text, speaker_names, verbose, input_func
) -> list[dict]:
    if not units:
        raise PipelineStop(
            "the machine transcript has no turns; nothing to correct",
            checkpoint=f"{out_base}-turns.json",
        )
    limit_file = f"{out_base}-transcript-review-limit.txt"
    context = transcript_correction_context(guest_context, reference_text, speaker_names)
    limit = _load_round_limit(limit_file)

    rewrite_file = f"{out_base}-transcript-rewrite-1.json"
    if os.path.exists(rewrite_file):
        current = _load_rewrite(rewrite_file, units)
    else:
        current = rewrite_transcript(units, context, speaker_names, rewrite_file, verbose=verbose)
        _write_rewrite(rewrite_file, current)

    # Round one reviews every turn; later rounds only the turns just revised,
    # so a turn the reviewer passed stays passed.
    scope = [u["index"] for u in units]
    round_no = 1
    while True:
        review_file = f"{out_base}-transcript-review-{round_no}.md"
        if os.path.exists(review_file):
            flagged = _load_review(review_file, scope)
        else:
            answer, flagged = review_transcript(units, current, context, scope, review_file, verbose=verbose)
            _write_review(review_file, round_no, answer, flagged, current)
        print(f"Transcript review {round_no}: {len(flagged)} turn(s) flagged")
        if not flagged:
            break
        if round_no >= limit:
            if not prompt_transcript_review_cap(round_no, flagged, current, limit_file, input_func):
                print(f"✓ Keeping the reviewed transcript with {len(flagged)} flagged turn(s)")
                break
            limit = round_no + TRANSCRIPT_EXTENSION_ROUNDS
            with open(limit_file, "w", encoding="utf-8") as f:
                f.write(f"{limit}\n")

        rewrite_file = f"{out_base}-transcript-rewrite-{round_no + 1}.json"
        if os.path.exists(rewrite_file):
            current = _load_rewrite(rewrite_file, units)
        else:
            current = revise_transcript_turns(
                units, current, flagged, context, speaker_names, rewrite_file, verbose=verbose
            )
            _write_rewrite(rewrite_file, current)
        scope = sorted(flagged)
        round_no += 1

    corrected = []
    for unit in units:
        index = unit["index"]
        turn = {
            "index": index,
            "label": unit["label"],
            "speaker": current[index]["speaker"],
            "start": unit["start"],
            "end": unit["end"],
            "text": current[index]["text"],
            "flagged": index in flagged,
        }
        if turn["flagged"]:
            turn["problem"] = flagged[index]
        corrected.append(turn)
    return corrected


def episode_frame_text(title: str = "", teaser: str = "", chapters: str = "") -> str:
    """The picked title and teaser and the approved chapters as a prompt section, or ""."""
    parts = []
    if title:
        parts.append(f"\n\n--- EPISODE TITLE ---\n{title}\n")
    if teaser:
        parts.append(f"\n\n--- TEASER ---\n{teaser}\n")
    if chapters:
        parts.append(f"\n\n--- CHAPTERS ---\n{chapters}\n")
    return "".join(parts)


def generate_draft(
    transcript: str,
    editorial_guidance: str = "",
    raw_notes: str = "",
    verbose: bool = False,
    title: str = "",
    teaser: str = "",
    chapters: str = "",
) -> str:
    """Generate article draft using Claude Code with web search."""
    print("Generating article draft with Claude Code...")

    parts: list[str] = [DRAFT_PROMPT]
    if editorial_guidance:
        parts.append(f"\n\n## Editorial Guidance\n{editorial_guidance}")
    if raw_notes:
        parts.append(
            "\n\n--- SHOW NOTES (companion .md files from raw/, same filename prefix as the audio) ---\n"
            f"{raw_notes}"
        )
    parts.append(episode_frame_text(title, teaser, chapters))
    parts.append(f"\n\n--- TRANSCRIPT ---\n{transcript}\n")
    prompt = "".join(parts)

    output = run_claude(prompt, verbose=verbose, allow_web=True)
    article = extract_article(output)
    print(f"✓ Draft generated ({len(article)} chars)")
    return article


def review_with_codex(
    draft: str,
    previous_review_file: str = "",
    verbose: bool = False,
    transcript: str = "",
    editorial_guidance: str = "",
) -> tuple[str, bool]:
    """Review draft using Codex CLI. Returns (review_text, is_good)."""
    print("Reviewing with Codex (grumpy expert mode)...")

    prompt = REVIEW_PROMPT + "\n\nThe article to review is provided on stdin."
    if previous_review_file:
        prompt += (
            f" Also read your previous review from {os.path.abspath(previous_review_file)} — "
            "do not repeat issues that were already fixed."
        )

    # The transcript lets the reviewer tell host experience from outside research.
    stdin_parts = [f"--- ARTICLE ---\n{draft}"]
    if transcript:
        stdin_parts.append(f"--- TRANSCRIPT ---\n{transcript}")
    if editorial_guidance:
        stdin_parts.append(f"--- EDITORIAL GUIDANCE AND GUEST CONTEXT ---\n{editorial_guidance}")
    review = run_codex(prompt, stdin_text="\n\n".join(stdin_parts) + "\n", verbose=verbose)

    is_good = _review_ends_good_to_go(review)
    if verbose:
        print(f"Review length: {len(review)} chars, GOOD_TO_GO: {is_good}")

    return review, is_good


def revise_draft(
    transcript: str,
    draft: str,
    review_comments: str,
    editorial_guidance: str = "",
    raw_notes: str = "",
    verbose: bool = False,
    title: str = "",
    teaser: str = "",
    chapters: str = "",
) -> str:
    """Revise draft using Claude Code based on reviewer feedback."""
    print("Revising draft with Claude Code...")

    parts: list[str] = [REVISE_PROMPT]
    if editorial_guidance:
        parts.append(f"\n\n## Editorial Guidance\n{editorial_guidance}")
    if raw_notes:
        parts.append(
            "\n\n--- SHOW NOTES (companion .md files from raw/) ---\n"
            f"{raw_notes}"
        )
    parts.append(episode_frame_text(title, teaser, chapters))
    parts.append(f"""

--- TRANSCRIPT ---
{transcript}

--- CURRENT DRAFT ---
{draft}

--- REVIEWER COMMENTS ---
{review_comments}
""")

    prompt = "".join(parts)

    output = run_claude(prompt, verbose=verbose, allow_web=True)
    article = extract_article(output)
    print(f"✓ Revision complete ({len(article)} chars)")
    return article


LEGACY_ARTICLE_HEADINGS = re.compile(r"^## (Summary|Key Topics|Highlights)\b", re.MULTILINE)


def is_legacy_article(text: str) -> bool:
    """True for articles in the old Summary / Key Topics / Highlights recap format."""
    return bool(LEGACY_ARTICLE_HEADINGS.search(text))


def set_aside_legacy_article(out_base: str) -> list[str]:
    """Rename old-format article, draft and review checkpoints to ``*.legacy``."""
    moved: list[str] = []
    patterns = ("-article.md", "-draft.md", "-draft-v*.md", "-review-*.md")
    for pattern in patterns:
        for path in sorted(glob.glob(f"{out_base}{pattern}")):
            os.replace(path, path + ".legacy")
            moved.append(os.path.basename(path))
    return moved


def generate_article(
    transcript: str,
    out_base: str,
    editorial_guidance: str = "",
    raw_notes: str = "",
    verbose: bool = False,
    input_func=input,
    title: str = "",
    teaser: str = "",
    chapters: str = "",
) -> str:
    """Run the draft-review loop, written to the picked title, teaser and chapters. Returns the final article."""
    article_file = f"{out_base}-article.md"
    if os.path.exists(article_file):
        with open(article_file, "r", encoding="utf-8") as f:
            saved_article = f.read()
        if not is_legacy_article(saved_article):
            print("Loading existing final article...")
            return saved_article
        # A recap-format article would otherwise be published into the new layout.
        print(
            f"\n{os.path.basename(article_file)} uses the old Summary/Highlights format.\n"
            "Press Enter to set it aside (*.legacy) and write a new article, "
            "or type 'keep' to publish it as is: ",
            end="",
            flush=True,
        )
        try:
            answer = input_func().strip().lower()
        except EOFError:
            answer = ""
        if answer == "keep":
            return saved_article
        moved = set_aside_legacy_article(out_base)
        print(f"✓ Set aside: {', '.join(moved)}")

    draft = None
    start_iteration = 1

    existing_drafts = sorted(glob.glob(f"{out_base}-draft-v*.md"))
    if existing_drafts:
        latest = existing_drafts[-1]
        match = re.search(r"-draft-v(\d+)\.md$", latest)
        if match:
            version = int(match.group(1))
            with open(latest, "r", encoding="utf-8") as f:
                draft = f.read()
            review_file = f"{out_base}-review-{version}.md"
            if os.path.exists(review_file):
                start_iteration = version + 1
            else:
                start_iteration = version
            print(f"✓ Resuming from draft v{version} (iteration {start_iteration})")

    if draft is None:
        draft_file = f"{out_base}-draft.md"
        if os.path.exists(draft_file):
            print("Loading existing initial draft...")
            with open(draft_file, "r", encoding="utf-8") as f:
                draft = f.read()
        else:
            draft = generate_draft(
                transcript,
                editorial_guidance=editorial_guidance,
                raw_notes=raw_notes,
                verbose=verbose,
                title=title,
                teaser=teaser,
                chapters=chapters,
            )
            with open(draft_file, "w", encoding="utf-8") as f:
                f.write(draft)
            print(f"✓ Draft saved to {draft_file}")

    prev_review_path = ""
    for iteration in range(start_iteration, MAX_REVIEW_ITERATIONS + 1):
        print(f"\n--- Review iteration {iteration}/{MAX_REVIEW_ITERATIONS} ---")

        if not prev_review_path and iteration > 1:
            candidate = f"{out_base}-review-{iteration - 1}.md"
            if os.path.exists(candidate):
                prev_review_path = candidate

        review_file = f"{out_base}-review-{iteration}.md"
        if os.path.exists(review_file):
            print(f"Loading existing review {iteration}...")
            with open(review_file, "r", encoding="utf-8") as f:
                review = f.read()
            is_good = _review_ends_good_to_go(review)
        else:
            review, is_good = review_with_codex(
                draft,
                previous_review_file=prev_review_path,
                verbose=verbose,
                transcript=transcript,
                editorial_guidance=editorial_guidance,
            )
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(review)
            print(f"✓ Review saved to {review_file}")

        prev_review_path = review_file

        if is_good:
            print(f"✓ GOOD_TO_GO after {iteration} iteration(s)")
            break

        print("Issues found, revising...")

        revised_file = f"{out_base}-draft-v{iteration + 1}.md"
        if os.path.exists(revised_file):
            print(f"Loading existing revision v{iteration + 1}...")
            with open(revised_file, "r", encoding="utf-8") as f:
                draft = f.read()
        else:
            draft = revise_draft(
                transcript,
                draft,
                review,
                editorial_guidance=editorial_guidance,
                raw_notes=raw_notes,
                verbose=verbose,
                title=title,
                teaser=teaser,
                chapters=chapters,
            )
            with open(revised_file, "w", encoding="utf-8") as f:
                f.write(draft)
            print(f"✓ Revised draft saved to {revised_file}")
    else:
        print(f"⚠ Reached {MAX_REVIEW_ITERATIONS} iterations without GOOD_TO_GO, using latest draft")

    with open(article_file, "w", encoding="utf-8") as f:
        f.write(draft)
    print(f"✓ Final article saved to {article_file}")
    for warning in article_style_warnings(draft):
        print(f"⚠ Article: {warning}")

    return draft


_ANCHOR_RE = re.compile(r"\{#([a-z0-9-]+)\}\s*$")


def article_style_warnings(article: str) -> list[str]:
    """Mechanical checks from blog-tone-of-voice.md that the review can miss."""
    warnings: list[str] = []
    words = len(article.split())
    if words > 4000:
        warnings.append(f"{words} words (cap 4,000, target 2,500-3,500)")
    if "\u2014" in article:
        warnings.append(f"{article.count(chr(0x2014))} em dash(es)")
    ids: list[str] = []
    for line in article.splitlines():
        if re.match(r"^#{2,3} ", line):
            match = _ANCHOR_RE.search(line)
            if match:
                ids.append(match.group(1))
            else:
                warnings.append(f"heading without {{#id}}: {line.strip()}")
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        warnings.append(f"duplicate heading ids: {', '.join(duplicates)}")
    if is_legacy_article(article):
        warnings.append("has a Summary, Key Topics or Highlights section")
    faq = re.search(r"\{#faq\}(.*?)(?=^## |\Z)", article, flags=re.MULTILINE | re.DOTALL)
    if not faq:
        warnings.append("no '## Common questions, answered {#faq}' section")
    else:
        questions = len(re.findall(r"^#{3,4} ", faq.group(1), flags=re.MULTILINE))
        if questions != 3:
            warnings.append(f"{questions} common questions (exactly 3 expected)")
    return warnings


ALLOWED_ARTICLE_TAGS = frozenset({"mark", "figure", "figcaption", "img", "br", "sup", "sub"})
_FENCED_CODE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.MULTILINE | re.DOTALL)
_INLINE_CODE_RE = re.compile(r"(`+).+?\1", re.DOTALL)
_SHORTCODE_RE = re.compile(r"\{\{[<%].*?[>%]\}\}", re.DOTALL)
_AUTOLINK_RE = re.compile(r"<(?:https?|mailto):[^>\s]*>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9-]*)\b[^>]*>")
_EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
_JS_LINK_RE = re.compile(r"\]\(\s*<?\s*javascript:", re.IGNORECASE)


def article_html_problems(article: str) -> list[str]:
    """Raw HTML the page must not carry: tags outside ALLOWED_ARTICLE_TAGS,
    ``on*=`` handlers and ``javascript:`` URLs. Code, shortcodes and autolinks are skipped.
    """
    text = _FENCED_CODE_RE.sub("", article)
    text = _INLINE_CODE_RE.sub("", text)
    text = _AUTOLINK_RE.sub("", _SHORTCODE_RE.sub("", text))
    problems: list[str] = []
    for match in _HTML_TAG_RE.finditer(text):
        tag = match.group(0)
        if match.group(1).lower() not in ALLOWED_ARTICLE_TAGS:
            problems.append(f"tag not allowed: {tag}")
        elif _EVENT_ATTR_RE.search(tag) or "javascript:" in tag.lower():
            problems.append(f"script in tag: {tag}")
    problems.extend(f"javascript: link: {m.group(0)}" for m in _JS_LINK_RE.finditer(text))
    return problems


def episode_source_text(chapters: str, transcript: str) -> str:
    """The approved chapters, when there are any, then the corrected transcript."""
    parts = []
    if chapters:
        parts.append(f"--- CHAPTERS ---\n{chapters}\n")
    parts.append(f"--- TRANSCRIPT ---\n{transcript}\n")
    return "\n".join(parts)


def _codex_options(
    base_prompt: str,
    chapters: str,
    transcript: str,
    editorial_guidance: str,
    verbose: bool,
) -> str:
    prompt = base_prompt
    if editorial_guidance:
        prompt += f"\nEditorial context for this episode: {editorial_guidance}"
    return run_codex(prompt, stdin_text=episode_source_text(chapters, transcript), verbose=verbose)


def generate_title_options(
    chapters: str, transcript: str, editorial_guidance: str = "", verbose: bool = False
) -> str:
    """Generate 5 title options from the chapters and the corrected transcript using Codex CLI."""
    return _codex_options(TITLES_PROMPT, chapters, transcript, editorial_guidance, verbose)


def generate_description_options(
    chapters: str, transcript: str, editorial_guidance: str = "", verbose: bool = False
) -> str:
    """Generate 5 teaser options from the chapters and the corrected transcript using Codex CLI."""
    return _codex_options(DESCRIPTIONS_PROMPT, chapters, transcript, editorial_guidance, verbose)


def _select_from_numbered_codex_output(lines_text: str, choice: str) -> str | None:
    """Return the selected line for choices 1–5, or None if nothing matched."""
    if choice not in ("1", "2", "3", "4", "5"):
        return None
    for line in lines_text.splitlines():
        line = line.strip()
        if line.startswith(f"{choice}.") or line.startswith(f"{choice})"):
            return re.sub(r"^\d+[\.\)]\s*", "", line).strip()
    lines = [l.strip() for l in lines_text.splitlines() if l.strip()]
    idx = int(choice) - 1
    if idx < len(lines):
        return re.sub(r"^\d+[\.\)]\s*", "", lines[idx]).strip()
    return None


def _interactive_codex_pick(
    chapters: str,
    transcript: str,
    editorial_guidance: str,
    verbose: bool,
    *,
    generate_options: Callable[..., str],
    announce_options: str,
    instruct_line1: str,
    instruct_line2: str,
    regen_hint_label: str,
    custom_prompt: str,
    input_func=input,
) -> str:
    regen_hint = ""
    while True:
        print(announce_options)
        combined = editorial_guidance
        if regen_hint:
            combined = f"{editorial_guidance}\nAdditional guidance: {regen_hint}".strip()
        options_text = generate_options(chapters, transcript, editorial_guidance=combined, verbose=verbose)
        print(f"\n{options_text}\n")
        print(instruct_line1)
        print(instruct_line2, end="", flush=True)
        choice = input_func().strip().lower()

        if choice in ("1", "2", "3", "4", "5"):
            picked = _select_from_numbered_codex_output(options_text, choice)
            if picked is not None:
                return picked
        elif choice == "c":
            print(custom_prompt, end="", flush=True)
            custom = input_func().strip()
            if custom:
                return custom
        elif choice == "r":
            print(regen_hint_label, end="", flush=True)
            regen_hint = input_func().strip()
        else:
            print("Invalid choice, try again.")


def pick_title(
    chapters: str, transcript: str, editorial_guidance: str = "", verbose: bool = False, input_func=input
) -> str:
    """Present title options and let the user choose or regenerate."""
    return _interactive_codex_pick(
        chapters,
        transcript,
        editorial_guidance,
        verbose,
        generate_options=generate_title_options,
        announce_options="\nGenerating title options...",
        instruct_line1="Enter a number (1-5) to pick, 'c' to type a custom title,",
        instruct_line2="or 'r' to regenerate with guidance: ",
        regen_hint_label="Enter guidance (e.g. 'focus more on security'): ",
        custom_prompt="Enter custom title: ",
        input_func=input_func,
    )


def pick_description(
    chapters: str, transcript: str, editorial_guidance: str = "", verbose: bool = False, input_func=input
) -> str:
    """Present teaser options and let the user choose or regenerate."""
    return _interactive_codex_pick(
        chapters,
        transcript,
        editorial_guidance,
        verbose,
        generate_options=generate_description_options,
        announce_options="\nGenerating podcast description options...",
        instruct_line1="Enter a number (1-5) to pick, 'c' to type a custom description,",
        instruct_line2="or 'r' to regenerate with guidance: ",
        regen_hint_label="Enter guidance: ",
        custom_prompt="Enter custom description: ",
        input_func=input_func,
    )
