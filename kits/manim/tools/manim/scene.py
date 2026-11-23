#!/usr/bin/env python3
"""The scene file: one JSON file per animation, deck/scenes/<id>.json, read by the
renderer (render.py, under Manim) and by the checks (plain python3, stdlib only).

    python3 tools/manim/scene.py deck/scenes/*.json     validate, print each hash

Every number in a scene file is an integer: pixels in the scene's own units (the
original SVG's viewBox) and milliseconds (Manim Lab MN-Q1, so a Rust core could write it).

    {"id": "sample-flow",                    same as the file name
     "title": "...",                         the picture's accessible name
     "summary": "...",                       one sentence shown above the player
     "source": "...",                        what it was rebuilt from
     "width": 900, "height": 230,            the viewBox
     "fade_ms": 300,                         how long lighting and dimming take
     "ease": [400, 100, 300, 1000],          cubic-bezier of every move, in thousandths
     "token_r": 10,                          radius of the step token, if steps use one
     "zones": [{"x", "y", "w", "h", "label", "tone": "a".."d"}],
     "nodes": {"<id>": {"x", "y", "w", "h", "r", "kind", "lines", "leading", "dy", "from"}},
         x, y is the box's centre; r its corner radius; kind is svc, client, store
         or ext (store draws a heavier border, ext a dashed one); lines is a list of
         [style, text] with style a key of theme.json's "text", centred on x, with
         baselines `leading` apart, the middle one at y + dy (SVG's text-anchor
         middle); from is the step (0-based) at which the node stops being dimmed.
     "edges": [{"a", "b", "dashed", "from"}],   drawn border to border
     "labels": [{"x", "y", "text", "style", "from"}],   free text, starting at x, baseline y
     "dots": [{"x", "y", "r", "tone", "from"}],
     "steps": [{"t": "words", "light": [node ids], "go": [{"path": [ids], "kind"}],
                "token": {"x", "y", "bug"}, "move_ms", "hold_ms"}]}

A step's clip lasts move_ms. move_ms is at least fade_ms and a whole number of
frames at theme.json's fps. hold_ms is how long Play waits after the clip.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "data" / "manim" / "theme.json"
KINDS = {"req", "res", "stream", "msg"}
NODE_KINDS = {"svc", "client", "store", "ext"}
TONES = {"a", "b", "c", "d"}
DOT_TONES = {"bad", "ok", "req", "accent"}


class SceneError(ValueError):
    pass


def canonical(obj):
    """The bytes a hash is taken over: sorted keys, no spaces, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def scene_hash(scene):
    return sha256(canonical(scene))


def load_theme(path=THEME):
    return json.loads(Path(path).read_text())


def frame_ms(theme):
    fps = theme["render"]["fps"]
    if 1000 % fps:
        raise SceneError(f"theme fps {fps} does not divide a second into whole milliseconds")
    return 1000 // fps


def _ints(value, where):
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        raise SceneError(f"{where} is {value}: scene files hold integers only")
    if isinstance(value, dict):
        for k, v in value.items():
            _ints(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _ints(v, f"{where}[{i}]")


def _need(obj, keys, where):
    for k in keys:
        if k not in obj:
            raise SceneError(f"{where} has no {k}")


def validate(scene, theme=None, name=None):
    """Raise SceneError naming the first fault; return the scene unchanged."""
    theme = theme or load_theme()
    _ints(scene, scene.get("id", "scene"))
    if "code" in scene:
        return _validate_code(scene, theme, name)
    _need(scene, ["id", "title", "summary", "source", "width", "height", "fade_ms", "ease", "nodes", "steps"], "the scene")
    if name is not None and scene["id"] != name:
        raise SceneError(f"the scene's id {scene['id']!r} is not its file name {name!r}")
    if scene["width"] <= 0 or scene["height"] <= 0:
        raise SceneError("the scene's width and height must be positive")
    if len(scene["ease"]) != 4:
        raise SceneError("ease needs four numbers")
    styles = theme["text"]
    nodes = scene["nodes"]
    steps = scene["steps"]
    last = len(steps) - 1
    if not steps:
        raise SceneError("the scene has no steps")

    def known(nid, where):
        if nid not in nodes:
            raise SceneError(f"{where} names the node {nid!r}, which the scene does not have")

    def when(obj, where):
        f = obj.get("from", 0)
        if not 0 <= f <= last:
            raise SceneError(f"{where} appears at step {f}, outside 0 to {last}")

    for z in scene.get("zones", []):
        _need(z, ["x", "y", "w", "h", "label", "tone"], "a zone")
        if z["tone"] not in TONES:
            raise SceneError(f"zone {z['label']!r} has tone {z['tone']!r}")
    for nid, n in nodes.items():
        where = f"node {nid}"
        _need(n, ["x", "y", "w", "h", "r", "kind", "lines", "leading", "dy"], where)
        if n["kind"] not in NODE_KINDS:
            raise SceneError(f"{where} has kind {n['kind']!r}")
        if not n["lines"]:
            raise SceneError(f"{where} has no words")
        for style, text in n["lines"]:
            if style not in styles:
                raise SceneError(f"{where} uses the text style {style!r}, which theme.json does not define")
            if not text.strip():
                raise SceneError(f"{where} has an empty line")
        when(n, where)
    for e in scene.get("edges", []):
        _need(e, ["a", "b"], "an edge")
        known(e["a"], "an edge")
        known(e["b"], "an edge")
        when(e, f"edge {e['a']}-{e['b']}")
    for lab in scene.get("labels", []):
        _need(lab, ["x", "y", "text", "style"], "a label")
        if lab["style"] not in styles:
            raise SceneError(f"label {lab['text']!r} uses the text style {lab['style']!r}")
        when(lab, f"label {lab['text']!r}")
    for d in scene.get("dots", []):
        _need(d, ["x", "y", "r", "tone"], "a dot")
        if d["tone"] not in DOT_TONES:
            raise SceneError(f"a dot has tone {d['tone']!r}")
        when(d, "a dot")
    fm = frame_ms(theme)
    for i, s in enumerate(steps):
        where = f"step {i + 1}"
        _need(s, ["t", "move_ms", "hold_ms"], where)
        if not s["t"].strip():
            raise SceneError(f"{where} has no words")
        if s["move_ms"] < scene["fade_ms"]:
            raise SceneError(f"{where} moves for {s['move_ms']} ms, less than fade_ms {scene['fade_ms']}")
        if s["move_ms"] % fm:
            raise SceneError(f"{where} moves for {s['move_ms']} ms, not a whole number of {fm} ms frames")
        if s["hold_ms"] < 0:
            raise SceneError(f"{where} holds for a negative time")
        for nid in s.get("light", []):
            known(nid, where)
        for m in s.get("go", []):
            if m.get("kind") not in KINDS:
                raise SceneError(f"{where} moves a mark of kind {m.get('kind')!r}")
            if len(m.get("path", [])) < 2:
                raise SceneError(f"{where} moves a mark along fewer than two nodes")
            for nid in m["path"]:
                known(nid, where)
        if "token" in s:
            _need(s["token"], ["x", "y"], f"{where}'s token")
            if "token_r" not in scene:
                raise SceneError(f"{where} has a token but the scene has no token_r")
    return scene


def _validate_code(scene, theme, name):
    """A code scene: Manim code in scene["code"] draws it (tools/manim/stepscene.py);
    the file gives the words and the times the player and the checks need."""
    _need(scene, ["id", "title", "summary", "source", "width", "height", "code", "steps"], "the scene")
    if name is not None and scene["id"] != name:
        raise SceneError(f"the scene's id {scene['id']!r} is not its file name {name!r}")
    if scene["width"] <= 0 or scene["height"] <= 0:
        raise SceneError("the scene's width and height must be positive")
    if not (ROOT / scene["code"]).is_file():
        raise SceneError(f"the scene's code {scene['code']} does not exist")
    if not scene["steps"]:
        raise SceneError("the scene has no steps")
    fm = frame_ms(theme)
    for i, s in enumerate(scene["steps"]):
        where = f"step {i + 1}"
        _need(s, ["t", "move_ms", "hold_ms"], where)
        if not s["t"].strip():
            raise SceneError(f"{where} has no words")
        if s["move_ms"] <= 0 or s["move_ms"] % fm:
            raise SceneError(f"{where} moves for {s['move_ms']} ms, not a positive whole number of {fm} ms frames")
        if s["hold_ms"] < 0:
            raise SceneError(f"{where} holds for a negative time")
    return scene


def load(path, theme=None):
    """A validated scene; a code scene also carries its code's hash, so editing the
    code makes its render stale."""
    path = Path(path)
    scene = validate(json.loads(path.read_text()), theme, name=path.stem)
    if "code" in scene:
        scene["code_sha256"] = sha256((ROOT / scene["code"]).read_bytes())
    return scene


def main(paths):
    if not paths:
        paths = sorted(str(p) for p in (ROOT / "deck" / "scenes").glob("*.json"))
    bad = 0
    for p in paths:
        try:
            s = load(p)
            print(f"ok   {p}: {len(s['steps'])} steps, {scene_hash(s)[:12]}")
        except (SceneError, ValueError, KeyError) as e:
            print(f"FAIL {p}: {e}")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
