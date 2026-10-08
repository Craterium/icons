#!/usr/bin/env python3
"""render the readme banner and social card from the icon sources.

usage:
    python3 tools/banner.py            writes banner/banner.png, banner@2x.png, social-card.png

needs pillow (pip install pillow). the icon wall is drawn from src/, so the
banner always shows the current set. dimming is done in hard steps, never a
gradient, to stay inside the brand rules.
"""
import pathlib
import random
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import craterium  # noqa: E402

ROOT = craterium.ROOT
FONTS = ROOT / "tools" / "fonts"
OUT = ROOT / "banner"

BG = "#0E1210"
TEXT = "#F1EFE6"
TEXT_2 = "#949D94"
ACCENT = "#9BD14B"

# (fg, accent) per distance step from the text, nearest first; None hides the icon
STEPS = [
    None,
    ("#19201B", "#24321C"),
    ("#222C24", "#34491F"),
    ("#2C3A2E", "#4A7020"),
]
HIGHLIGHT = ("#45574A", ACCENT)

# the craterium mark, 12 x 12, from logo/craterium-mark.svg
MARK = [
    "....####.+++",
    "..######.+++",
    ".###.....+++",
    ".##.........",
    "##........##",
    "##........##",
    "##........##",
    "##........##",
    ".##......##.",
    ".###....###.",
    "..########..",
    "....####....",
]


def draw_grid(draw, rows, x0, y0, cell, fg, accent):
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            color = fg if c == "#" else accent if c == "+" else None
            if color:
                draw.rectangle([x0 + x * cell, y0 + y * cell,
                                x0 + (x + 1) * cell - 1, y0 + (y + 1) * cell - 1], fill=color)


def render(width, height, scale, out):
    icons = craterium.load_icons()
    rng = random.Random(12)
    order = icons[:]
    rng.shuffle(order)

    img = Image.new("RGB", (width * scale, height * scale), BG)
    draw = ImageDraw.Draw(img)

    cell = 4 * scale              # 48 px icons at 1x
    pitch = 80 * scale            # icon plus gap, divides 1280, 320 and 640
    cols = img.width // pitch
    rows = img.height // pitch
    off_x = (img.width - (cols * pitch - (pitch - 12 * cell))) // 2
    off_y = (img.height - (rows * pitch - (pitch - 12 * cell))) // 2

    # text block size decides the clear zone
    title_font = ImageFont.truetype(str(FONTS / "SUSE-600.ttf"), 64 * scale)
    sub_font = ImageFont.truetype(str(FONTS / "FragmentMono-Regular.ttf"), 20 * scale)
    word_a, word_b = "craterium", " icons"
    sub = f"{len(icons)} pixel icons · 12×12 grid · mono + duotone · svg + png"
    mark_cell = 6 * scale
    mark_w = 12 * mark_cell
    gap = 24 * scale
    wa = draw.textlength(word_a, font=title_font)
    wb = draw.textlength(word_b, font=title_font)
    title_w = mark_w + gap + wa + wb
    sub_w = draw.textlength(sub, font=sub_font)
    block_w = max(title_w, sub_w)
    block_h = mark_w + 28 * scale + 20 * scale
    cx, cy = img.width / 2, img.height / 2
    half_w, half_h = block_w / 2 + 40 * scale, block_h / 2 + 40 * scale

    i = 0
    for r in range(rows):
        for c in range(cols):
            x = off_x + c * pitch
            y = off_y + r * pitch
            # normalized distance of the icon center to the clear zone
            dx = max(0, abs(x + 6 * cell - cx) - half_w) / pitch
            dy = max(0, abs(y + 6 * cell - cy) - half_h) / pitch
            inside = abs(x + 6 * cell - cx) < half_w and abs(y + 6 * cell - cy) < half_h
            step = 0 if inside else min(len(STEPS) - 1, 1 + int(max(dx, dy) * 1.5))
            icon = order[i % len(order)]
            i += 1
            colors = STEPS[step]
            if colors is None:
                continue
            if step == len(STEPS) - 1 and rng.random() < 0.06:
                colors = HIGHLIGHT
            draw_grid(draw, icon.grid("duotone"), x, y, cell, *colors)

    # title row: mark, then "craterium icons"
    top = cy - block_h / 2
    left = cx - title_w / 2
    draw_grid(draw, MARK, int(left), int(top), mark_cell, TEXT, ACCENT)
    ascent, descent = title_font.getmetrics()
    ty = top + mark_w / 2 - (ascent - descent) / 2 - descent * 0.35
    tx = left + mark_w + gap
    draw.text((tx, ty), word_a, font=title_font, fill=TEXT)
    draw.text((tx + wa, ty), word_b, font=title_font, fill=ACCENT)
    draw.text((cx - sub_w / 2, top + mark_w + 28 * scale), sub, font=sub_font, fill=TEXT_2)

    OUT.mkdir(exist_ok=True)
    img.save(OUT / out, optimize=True)
    print(f"wrote banner/{out}")


def main():
    render(1280, 320, 1, "banner.png")
    render(1280, 320, 2, "banner@2x.png")
    render(1280, 640, 1, "social-card.png")


if __name__ == "__main__":
    main()
