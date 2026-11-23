#!/usr/bin/env python3
"""Code excerpts from the codebase this project explains, each checked against it.

Every excerpt the guide shows is a row in data/excerpts.json:

    "submit": ["client/app/api.service.ts", 1713, 1717, "postSubmission(submissionForm)"]

that is: the file (relative to the codebase), its first and last line, and text
the first line must contain. When the codebase changes and the function moves,
the check fails and says where that text is now, so a page never shows the
wrong lines. The codebase is named in notes/target (one line, a path), the same
file scripts/target_unchanged.py reads.

    python3 tools/guide/excerpts.py              check every excerpt
    python3 tools/guide/excerpts.py KEY          print one excerpt with its line numbers
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def target(project=PROJECT):
    f = project / "notes" / "target"
    if not f.exists():
        raise SystemExit("FAIL notes/target is missing: write the path of the codebase this guide explains")
    p = Path(f.read_text().strip()).expanduser()
    return (p if p.is_absolute() else project / p).resolve()


def table(project=PROJECT):
    return json.loads((project / "data" / "excerpts.json").read_text())


def excerpt(key, project=PROJECT):
    """{file, first, lines} for one excerpt, read from the codebase now."""
    rel, first, last, _ = table(project)[key]
    lines = (target(project) / rel).read_text(errors="replace").splitlines()
    return {"file": rel, "first": first, "lines": lines[first - 1:last]}


def problems(project=PROJECT):
    out = []
    base = target(project)
    for key, row in table(project).items():
        if not (isinstance(row, list) and len(row) == 4):
            out.append(f"{key}: a row is [file, first line, last line, text the first line contains]")
            continue
        rel, first, last, must = row
        path = base / rel
        if not path.is_file():
            out.append(f"{key}: {rel} is not in the codebase")
            continue
        lines = path.read_text(errors="replace").splitlines()
        if not (1 <= first <= last <= len(lines)):
            out.append(f"{key}: lines {first}-{last} are outside {rel} ({len(lines)} lines)")
            continue
        if must not in lines[first - 1]:
            now = [i + 1 for i, line in enumerate(lines) if must in line]
            where = f"; that text is now at line {', '.join(map(str, now[:3]))}" if now else "; that text is no longer in the file"
            out.append(f"{key}: line {first} of {rel} no longer contains {must!r}{where}")
    return out


def main(argv):
    if argv:
        e = excerpt(argv[0])
        for i, line in enumerate(e["lines"]):
            print(f"{e['first'] + i:>5}  {line}")
        return 0
    found = problems()
    for p in found:
        print(f"FAIL excerpt {p}")
    if not found:
        print(f"excerpts: {len(table())} excerpts in place in {target()}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
