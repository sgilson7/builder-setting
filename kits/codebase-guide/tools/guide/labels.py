#!/usr/bin/env python3
"""Check that every part of the guide says whether it is measured or proposed.

A guide mixes two kinds of claim: what the code does now (measured, read from
the codebase) and what it should do (proposed, a design). A reader must never
mistake one for the other. In the journal, mark each tab or entry about the
codebase with data-guide="measured" or data-guide="proposed":

- a measured part shows at least one excerpt (data-excerpt="KEY"), and each KEY
  is a row of data/excerpts.json;
- a proposed part shows no excerpt: it shows the contract it would add, never
  code that does not exist.

    python3 tools/guide/labels.py [JOURNAL/index.html]
"""

import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
OPEN = re.compile(r'<(section|article)\b[^>]*\bdata-guide="([a-z]+)"[^>]*>', re.S)


def parts(html):
    """(kind, id, body) for each element marked data-guide, up to its closing tag."""
    out = []
    for m in OPEN.finditer(html):
        tag, kind = m.group(1), m.group(2)
        depth, i = 1, m.end()
        for t in re.finditer(rf"<(/?){tag}\b", html[m.end():]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                i = m.end() + t.start()
                break
        ident = re.search(r'\bid="([^"]+)"', m.group(0))
        out.append((kind, ident.group(1) if ident else f"{tag} at character {m.start()}", html[m.end():i]))
    return out


def problems(html, keys):
    out = []
    found = parts(html)
    if not found:
        out.append('no part of the journal is marked data-guide="measured" or "proposed"')
    for kind, ident, body in found:
        cited = re.findall(r'data-excerpt="([^"]+)"', body)
        if kind == "measured":
            if not cited:
                out.append(f"{ident}: marked measured but shows no excerpt (data-excerpt)")
            out += [f"{ident}: excerpt {k!r} is not in data/excerpts.json" for k in cited if k not in keys]
        elif kind == "proposed":
            if cited:
                out.append(f"{ident}: marked proposed but shows code excerpts ({', '.join(cited[:3])}); show the contract instead")
        else:
            out.append(f'{ident}: data-guide="{kind}"; use measured or proposed')
    return out


def main(argv):
    page = Path(argv[0]) if argv else PROJECT.parent / f"{PROJECT.name}-journal" / "index.html"
    keys = set(json.loads((PROJECT / "data" / "excerpts.json").read_text())) if (PROJECT / "data" / "excerpts.json").exists() else set()
    found = problems(page.read_text(), keys)
    for p in found:
        print(f"FAIL guide label {p}")
    if not found:
        print(f"labels: every marked part of {page.name} says measured or proposed, and keeps to it")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
