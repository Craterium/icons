#!/usr/bin/env python3
"""build the craterium pixel icon set.

usage:
    python3 tools/craterium.py check            validate every source grid
    python3 tools/craterium.py svg              write svg/mono and svg/duotone
    python3 tools/craterium.py png              write png/<theme>/<variant>/<size>
    python3 tools/craterium.py sprite           write svg sprites per variant
    python3 tools/craterium.py manifest         write icons.json
    python3 tools/craterium.py preview          write preview.html (contact sheet)
    python3 tools/craterium.py all              everything above
    python3 tools/craterium.py new <cat> <name> copy the template to src/<cat>/<name>.txt
    python3 tools/craterium.py clean            remove generated files

source format (src/<category>/<name>.txt): 12 lines of 12 characters
    .  empty cell
    #  foreground cell, rendered with currentColor
    +  accent cell, var(--crt-accent) in duotone, currentColor in mono
lines starting with ; are comments. "; tags: a, b, c" adds search tags.

no dependencies. png files are written with zlib from the standard library.
"""
import json
import pathlib
import shutil
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TEMPLATE = ROOT / "tools" / "_template.txt"

GRID = 12
EMPTY, FG, ACCENT = ".", "#", "+"
MAX_ACCENT = 12
PNG_SIZES = (12, 48, 96)
VARIANTS = ("mono", "duotone")
ACCENT_FALLBACK = "#9BD14B"

# fixed colors for raster exports, from the craterium tokens
THEMES = {
    "on-dark": {"fg": "#F1EFE6", "accent": "#9BD14B"},
    "on-light": {"fg": "#0E1210", "accent": "#4A7020"},
}

GENERATED = ("svg", "png", "icons.json", "preview.html")


class GridError(Exception):
    pass


class Icon:
    def __init__(self, path):
        self.path = path
        self.name = path.stem
        self.category = path.parent.name
        self.tags = []
        self.rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(";"):
                key, _, value = line[1:].strip().partition(":")
                if key.strip() == "tags":
                    self.tags = [t.strip() for t in value.split(",") if t.strip()]
                continue
            if line.strip():
                self.rows.append(line.rstrip())

    def grid(self, variant):
        if variant == "mono":
            return [r.replace(ACCENT, FG) for r in self.rows]
        return self.rows

    def cells(self):
        return sum(GRID - r.count(EMPTY) for r in self.rows)

    def accents(self):
        return sum(r.count(ACCENT) for r in self.rows)


def load_icons():
    icons = [Icon(p) for p in sorted(SRC.glob("*/*.txt"))]
    seen = {}
    for icon in icons:
        if icon.name in seen:
            raise GridError(f"{icon.path}: name already used by {seen[icon.name]}")
        seen[icon.name] = icon.path
    return icons


def validate(icon):
    rows = icon.rows
    if len(rows) != GRID:
        raise GridError(f"{icon.path}: expected {GRID} rows, got {len(rows)}")
    for i, row in enumerate(rows):
        if len(row) != GRID:
            raise GridError(f"{icon.path}: row {i + 1} has {len(row)} cells, expected {GRID}")
        unknown = set(row) - {EMPTY, FG, ACCENT}
        if unknown:
            raise GridError(f"{icon.path}: row {i + 1} has unknown cells {sorted(unknown)}")


def filled(rows, x, y):
    return 0 <= x < GRID and 0 <= y < GRID and rows[y][x] != EMPTY


def warnings_for(icon):
    rows = icon.rows
    found = []
    accent = icon.accents()
    if accent == 0:
        found.append("no accent cells, the duotone variant would equal mono")
    if accent > MAX_ACCENT:
        found.append(f"{accent} accent cells, keep it at {MAX_ACCENT} or fewer")
    top, bottom = rows[0] != EMPTY * GRID, rows[-1] != EMPTY * GRID
    left = any(r[0] != EMPTY for r in rows)
    right = any(r[-1] != EMPTY for r in rows)
    if (top and bottom) or (left and right):
        found.append("shape reaches the padding on two opposite sides")
    for y in range(GRID):
        for x in range(GRID):
            if rows[y][x] == EMPTY:
                continue
            if not any(filled(rows, x + dx, y + dy)
                       for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy):
                found.append(f"orphan pixel at column {x + 1}, row {y + 1}")
    return found


def runs(rows, cell):
    for y, row in enumerate(rows):
        x = 0
        while x < GRID:
            if row[x] != cell:
                x += 1
                continue
            start = x
            while x < GRID and row[x] == cell:
                x += 1
            yield start, y, x - start


def path_d(rows, cell):
    return "".join(f"M{x} {y}h{w}v1h-{w}z" for x, y, w in runs(rows, cell))


def svg_paths(rows):
    parts = []
    fg, accent = path_d(rows, FG), path_d(rows, ACCENT)
    if fg:
        parts.append(f'<path fill="currentColor" d="{fg}"/>')
    if accent:
        parts.append(f'<path style="fill: var(--crt-accent, {ACCENT_FALLBACK})" d="{accent}"/>')
    return "".join(parts)


def to_svg(icon, variant):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}" '
        f'width="24" height="24" shape-rendering="crispEdges" aria-hidden="true" '
        f'data-icon="{icon.name}">{svg_paths(icon.grid(variant))}</svg>\n'
    )


def hex_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def png_bytes(rows, size, colors):
    """nearest neighbour raster of a grid, RGBA, size must be a multiple of 12"""
    scale = size // GRID
    fg = hex_rgb(colors["fg"]) + (255,)
    accent = hex_rgb(colors["accent"]) + (255,)
    pick = {EMPTY: (0, 0, 0, 0), FG: fg, ACCENT: accent}
    raw = bytearray()
    for row in rows:
        line = bytearray(b"\x00")
        for cell in row:
            line += bytes(pick[cell]) * scale
        raw += bytes(line) * scale

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8", newline="\n")
    else:
        path.write_bytes(data)


def cmd_check(icons):
    total = 0
    for icon in icons:
        validate(icon)
        for w in warnings_for(icon):
            print(f"warning: {icon.path.relative_to(ROOT)}: {w}", file=sys.stderr)
            total += 1
    print(f"checked {len(icons)} icons, {total} warning(s)")
    return total


def cmd_svg(icons):
    for variant in VARIANTS:
        for icon in icons:
            write(ROOT / "svg" / variant / f"{icon.name}.svg", to_svg(icon, variant))
    print(f"wrote {len(icons) * len(VARIANTS)} svg files")


def cmd_png(icons):
    count = 0
    for theme, colors in THEMES.items():
        for variant in VARIANTS:
            for size in PNG_SIZES:
                for icon in icons:
                    out = ROOT / "png" / theme / variant / str(size) / f"{icon.name}.png"
                    write(out, png_bytes(icon.grid(variant), size, colors))
                    count += 1
    print(f"wrote {count} png files")


def cmd_sprite(icons):
    for variant in VARIANTS:
        symbols = "".join(
            f'<symbol id="crt-{i.name}" viewBox="0 0 {GRID} {GRID}">{svg_paths(i.grid(variant))}</symbol>'
            for i in icons
        )
        write(ROOT / "svg" / f"sprite-{variant}.svg",
              f'<svg xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">{symbols}</svg>\n')
    print(f"wrote {len(VARIANTS)} sprites")


def cmd_manifest(icons):
    data = {
        "name": "craterium-icons",
        "grid": GRID,
        "count": len(icons),
        "icons": [
            {"name": i.name, "category": i.category, "tags": i.tags,
             "cells": i.cells(), "accent": i.accents()}
            for i in icons
        ],
    }
    write(ROOT / "icons.json", json.dumps(data, indent=2) + "\n")
    print("wrote icons.json")


def cmd_preview(icons):
    by_cat = {}
    for icon in icons:
        by_cat.setdefault(icon.category, []).append(icon)
    sections = []
    for cat, items in by_cat.items():
        tiles = "".join(
            f'<figure title="{i.name}"><span class="m">{to_svg(i, "mono")}</span>'
            f'<span class="d">{to_svg(i, "duotone")}</span><figcaption>{i.name}</figcaption></figure>'
            for i in items
        )
        sections.append(f"<h2>{cat} <small>{len(items)}</small></h2><div class=g>{tiles}</div>")
    html = f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Craterium Icons</title>
<style>
:root {{ --bg:#0E1210; --surface:#151B17; --border:#2C3A2E; --text:#F1EFE6; --text-2:#949D94; --crt-accent:#9BD14B; }}
:root[data-theme=light] {{ --bg:#F1EFE6; --surface:#FBFAF5; --border:#CFCBBC; --text:#0E1210; --text-2:#565E57; --crt-accent:#4A7020; }}
body {{ margin:0; padding:24px 16px; background:var(--bg); color:var(--text); font:14px/1.4 ui-monospace, monospace; }}
header {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; max-width:1200px; margin:0 auto; }}
h1 {{ font-size:20px; margin:0 auto 0 0; }}
button {{ font:inherit; color:var(--text); background:var(--surface); border:2px solid var(--border); padding:4px 10px; cursor:pointer; }}
main {{ max-width:1200px; margin:0 auto; }}
h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.08em; color:var(--text-2); margin:32px 0 12px; }}
.g {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(96px, 1fr)); gap:8px; }}
figure {{ margin:0; padding:12px 4px 8px; background:var(--surface); border:2px solid var(--border); display:flex; flex-direction:column; align-items:center; gap:8px; }}
figure svg {{ width:var(--s, 48px); height:var(--s, 48px); display:block; }}
figcaption {{ font-size:11px; color:var(--text-2); text-align:center; word-break:break-all; }}
body.mono .d, body:not(.mono) .m {{ display:none; }}
</style>
<header><h1>craterium icons · {len(icons)}</h1>
<button onclick="document.body.classList.toggle('mono')">mono / duotone</button>
<button onclick="var r=document.documentElement;r.dataset.theme=r.dataset.theme==='light'?'dark':'light'">theme</button>
<button onclick="var s=document.body.style;s.setProperty('--s',({{'48px':'24px','24px':'12px','12px':'96px','96px':'48px'}})[s.getPropertyValue('--s')||'48px'])">size</button>
</header><main>{''.join(sections)}</main>
"""
    write(ROOT / "preview.html", html)
    print("wrote preview.html")


def cmd_new(category, name):
    out = SRC / category / f"{name}.txt"
    if out.exists():
        sys.exit(f"error: {out} already exists")
    write(out, TEMPLATE.read_text(encoding="utf-8"))
    print(f"created {out.relative_to(ROOT)}")


def cmd_clean():
    for name in GENERATED:
        target = ROOT / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    print("cleaned")


def main():
    args = sys.argv[1:] or ["all"]
    cmd = args[0]
    try:
        if cmd == "clean":
            return cmd_clean()
        if cmd == "new":
            if len(args) != 3:
                sys.exit("usage: craterium.py new <category> <name>")
            return cmd_new(args[1], args[2])
        icons = load_icons()
        for icon in icons:
            validate(icon)
        steps = {"check": cmd_check, "svg": cmd_svg, "png": cmd_png, "sprite": cmd_sprite,
                 "manifest": cmd_manifest, "preview": cmd_preview}
        if cmd == "all":
            for step in steps.values():
                step(icons)
        elif cmd in steps:
            warns = steps[cmd](icons)
            if cmd == "check" and warns and "--strict" in args:
                sys.exit(1)
        else:
            sys.exit(f"unknown command {cmd}, see --help in the file header")
    except GridError as err:
        sys.exit(f"error: {err}")


if __name__ == "__main__":
    main()
