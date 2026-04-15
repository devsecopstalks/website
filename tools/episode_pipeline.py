"""
Claude Code + Codex adversarial review loop for episode articles.
Checkpoints under tools/out/{stem}-* — see SiRob process-recording pattern.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
EPISODES_DIR = os.path.join(TOOLS_DIR, "..", "content", "episodes")
PROMPTS_DIR = os.path.join(TOOLS_DIR, "prompts")
CONTEXT_FILE = os.path.join(TOOLS_DIR, "podcast-context.md")

MAX_REVIEW_ITERATIONS = 5

with open(CONTEXT_FILE, "r", encoding="utf-8") as _f:
    _CONTENT_CONTEXT = _f.read()


def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/ and inject the podcast context."""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    with open(path, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("{{CONTEXT}}", _CONTENT_CONTEXT)


DRAFT_PROMPT = load_prompt("draft")
REVISE_PROMPT = load_prompt("revise")
TITLES_PROMPT = load_prompt("titles")
DESCRIPTIONS_PROMPT = load_prompt("descriptions")


def run_claude(prompt: str, verbose=False, allow_web=False) -> str:
    """Run Claude Code CLI with the given prompt on stdin. Returns output text."""
    if not shutil.which("claude"):
        print("Error: 'claude' CLI not found. Install Claude Code.")
        sys.exit(1)

    cmd = [
        "claude",
        "--print",
        "--model", "opus",
        "--add-dir", EPISODES_DIR,
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
        print(f"Claude failed (exit {result.returncode})")
        print(f"stdout: {result.stdout[:2000]}")
        sys.exit(1)

    output = result.stdout.strip()
    if not output:
        print("Claude returned empty response")
        sys.exit(1)

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
        cmd = ["codex", "exec", "-o", tmp_path, "--full-auto", "--add-dir", EPISODES_DIR]
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

    prompt = "Read the review instructions from prompts/review.md, then review the article provided on stdin."
    if previous_review_file:
        prompt += (
            f" Also read your previous review from {previous_review_file} — "
            "do not repeat issues that were already fixed."
        )

    review = run_codex(prompt, stdin_text=draft, verbose=verbose)

    is_good = review.strip().splitlines()[-1].strip() == "GOOD_TO_GO"
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
            is_good = review.strip().splitlines()[-1].strip() == "GOOD_TO_GO"
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
