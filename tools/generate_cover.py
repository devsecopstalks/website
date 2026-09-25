"""Generate a per-episode cover image in the DevSecOps Talks brand.

Colours are sampled from
static/images/pod_cover.png; the font is Nunito (OFL, tools/fonts/), a rounded
geometric face close to the logo lettering, so rendering is identical on any machine.
"""

import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
COVERS_DIR = os.path.join(REPO_ROOT, "static", "images", "covers")
LOGO_PATH = os.path.join(REPO_ROOT, "static", "images", "logo.png")
FONT_PATH = os.path.join(TOOLS_DIR, "fonts", "Nunito-Variable.ttf")

SIZE = 1400
TEAL_DEEP = (0, 68, 69)  # pod_cover background
TEAL_GLOW = (18, 96, 94)  # lifted towards the logo's #2c7973 for the centre glow
GREEN = (110, 185, 142)
YELLOW = (255, 216, 0)
WHITE = (255, 255, 255)
MAX_WIDTH = SIZE - 2 * int(SIZE * 0.12)
MAX_FONT_SIZE = int(SIZE * 0.12)
MIN_FONT_SIZE = 48
MAX_TEXT_HEIGHT = SIZE * 0.44

# Connector words after which the leading "hook" phrase of a title usually ends.
_SPLIT_WORDS = {"vs", "in", "for", "with", "and", "to", "of", "on", "from", "not"}


def _pick_highlight(words):
    """Mark the opening phrase, up to the first connector word, for the accent colour."""
    cut = None
    for i, w in enumerate(words[1:], start=1):
        if re.sub(r"[^\w]", "", w).lower() in _SPLIT_WORDS:
            cut = i
            break
    if cut is None:
        cut = min(2, len(words))
    return [(w, True) for w in words[:cut]] + [(w, False) for w in words[cut:]]


def _font(size, weight="ExtraBold"):
    font = ImageFont.truetype(FONT_PATH, size)
    font.set_variation_by_name(weight)
    return font


def _background():
    mask = Image.radial_gradient("L").resize((SIZE, SIZE), Image.Resampling.BICUBIC)
    # The gradient is centred; shift it up so the glow sits behind the title.
    mask = mask.transform(mask.size, Image.Transform.AFFINE, (1, 0, 0, 0, 1, SIZE * 0.06), fillcolor=255)
    return Image.composite(Image.new("RGB", (SIZE, SIZE), TEAL_DEEP),
                           Image.new("RGB", (SIZE, SIZE), TEAL_GLOW), mask)


def _wrap(words, font, draw):
    lines, cur = [], []
    for w in words:
        trial = cur + [w]
        width = draw.textlength(" ".join(t for t, _ in trial), font=font)
        if width > MAX_WIDTH and cur:
            lines.append(cur)
            cur = [w]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _layout(words, draw):
    size = MAX_FONT_SIZE
    while True:
        font = _font(size)
        lines = _wrap(words, font, draw)
        line_h = int(size * 1.18)
        if line_h * len(lines) < MAX_TEXT_HEIGHT or size <= MIN_FONT_SIZE:
            return font, lines, line_h
        size -= 6


def _centered(draw, y, text, font, fill):
    x = (SIZE - draw.textlength(text, font=font)) / 2
    draw.text((x, y), text, font=font, fill=fill)


def clean_title(title):
    """Drop a leading "#110 - " so the cover carries only the headline."""
    return re.sub(r"^\s*#?\d+\s*[-–—:]\s*", "", title).strip()


def render_cover(episode_number, title, guests=None, out_path=None):
    """Render the cover PNG for `title` to `out_path`."""
    im = _background()
    draw = ImageDraw.Draw(im)

    _centered(draw, SIZE * 0.12, f"EPISODE {episode_number}", _font(44, "Black"), GREEN)

    words = _pick_highlight(clean_title(title).split())
    font, lines, line_h = _layout(words, draw)
    y = SIZE * 0.47 - line_h * len(lines) / 2
    space = draw.textlength(" ", font=font)
    for line in lines:
        x = (SIZE - draw.textlength(" ".join(t for t, _ in line), font=font)) / 2
        for word, accent in line:
            draw.text((x, y), word, font=font, fill=YELLOW if accent else WHITE)
            x += draw.textlength(word, font=font) + space
        y += line_h

    # Titles usually name the guest already; only credit the ones they leave out.
    guests = [g for g in guests or [] if g.lower() not in title.lower()]
    if guests:
        _centered(draw, y + line_h * 0.35, "with " + ", ".join(guests), _font(46, "Bold"), GREEN)

    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo_w = int(SIZE * 0.38)
    logo = logo.resize((logo_w, round(logo.height * logo_w / logo.width)), Image.Resampling.LANCZOS)
    im.paste(logo, ((SIZE - logo_w) // 2, int(SIZE * 0.86) - logo.height // 2), logo)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    im.save(out_path, optimize=True)
    return out_path


def generate_cover(episode_number, title, guests=None, out_path=None):
    """Write static/images/covers/NNN.png (or `out_path`) unless it already exists.

    Returns the site-relative path for the page's `image` front matter, e.g.
    "/images/covers/110.png". An existing file is kept so a hand-made cover wins.
    """
    filename = f"{int(episode_number):03d}.png"
    target = out_path or os.path.join(COVERS_DIR, filename)
    if not os.path.exists(target):
        render_cover(episode_number, title, guests, target)
        print(f"✓ Generated cover: {target}")
    return f"/images/covers/{filename}"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: generate_cover.py <episode_number> <title> [guest ...]")
        sys.exit(1)
    print(generate_cover(int(sys.argv[1]), sys.argv[2], sys.argv[3:] or None))
