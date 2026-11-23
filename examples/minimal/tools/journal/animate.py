#!/usr/bin/env python3
"""The journal's animations, kept as scene files and played by FlowScene.

A moving part of the build (a request through the system, a turn of the game
loop, a deploy, a behaviour tree choosing) is drawn in the journal as an
animation, not a still: boxes for the parts, marks that move between them one
step at a time, the words of each step, and the code that runs at it. Each
animation is a scene file in the journal's flows/ folder; this script puts it in
index.html so the page works opened from disk and as a published artifact.

    python3 tools/journal/animate.py [JOURNAL]            put every scene into index.html
    python3 tools/journal/animate.py [JOURNAL] --check    exit 1 if a scene is refused or the page is out of date

JOURNAL defaults to ../<project>-journal/. In an entry, write where the
animation goes:

    <!--FLOW id=request-->
    <!--/FLOW-->

and keep the scene in flows/request.json. The script fills the marker with a
figure: the mount, the scene as inline JSON, a caption saying where its data
came from, and every step as text (an ordered list that reads without
JavaScript and that scripts/journal_check.py can count). The first time a page
has an animation, it also puts the engine and its words between
<!--FLOWSCENE--> and <!--/FLOWSCENE--> before </body>. Edit the scene file, run
this script, never edit the figure by hand.

A scene file is FlowScene's (tools/journal/flowscene/check.py documents every
field) with two more:

    "status": "measured" | "proposed" | "illustrative"
        measured: traced from the code or a run; proposed: a design not built
        yet; illustrative: made up to explain, standing for nothing measured
    "from": where a measured scene's steps came from: the file, command or
        commit (required when measured)

Manim renders are a kit (kits/manim/); use one where the picture itself has to
move (mathematics, shapes that turn into other shapes, many objects).
"""

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "flowscene"))
from check import FlowError, validate  # noqa: E402

STATUS = {"measured": "Measured", "proposed": "Proposed", "illustrative": "Illustrative"}
MARK = re.compile(r"<!--FLOW id=([a-z0-9][a-z0-9-]*)-->.*?<!--/FLOW-->", re.S)
ENGINE = re.compile(r"<!--FLOWSCENE-->.*?<!--/FLOWSCENE-->", re.S)


def journal_dir(arg=None):
    if arg:
        return Path(arg).resolve()
    sys.path.insert(0, str(ROOT / "scripts"))
    from journal_check import setting  # noqa: E402
    brief = ROOT / "BRIEF.md"
    return setting(ROOT, brief.read_text())[1] if brief.exists() else ROOT.parent / f"{ROOT.name}-journal"


def load_scene(where, fid):
    path = where / "flows" / f"{fid}.json"
    if not path.exists():
        raise FlowError(f"the journal places animation {fid} and flows/{fid}.json does not exist")
    scene = json.loads(path.read_text())
    if scene.get("id") != fid:
        raise FlowError(f"flows/{fid}.json: id {scene.get('id')!r} is not the file's name")
    validate(scene, f"flows/{fid}.json")
    status = scene.get("status")
    if status not in STATUS:
        raise FlowError(f"flows/{fid}.json: status {status!r}, not one of {sorted(STATUS)}")
    if status == "measured" and not str(scene.get("from", "")).strip():
        raise FlowError(f"flows/{fid}.json: a measured scene says where its steps came from (\"from\")")
    return scene


def inline_json(data):
    # </script> inside the JSON would end the element early
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def figure(scene):
    fid, esc = scene["id"], html.escape
    source = f" from {esc(scene['from'])}" if scene.get("from") else ""
    flows = []
    for f in scene["flows"]:
        steps = "".join(f"<li>{esc(s['t'])}</li>" for s in f["steps"])
        flows.append(f"<li><b>{esc(f['title'])}.</b> {esc(f['sum'])}<ol>{steps}</ol></li>")
    n = sum(len(f["steps"]) for f in scene["flows"])
    return (f'<!--FLOW id={fid}-->\n'
            f'<div class="flow-fig" role="figure" aria-label="{esc(scene["title"])}" data-status="{scene["status"]}" data-steps="{n}">'
            f'<div data-flow="{fid}"></div>'
            f'<script type="application/json" data-flow-scene="{fid}">{inline_json(scene)}</script>'
            f'<p class="flow-cap"><b>{esc(scene["title"])}.</b> <span class="flow-status">{STATUS[scene["status"]]}</span>{source}.</p>'
            f'<details class="flow-steps"><summary>Every step as text</summary><ol>{"".join(flows)}</ol></details>'
            f'</div>\n<!--/FLOW-->')


# The figure's own look. It is a div with role="figure", not a <figure>, so a journal
# page's picture viewer, which opens any <figure>'s button full-window, leaves the
# engine's buttons alone. The step list in <details> is for a reader without
# JavaScript; once the engine has drawn its own, it is hidden.
FIG_CSS = """.flow-fig { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 12px; margin: 12px 0; }
.flow-fig .flow-cap { font-size: 14px; color: var(--muted); margin: 8px 0 0; }
.flow-fig .flow-status { font-family: var(--mono, monospace); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--fg); }
.flow-fig:has([data-ready="true"]) .flow-steps { display: none; }
"""


def engine_block():
    fs = HERE / "flowscene"
    return ("<!--FLOWSCENE-->\n"
            f"<style>\n{FIG_CSS}{(fs / 'engine.css').read_text()}</style>\n"
            f'<script type="application/json" id="flow-labels">{inline_json(json.loads((fs / "labels.json").read_text()))}</script>\n'
            f"<script>\n{(fs / 'engine.js').read_text()}</script>\n"
            "<!--/FLOWSCENE-->")


def render(page, where):
    """The page with every animation filled from its scene file. Raises FlowError."""
    ids = MARK.findall(page)
    scenes = {fid: load_scene(where, fid) for fid in dict.fromkeys(ids)}
    page = MARK.sub(lambda m: figure(scenes[m.group(1)]), page)
    if ids:
        block = engine_block()
        if ENGINE.search(page):
            page = ENGINE.sub(lambda m: block, page)
        elif "</body>" in page:
            page = page.replace("</body>", block + "\n</body>", 1)
        else:   # a page that leaves </body> implicit: the engine goes at the end
            page = page.rstrip("\n") + "\n" + block + "\n"
    return page


def problems(where):
    index = where / "index.html"
    if not index.exists():
        return []
    page = index.read_text()
    try:
        fresh = render(page, where)
    except (FlowError, KeyError, TypeError, ValueError) as e:
        return [f"animation: {e}"]
    out = []
    if fresh != page:
        out.append("the animations are out of date with flows/: run python3 tools/journal/animate.py")
    placed = set(MARK.findall(page))
    for p in sorted((where / "flows").glob("*.json")) if (where / "flows").is_dir() else []:
        if p.stem not in placed:
            out.append(f"flows/{p.name} is placed in no entry: add <!--FLOW id={p.stem}--><!--/FLOW--> where it belongs")
    return out


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    where = journal_dir(args[0] if args else None)
    index = where / "index.html"
    if "--check" in argv:
        bad = problems(where)
        for b in bad:
            print(f"FAIL {b}")
        if not bad:
            print(f"animations: {len(set(MARK.findall(index.read_text()))) if index.exists() else 0} in place")
        return 1 if bad else 0
    try:
        page = render(index.read_text(), where)
    except (FlowError, KeyError, TypeError, ValueError) as e:
        print(f"FAIL animation: {e}")
        return 1
    index.write_text(page)
    print(f"animations: {len(set(MARK.findall(page)))} placed in {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
