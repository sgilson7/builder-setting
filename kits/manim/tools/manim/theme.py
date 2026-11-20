#!/usr/bin/env python3
"""Write deck/manim/theme.css from data/manim/theme.json, so the deck, the
originals beside the Manim versions, and the renders share one palette and one pair
of fonts served from the deck's own origin (Manim Lab MN-Q4).

    python3 tools/manim/theme.py           write it
    python3 tools/manim/theme.py --check   exit 1 if it is out of date
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "data" / "manim" / "theme.json"
CSS = ROOT / "deck" / "manim" / "theme.css"
FALLBACK = {"body": "system-ui, -apple-system, \"Segoe UI\", sans-serif",
            "mono": "ui-monospace, Menlo, Consolas, monospace"}


def tokens(colours):
    out = []
    for k, v in colours.items():
        name = "--" + k.replace("_", "-")
        if isinstance(v, list):
            out.append(f"{name}: color-mix(in srgb, {v[0]} {v[1]}%, transparent);")
        else:
            out.append(f"{name}: {v};")
    return " ".join(out)


def css(theme):
    lines = ["/* Written by tools/manim/theme.py from data/manim/theme.json. Do not edit. */"]
    for key, f in theme["fonts"].items():
        rel = "../" + Path(f["file"]).relative_to("deck").as_posix()
        lines.append(f"@font-face {{ font-family: \"{f['family']}\"; src: url(\"{rel}\") format(\"truetype\"); "
                     "font-weight: 100 900; font-display: swap; }")
    fonts = " ".join(f"--{k}: \"{f['family']}\", {FALLBACK[k]};" for k, f in theme["fonts"].items())
    lines.append(f":root {{ {fonts} {tokens(theme['light'])} }}")
    dark = tokens(theme["dark"])
    lines.append(f"@media (prefers-color-scheme: dark) {{ :root:not([data-theme=\"light\"]) {{ {dark} color-scheme: dark; }} }}")
    lines.append(f":root[data-theme=\"dark\"] {{ {dark} color-scheme: dark; }}")
    return "\n".join(lines) + "\n"


def main(argv):
    want = css(json.loads(THEME.read_text()))
    if "--check" in argv:
        if not CSS.exists() or CSS.read_text() != want:
            print("deck/manim/theme.css is out of date: run python3 tools/manim/theme.py")
            return 1
        print("deck/manim/theme.css matches theme.json")
        return 0
    CSS.parent.mkdir(parents=True, exist_ok=True)
    CSS.write_text(want)
    print(f"wrote {CSS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
