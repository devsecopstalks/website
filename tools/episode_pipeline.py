"""
Claude Code + Codex adversarial review loop for episode articles.
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

MAX_REVIEW_ITERATIONS = 10

with open(CONTEXT_FILE, "r", encoding="utf-8") as _f:
    _CONTENT_CONTEXT = _f.read()

with open(STYLE_FILE, "r", encoding="utf-8") as _f:
    _WRITING_STYLE = _f.read()


def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ and inject context + writing style."""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    return (
        template.replace("{{CONTEXT}}", _CONTENT_CONTEXT).replace("{{STYLE}}", _WRITING_STYLE)
    )


DRAFT_PROMPT = load_prompt("draft")
REVISE_PROMPT = load_prompt("revise")
REVIEW_PROMPT = load_prompt("review")
TITLES_PROMPT = load_prompt("titles")
DESCRIPTIONS_PROMPT = load_prompt("descriptions")
GUESTS_PROMPT = load_prompt("guests")


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
        timeout=900,
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


def run_codex(prompt: str, stdin_text: str = "", verbose=False) -> str:
    """Run OpenAI Codex CLI in non-interactive mode. Returns output text."""
    if not shutil.which("codex"):
        print("Error: 'codex' CLI not found. Install with: npm install -g @openai/codex")
        sys.exit(1)

    if verbose:
        print(f"Running codex exec (prompt: {len(prompt)} chars, stdin: {len(stdin_text)} chars)...")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        cmd = [
            "codex",
            "exec",
            "--model",
            "gpt-5.6-sol",
            "-o",
            tmp_path,
            "--full-auto",
            "--add-dir",
            EPISODES_DIR,
            "--add-dir",
            REPO_ROOT,
        ]
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
            timeout=900,
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
    """Extract article content starting from ## Summary."""
    marker = "## Summary"
    if marker in text:
        parts = text.split(marker)
        article = marker + parts[-1]
    else:
        print("⚠ Output missing '## Summary' — using as-is")
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
            }
        )

    if not guests and status != "needs_operator":
        status = "no_guests"
    elif status == "no_guests":
        status = "verified"

    return {
        "status": status,
        "guests": guests,
        "notes": str(data.get("notes") or "").strip(),
    }


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
        "Introduce the guest(s) near the start of the article.",
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


def generate_draft(
    transcript: str,
    editorial_guidance: str = "",
    raw_notes: str = "",
    verbose: bool = False,
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
) -> tuple[str, bool]:
    """Review draft using Codex CLI. Returns (review_text, is_good)."""
    print("Reviewing with Codex (grumpy expert mode)...")

    prompt = REVIEW_PROMPT + "\n\nThe article to review is provided on stdin."
    if previous_review_file:
        prompt += (
            f" Also read your previous review from {previous_review_file} — "
            "do not repeat issues that were already fixed."
        )

    review = run_codex(prompt, stdin_text=draft, verbose=verbose)

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
    parts.append(f"""

--- ORIGINAL TRANSCRIPT ---
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


def generate_article(
    transcript: str,
    out_base: str,
    editorial_guidance: str = "",
    raw_notes: str = "",
    verbose: bool = False,
) -> str:
    """Run the draft-review loop. Returns final article text."""
    article_file = f"{out_base}-article.md"
    if os.path.exists(article_file):
        print("Loading existing final article...")
        with open(article_file, "r", encoding="utf-8") as f:
            return f.read()

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
                draft, previous_review_file=prev_review_path, verbose=verbose
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
            )
            with open(revised_file, "w", encoding="utf-8") as f:
                f.write(draft)
            print(f"✓ Revised draft saved to {revised_file}")
    else:
        print(f"⚠ Reached {MAX_REVIEW_ITERATIONS} iterations without GOOD_TO_GO, using latest draft")

    with open(article_file, "w", encoding="utf-8") as f:
        f.write(draft)
    print(f"✓ Final article saved to {article_file}")

    return draft


def _codex_options_for_article(
    base_prompt: str,
    article: str,
    editorial_guidance: str,
    verbose: bool,
) -> str:
    prompt = base_prompt
    if editorial_guidance:
        prompt += f"\nEditorial context for this episode: {editorial_guidance}"
    return run_codex(prompt, stdin_text=article, verbose=verbose)


def generate_title_options(article: str, editorial_guidance: str = "", verbose: bool = False) -> str:
    """Generate 5 title options using Codex CLI."""
    return _codex_options_for_article(TITLES_PROMPT, article, editorial_guidance, verbose)


def generate_description_options(article: str, editorial_guidance: str = "", verbose: bool = False) -> str:
    """Generate 5 podcast description options using Codex CLI."""
    return _codex_options_for_article(DESCRIPTIONS_PROMPT, article, editorial_guidance, verbose)


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
    article: str,
    editorial_guidance: str,
    verbose: bool,
    *,
    generate_options: Callable[[str, str, bool], str],
    announce_options: str,
    instruct_line1: str,
    instruct_line2: str,
    regen_hint_label: str,
    custom_prompt: str,
) -> str:
    regen_hint = ""
    while True:
        print(announce_options)
        combined = editorial_guidance
        if regen_hint:
            combined = f"{editorial_guidance}\nAdditional guidance: {regen_hint}".strip()
        options_text = generate_options(article, editorial_guidance=combined, verbose=verbose)
        print(f"\n{options_text}\n")
        print(instruct_line1)
        print(instruct_line2, end="", flush=True)
        choice = input().strip().lower()

        if choice in ("1", "2", "3", "4", "5"):
            picked = _select_from_numbered_codex_output(options_text, choice)
            if picked is not None:
                return picked
        elif choice == "c":
            print(custom_prompt, end="", flush=True)
            custom = input().strip()
            if custom:
                return custom
        elif choice == "r":
            print(regen_hint_label, end="", flush=True)
            regen_hint = input().strip()
        else:
            print("Invalid choice, try again.")


def pick_title(article: str, editorial_guidance: str = "", verbose: bool = False) -> str:
    """Present title options and let the user choose or regenerate."""
    return _interactive_codex_pick(
        article,
        editorial_guidance,
        verbose,
        generate_options=generate_title_options,
        announce_options="\nGenerating title options...",
        instruct_line1="Enter a number (1-5) to pick, 'c' to type a custom title,",
        instruct_line2="or 'r' to regenerate with guidance: ",
        regen_hint_label="Enter guidance (e.g. 'focus more on security'): ",
        custom_prompt="Enter custom title: ",
    )


def pick_description(article: str, editorial_guidance: str = "", verbose: bool = False) -> str:
    """Present description options and let the user choose or regenerate."""
    return _interactive_codex_pick(
        article,
        editorial_guidance,
        verbose,
        generate_options=generate_description_options,
        announce_options="\nGenerating podcast description options...",
        instruct_line1="Enter a number (1-5) to pick, 'c' to type a custom description,",
        instruct_line2="or 'r' to regenerate with guidance: ",
        regen_hint_label="Enter guidance: ",
        custom_prompt="Enter custom description: ",
    )
