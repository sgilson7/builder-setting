#!/usr/bin/env python3
"""Copy the site that tools/manim/sitepages.py writes into a clone of the repository that serves it.

    python3 tools/manim/publish.py ../my-site          copy, then say what changed
    python3 tools/manim/publish.py ../my-site --check  fail if the clone differs

From Manim Lab's CSC 226 site, served by GitHub Pages from a repository that holds
only the built files. This script copies files and nothing else: the commit and the
push are the person's to approve (a deploy happens only on the person's word).

What is copied is named here: the pages sitepages.py writes (from the generator, not from
disk, so a page edited by hand is not published), the player, slide and page scripts
and styles, the fonts with their licences, the scene files and their rendered media.
Each scene file is copied with only the fields the player reads (SCENE_KEEP). Its
"source", "summary" and "code" stay behind: a source line can name files the reader
should not see (Manim Lab T6 found course file names published this way), and the
summary is already on the scene's page. Files in the clone the site lacks are removed,
except .git and .nojekyll, which this script writes so GitHub Pages serves the files
as they are.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sitepages as sitegen  # noqa: E402

SCENE_KEEP = ("id", "title", "width", "height", "steps")
SHARED = ("manim/theme.css", "manim/player.css", "manim/player.js", "manim/deck.js", "manim/deck.css",
          "manim/page.js", "manim/page.css", "fonts/PublicSans-wght.ttf", "fonts/JetBrainsMono-wght.ttf",
          "fonts/PublicSans-OFL.txt", "fonts/JetBrainsMono-OFL.txt")


def content(config=sitegen.CONFIG):
    """Every published file, by its path in the serving repository, as bytes."""
    site, scenes = sitegen.load(config)
    base = sitegen.ROOT / site["root"]
    want = {k: v.encode() for k, v in sitegen.pages(site, scenes).items()}
    for name in SHARED:
        want[name] = (base / name).read_bytes()
    for sid, scene in scenes.items():
        kept = {k: scene[k] for k in SCENE_KEEP}
        want[f"scenes/{sid}.json"] = (json.dumps(kept, indent=1, ensure_ascii=False) + "\n").encode()
        for p in sorted((base / "media" / sid).rglob("*")):
            if p.is_file():
                want[p.relative_to(base).as_posix()] = p.read_bytes()
    want[".nojekyll"] = b""
    return want


def main(argv):
    if not argv or argv[0].startswith("-"):
        raise SystemExit(__doc__)
    dest = Path(argv[0]).resolve()
    if not (dest / ".git").is_dir():
        raise SystemExit(f"{dest} is not a git clone")
    want = content()
    have = {p.relative_to(dest).as_posix() for p in dest.rglob("*")
            if p.is_file() and p.relative_to(dest).parts[0] != ".git"}
    changed = [k for k, v in want.items() if not (dest / k).is_file() or (dest / k).read_bytes() != v]
    extra = sorted(have - set(want))
    if "--check" in argv:
        if changed or extra:
            raise SystemExit(f"publish: {len(changed)} files differ, {len(extra)} extra: {(changed + extra)[:5]}")
        print(f"publish current: {len(want)} files")
        return
    for k in changed:
        (dest / k).parent.mkdir(parents=True, exist_ok=True)
        (dest / k).write_bytes(want[k])
    for k in extra:
        (dest / k).unlink()
    for d in sorted((p for p in dest.rglob("*") if p.is_dir() and ".git" not in p.parts), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    print(json.dumps({"files": len(want), "changed": len(changed), "removed": len(extra),
                      "bytes": sum(len(v) for v in want.values())}))


if __name__ == "__main__":
    main(sys.argv[1:])
