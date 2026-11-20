#!/usr/bin/env python3
"""Draw one scene file with Manim Community, one section per step, in one theme.

    .venv-manim/bin/python tools/manim/render.py deck/scenes/ID.json light|dark OUTDIR

Writes OUTDIR/sections/*.mp4 (Manim's own section clips, not yet remuxed) and
OUTDIR/step-NN.png, the last frame of each step. scripts/render.sh calls this and
does the rest (remux, manifest). Every colour, size and stroke comes from
data/manim/theme.json; every position and time from the scene file. The one number
of its own is where a zone's label sits, after engine.js line 89.

Step n's clip starts where step n-1 ended (step 1's from the bare scene): pieces
whose `from` is later than the step are dimmed; the step's `light` nodes fade to
the lit colours over fade_ms; the previous step's marks vanish and this step's
move along their paths for move_ms (engine.js clears them the same way); the
token, if the step has one, moves from where it was, or fades in.
"""
import importlib.util
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import geometry  # noqa: E402
import scene as scenefile  # noqa: E402
from stepscene import TEX, ExactFrames  # noqa: E402

import manimpango  # noqa: E402
from manim import (  # noqa: E402
    AnimationGroup, Circle, DashedVMobject, Line, Polygon, RoundedRectangle, Scene,
    Square, Text, UpdateFromAlphaFunc, VGroup, VMobject, Wait, rate_functions, tempconfig,
)
from manim.constants import BOLD, NORMAL, SEMIBOLD  # noqa: E402

ZONE_LABEL_DX, ZONE_LABEL_DY = 12, 20      # engine.js line 89
MARK = 7                                   # engine.js markShape() default size
PX = 100                                   # Manim stroke_width per scene pixel
EM = 72                                    # Manim font_size per scene pixel of em
SET_AT = 48                                # Pango sets text at this size, then it is scaled:
                                           # at EM x px it wraps lines at its 600 px layout width
# Layers, bottom to top, in engine.js's order (lines 85-86): zones, edges, live paths,
# nodes, marks; MerryQuery draws its token last (merryquery-deck.html line 300).
LAYER = {"zone": 0, "edge": 1, "live": 2, "node": 3, "mark": 4, "token": 5}
WEIGHTS = {"normal": NORMAL, "semibold": SEMIBOLD, "bold": BOLD}
DESCENDS = set("gjpqy,;()[]{}/_|@$Q")


class Drawn:
    """One scene file's mobjects in Manim coordinates (1 unit = 1 scene pixel)."""

    def __init__(self, scene, theme, mode):
        self.s, self.t, self.c = scene, theme, theme[mode]
        self.W, self.H = scene["width"], scene["height"]

    def p(self, x, y):
        return [x - self.W / 2, self.H / 2 - y, 0]

    def col(self, key):
        v = self.c[key]
        return v[0] if isinstance(v, list) else v

    def stroke(self, key):
        return self.t["stroke"][key] * PX

    def text(self, words, style, x, y, anchor):
        st = self.t["text"][style]
        font = self.t["fonts"][st["font"]]["family"]
        if st.get("upper"):
            words = words.upper()
        m = Text(words, font=font, font_size=SET_AT, weight=WEIGHTS[st["weight"]],
                 color=self.col(st["colour"]))
        m.scale(st["px"] * EM / SET_AT)
        chars = [g for g, ch in zip(m.submobjects, words.replace(" ", "")) if ch not in DESCENDS]
        base = min(g.get_bottom()[1] for g in (chars or m.submobjects))
        target = self.p(x, y)
        m.shift([0, target[1] - base, 0])
        if anchor == "middle":
            m.set_x(target[0])
        else:
            m.shift([target[0] - m.get_left()[0], 0, 0])
        return m

    def dashed(self, mob, dash, gap):
        n = max(2, round(mob_length(mob) / (dash + gap)))
        return DashedVMobject(mob, num_dashes=n, dashed_ratio=dash / (dash + gap))

    def zone(self, z):
        fill, alpha = self.c["zone_" + z["tone"]]
        r = RoundedRectangle(width=z["w"], height=z["h"], corner_radius=14,
                             fill_color=fill, fill_opacity=alpha / 100, stroke_width=0)
        r.move_to(self.p(z["x"] + z["w"] / 2, z["y"] + z["h"] / 2))
        edge = RoundedRectangle(width=z["w"], height=z["h"], corner_radius=14,
                                stroke_color=self.col("line"), stroke_width=self.stroke("zone"))
        edge.move_to(r)
        label = self.text(z["label"], "zone", z["x"] + ZONE_LABEL_DX, z["y"] + ZONE_LABEL_DY, "start")
        return VGroup(r, self.dashed(edge, 4, 4), label).set_z_index(LAYER["zone"])

    def box(self, nid, lit):
        n = self.s["nodes"][nid]
        width = "lit" if lit else ("store" if n["kind"] == "store" else "box")
        r = RoundedRectangle(width=n["w"], height=n["h"], corner_radius=n["r"],
                             fill_color=self.col("lit" if lit else "panel"), fill_opacity=1,
                             stroke_color=self.col("lit_line" if lit else "muted"),
                             stroke_width=self.stroke(width))
        r.move_to(self.p(n["x"], n["y"]))
        if n["kind"] == "ext" and not lit:
            fill = r.copy().set_stroke(width=0)
            return VGroup(fill, self.dashed(r.copy().set_fill(opacity=0), 5, 3))
        return VGroup(r)

    def node(self, nid, lit, dimmed, later):
        g = VGroup(self.box(nid, lit), self.words(nid)).set_z_index(LAYER["node"])
        return g.set_opacity(later) if dimmed else g

    def words(self, nid):
        n = self.s["nodes"][nid]
        k = len(n["lines"])
        return VGroup(*[self.text(w, style, n["x"], n["y"] + n["dy"] + (i - (k - 1) / 2) * n["leading"], "middle")
                        for i, (style, w) in enumerate(n["lines"])])

    def edge(self, e):
        a, b = geometry.segment(self.s["nodes"], e["a"], e["b"])
        line = Line(self.p(*a), self.p(*b), stroke_color=self.col("line"), stroke_width=self.stroke("edge"))
        return (self.dashed(line, 5, 4) if e.get("dashed") else line).set_z_index(LAYER["edge"])

    def live(self, m):
        pts = geometry.polyline(self.s["nodes"], m["path"])
        v = VMobject(stroke_color=self.col(m["kind"]), stroke_width=self.stroke("live"),
                     stroke_opacity=self.t["opacity"]["live"] / 100)
        v.set_points_as_corners([self.p(*q) for q in pts])
        if m["kind"] == "stream":
            v = self.dashed(v, 8, 5)
        elif m["kind"] == "msg":
            v = self.dashed(v, 2, 4)
        return v.set_z_index(LAYER["live"]), pts

    def mark(self, kind):
        s = MARK
        if kind == "res":
            m = Square(side_length=2 * s)
        elif kind == "stream":
            m = Polygon([0, s + 2, 0], [s + 2, 0, 0], [0, -s - 2, 0], [-s - 2, 0, 0])
        elif kind == "msg":
            m = Polygon([0, s + 2, 0], [s + 2, -s, 0], [-s - 2, -s, 0])
        else:
            m = Circle(radius=s)
        return (m.set_fill(self.col(kind), 1).set_stroke(self.col("panel"), self.stroke("mark"))
                .set_z_index(LAYER["mark"]))

    def dot(self, d):
        return Circle(radius=d["r"], fill_color=self.col(d["tone"]), fill_opacity=1,
                      stroke_width=0).move_to(self.p(d["x"], d["y"])).set_z_index(LAYER["node"])

    def token(self, tok):
        return Circle(radius=self.s["token_r"], fill_color=self.col("bad" if tok.get("bug") else "req"),
                      fill_opacity=1, stroke_width=0).move_to(self.p(tok["x"], tok["y"])).set_z_index(LAYER["token"])


def mob_length(mob):
    pts = mob.points
    total = 0.0
    for i in range(0, len(pts) - 3, 4):
        a, b = pts[i], pts[i + 3]
        total += ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
    return total


def dim(i, piece):
    return piece.get("from", 0) > i


class FromSceneFile(ExactFrames, Scene):
    # ExactFrames: Manim's own np.arange(0, run_time, 1/fps) gives 57 frames for 1.12 s at 50 fps.
    scene_data = theme_data = mode = out = None

    def construct(self):
        s, theme = self.scene_data, self.theme_data
        d = Drawn(s, theme, self.mode)
        later = theme["opacity"]["later"] / 100
        fade = s["fade_ms"] / 1000
        ease = geometry.cubic_bezier(*[v / 1000 for v in s["ease"]])

        def shown(mob, is_dim):
            return mob.set_opacity(later) if is_dim else mob

        for z in s.get("zones", []):
            self.add(d.zone(z))
        edges = [(e, d.edge(e)) for e in s.get("edges", [])]
        nodes = {nid: d.node(nid, False, dim(0, s["nodes"][nid]), later) for nid in s["nodes"]}
        dots = [(x, d.dot(x)) for x in s.get("dots", [])]
        labels = [(x, d.text(x["text"], x["style"], x["x"], x["y"], "start").set_z_index(LAYER["node"]))
                  for x in s.get("labels", [])]
        # Before step 1: nothing lit, later pieces dimmed.
        for piece, mob in edges + dots + labels:
            self.add(shown(mob, dim(0, piece)))
        self.add(*nodes.values())
        lit_before, live, marks, token = set(), [], [], None
        prev = -1
        for i, step in enumerate(s["steps"]):
            self.next_section(f"step-{i + 1:02d}")
            anims = []
            # pieces that stop being dimmed at this step
            for piece, mob in edges + dots + labels:
                if dim(prev if prev >= 0 else 0, piece) and not dim(i, piece):
                    anims.append(mob.animate(run_time=fade).set_opacity(1))
            lit_now = set(step.get("light", []))
            for nid, mob in nodes.items():
                n = s["nodes"][nid]
                was_dim = dim(prev if prev >= 0 else 0, n)
                now_dim = dim(i, n)
                if (nid in lit_now) != (nid in lit_before) or was_dim != now_dim:
                    target = d.node(nid, nid in lit_now, now_dim, later)
                    anims.append(mob.animate(run_time=fade).become(target))
            # the previous step's marks go; this step's appear at their starts
            self.remove(*live, *marks)
            live, marks = [], []
            for m in step.get("go", []):
                line, pts = d.live(m)
                mark = d.mark(m["kind"]).move_to(d.p(*pts[0]))
                live.append(line)
                marks.append(mark)
                self.add(line)
                self.add(mark)

                def follow(mob, alpha, pts=pts):
                    mob.move_to(d.p(*geometry.at(pts, ease(alpha))))
                anims.append(UpdateFromAlphaFunc(mark, follow, run_time=step["move_ms"] / 1000,
                                                 rate_func=rate_functions.linear))
            if "token" in step:
                new = d.token(step["token"])
                if token is None:
                    new.set_opacity(0)
                    self.add(new)
                    anims.append(new.animate(run_time=fade).set_opacity(1))
                    token = new
                else:
                    token.set_fill(new.get_fill_color())
                    start, end = token.get_center(), new.get_center()

                    def glide(mob, alpha, start=start, end=end):
                        mob.move_to(start + (end - start) * ease(alpha))
                    anims.append(UpdateFromAlphaFunc(token, glide, run_time=step["move_ms"] / 1000,
                                                     rate_func=rate_functions.linear))
            elif token is not None:
                anims.append(token.animate(run_time=fade).set_opacity(0))
                token = None
            # the clip lasts move_ms whatever moves in it
            self.play(AnimationGroup(*anims, Wait(run_time=step["move_ms"] / 1000, frozen_frame=False)))
            self.camera.get_image().save(self.out / f"step-{i + 1:02d}.png")
            lit_before, prev = lit_now, i


def render(scene_path, mode, out):
    theme = scenefile.load_theme()
    scene = scenefile.load(scene_path, theme)
    for f in theme["fonts"].values():
        if not manimpango.register_font(str(ROOT / f["file"])):
            raise SystemExit(f"Pango refused {f['file']}")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    r = theme["render"]
    with tempconfig({
        "frame_width": scene["width"], "frame_height": scene["height"],
        "pixel_width": scene["width"] * r["scale"], "pixel_height": scene["height"] * r["scale"],
        "frame_rate": r["fps"], "background_color": theme[mode]["panel"],
        "media_dir": str(out / "manim"), "save_sections": True, "disable_caching": True,
        "format": "mp4", "output_file": scene["id"], "write_to_movie": True,
        "verbosity": "WARNING", "progress_bar": "none",
        **({"tex_template": TEX} if "code" in scene else {}),
    }):
        cls = type("FromSceneFile", (FromSceneFile,), {
            "scene_data": scene, "theme_data": theme, "mode": mode, "out": out})
        if "code" in scene:
            cls = type("CodeScene", (code_class(scene),), {
                "scene_data": scene, "theme_data": theme, "mode": mode, "out": out})
        cls().render()


def code_class(scene):
    """The Animation class of a code scene's module (tools/manim/stepscene.py)."""
    if not shutil.which("latex") and Path("/Library/TeX/texbin/latex").exists():
        os.environ["PATH"] = "/Library/TeX/texbin" + os.pathsep + os.environ["PATH"]
    path = ROOT / scene["code"]
    spec = importlib.util.spec_from_file_location(scene["id"].replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Animation


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[2] not in ("light", "dark"):
        sys.exit(__doc__)
    render(sys.argv[1], sys.argv[2], sys.argv[3])
