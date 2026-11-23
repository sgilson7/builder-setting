#!/usr/bin/env python3
"""Check FlowScene scene files (deck/flows/*.json) before a page plays them. Stdlib only.

    python3 tools/flowscene/check.py              every scene in deck/flows/
    python3 tools/flowscene/check.py FILE.json    the files named

FlowScene draws whatever it is given and fails quietly: a mark sent to a node that
does not exist stops the animation, a highlight outside its excerpt lights nothing,
and a mark between two boxes with no line drawn between them crosses empty space.
This refuses each of those before the page is opened.

A scene file:

    {"id": "...",                         the file's name
     "title": "...",                      the picture's accessible name
     "viewBox": "0 0 W H",
     "nodes": {"id": [x, y, "label\\nsecond line", "kind"]},   kind optional
     "zones": [{"x", "y", "w", "h", "label", "tone": "a"|"b"|"c"|"d"}],
     "edges": [["a", "b"], ["a", "b", true]],                   true draws it dashed
     "via": {"a>b": [[x, y], ...]},       bends for the edge a-b
     "flows": [{"id", "title", "sum",
                "steps": [{"t": "words",
                           "go": [{"path": ["a", "b", ...], "kind": "req"|"res"|"stream"|"msg"}],
                           "work": ["node", ...],   lit without a mark
                           "c": "excerpt key", "hl": [first, last] or [[first, last], ...],
                           "x": {"h": "heading", "body": "a proposed contract"}}]}],
     "start": "flow id",                  optional
     "code": {"key": {"file", "first", "lines": ["...", ...]}}}   optional

Every coordinate is an integer. Excerpts here are copied text; a project that shows
code from a codebase it explains should also check them against it (kits/codebase-guide).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOWS = ROOT / "deck" / "flows"
NODE_KINDS = {"svc", "client", "store", "ext", "mod", "bus", "new", "chg"}
MARK_KINDS = {"req", "res", "stream", "msg"}
TONES = {"a", "b", "c", "d"}


class FlowError(ValueError):
    pass


def _int(v, where):
    if isinstance(v, bool) or not isinstance(v, int):
        raise FlowError(f"{where}: {v!r} is not an integer")


def _words(v, where):
    if not isinstance(v, str) or not v.strip():
        raise FlowError(f"{where}: needs words")


def validate(scene, name="scene"):
    for k in ("id", "title", "viewBox", "nodes", "edges", "flows"):
        if k not in scene:
            raise FlowError(f"{name}: no {k}")
    vb = scene["viewBox"].split()
    if len(vb) != 4 or not all(p.lstrip("-").isdigit() for p in vb):
        raise FlowError(f"{name}: viewBox {scene['viewBox']!r} is not four integers")
    nodes = scene["nodes"]
    for nid, n in nodes.items():
        if not (isinstance(n, list) and len(n) in (3, 4)):
            raise FlowError(f"{name}: node {nid} is not [x, y, label] or [x, y, label, kind]")
        _int(n[0], f"{name}: node {nid} x")
        _int(n[1], f"{name}: node {nid} y")
        _words(n[2], f"{name}: node {nid} label")
        if len(n) == 4 and n[3] not in NODE_KINDS:
            raise FlowError(f"{name}: node {nid} has kind {n[3]!r}, not one of {sorted(NODE_KINDS)}")
    for i, z in enumerate(scene.get("zones", [])):
        for k in ("x", "y", "w", "h"):
            _int(z.get(k), f"{name}: zone {i + 1} {k}")
        _words(z.get("label"), f"{name}: zone {i + 1} label")
        if z.get("tone", "a") not in TONES:
            raise FlowError(f"{name}: zone {i + 1} tone {z['tone']!r}")
    drawn = set()
    for e in scene["edges"]:
        for nid in e[:2]:
            if nid not in nodes:
                raise FlowError(f"{name}: edge {e[0]}-{e[1]} names node {nid}, which the scene lacks")
        drawn |= {(e[0], e[1]), (e[1], e[0])}
    for key, pts in scene.get("via", {}).items():
        a, _, b = key.partition(">")
        if (a, b) not in drawn:
            raise FlowError(f"{name}: via {key} bends an edge the scene does not draw")
        for p in pts:
            _int(p[0], f"{name}: via {key}")
            _int(p[1], f"{name}: via {key}")
    code = scene.get("code") or {}
    for key, c in code.items():
        _int(c.get("first"), f"{name}: excerpt {key} first")
        if not c.get("file") or not isinstance(c.get("lines"), list):
            raise FlowError(f"{name}: excerpt {key} needs file and lines")
    flow_ids = [f.get("id") for f in scene["flows"]]
    if not flow_ids or len(set(flow_ids)) != len(flow_ids):
        raise FlowError(f"{name}: flow ids must be present and different {flow_ids}")
    if "start" in scene and scene["start"] not in flow_ids:
        raise FlowError(f"{name}: start {scene['start']!r} is not a flow")
    for f in scene["flows"]:
        _words(f.get("title"), f"{name}: flow {f['id']} title")
        _words(f.get("sum"), f"{name}: flow {f['id']} sum")
        if not f.get("steps"):
            raise FlowError(f"{name}: flow {f['id']} has no steps")
        for i, s in enumerate(f["steps"]):
            where = f"{name}: flow {f['id']} step {i + 1}"
            _words(s.get("t"), where)
            for m in s.get("go", []):
                if m.get("kind") not in MARK_KINDS:
                    raise FlowError(f"{where}: mark kind {m.get('kind')!r}, not one of {sorted(MARK_KINDS)}")
                path = m.get("path", [])
                if len(path) < 2:
                    raise FlowError(f"{where}: a mark's path needs two nodes or more")
                for nid in path:
                    if nid not in nodes:
                        raise FlowError(f"{where}: path names node {nid}, which the scene lacks")
                for a, b in zip(path, path[1:]):
                    if (a, b) not in drawn:
                        raise FlowError(f"{where}: a mark goes {a} to {b}, and no edge is drawn between them")
            for nid in s.get("work", []):
                if nid not in nodes:
                    raise FlowError(f"{where}: lights node {nid}, which the scene lacks")
            if "c" in s:
                if s["c"] not in code:
                    raise FlowError(f"{where}: shows excerpt {s['c']!r}, which the scene lacks")
                c = code[s["c"]]
                last = c["first"] + len(c["lines"]) - 1
                hl = s.get("hl", [])
                for a, b in ([hl] if hl and isinstance(hl[0], int) else hl):
                    if not (c["first"] <= a <= b <= last):
                        raise FlowError(f"{where}: highlights lines {a}-{b}; {s['c']} holds {c['first']}-{last}")
            if "x" in s:
                _words(s["x"].get("h"), f"{where}: contract heading")
                _words(s["x"].get("body"), f"{where}: contract body")
    return scene


def load(path):
    path = Path(path)
    scene = json.loads(path.read_text())
    if scene.get("id") != path.stem:
        raise FlowError(f"{path.name}: id {scene.get('id')!r} is not the file's name")
    return validate(scene, path.name)


def main(argv):
    files = [Path(a) for a in argv] or sorted(FLOWS.glob("*.json"))
    bad = 0
    for p in files:
        try:
            load(p)
        except (FlowError, KeyError, TypeError, ValueError) as e:
            bad += 1
            print(f"FAIL {e}")
    if bad:
        raise SystemExit(f"{bad} of {len(files)} scene files refused")
    print(f"{len(files)} scene files checked")


if __name__ == "__main__":
    main(sys.argv[1:])
