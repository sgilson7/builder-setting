#!/usr/bin/env python3
"""Check that the codebase this project explains is exactly as it was when reading began.

A guide reads its codebase and never changes it. This hashes every file under
the codebase named in notes/target and compares the list with
notes/target.sha256, written once before any reading. A file added, removed or
edited fails, and so do the quiet changes: node_modules/ from an install, a
build's output, or a .git/ from git init.

    python3 scripts/target_unchanged.py            check
    python3 scripts/target_unchanged.py --write    write the manifest, once
"""

import hashlib
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT / "notes" / "target.sha256"


def target(project=PROJECT):
    f = project / "notes" / "target"
    if not f.exists():
        return None
    p = Path(f.read_text().strip()).expanduser()
    return (p if p.is_absolute() else project / p).resolve()


def digest(root):
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            out[rel] = "link:" + str(p.readlink())
        elif p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main(argv, project=PROJECT):
    root, manifest = target(project), project / "notes" / "target.sha256"
    if not root or not root.is_dir():
        print("FAIL the codebase in notes/target is missing")
        return 1
    now = digest(root)
    if "--write" in argv:
        if manifest.exists():
            print(f"FAIL {manifest.name} exists; it is written once, before reading begins")
            return 1
        manifest.write_text("".join(f"{sha}  {rel}\n" for rel, sha in now.items()))
        print(f"wrote {manifest.name}: {len(now)} files")
        return 0
    if not manifest.exists():
        print("FAIL notes/target.sha256 is missing: run python3 scripts/target_unchanged.py --write before reading")
        return 1
    then = dict(reversed(line.split("  ", 1)) for line in manifest.read_text().splitlines())
    added = sorted(set(now) - set(then))
    removed = sorted(set(then) - set(now))
    edited = sorted(r for r in set(now) & set(then) if now[r] != then[r])
    for label, rows in (("added", added), ("removed", removed), ("edited", edited)):
        for r in rows[:20]:
            print(f"FAIL the codebase changed: {label} {r}")
    if added or removed or edited:
        return 1
    print(f"codebase unchanged: {len(now)} files match notes/target.sha256")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
