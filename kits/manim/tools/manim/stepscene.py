"""The base for code scenes: an animation written as Manim code, not as nodes and paths.

A code scene is a scene file with "code": "animations/ID.py" and steps of
{t, move_ms, hold_ms}; the module defines `class Animation(StepScene)` whose
construct() wraps each step's animations in `with self.step():`. The harness
does the rest as for any scene: one clip and one final-frame PNG per step, light
and dark, the manifest, the checks and the deck's player.

    class Animation(StepScene):
        def construct(self):
            dots = VGroup(*[Dot(radius=4, color=self.ink("fg")) for _ in range(7)])
            with self.step():
                self.play(FadeIn(dots), run_time=1)

Units: 1 Manim unit = 1 scene pixel, origin at the centre, y up (Manim's own way).
A step's animations may take at most its move_ms; the step is padded with a held
frame to exactly move_ms, so the clip has move_ms / frame frames and the manifest
check holds. Colours come from theme.json's palette in the scene's theme (ink),
text from its fonts (words), maths from LaTeX (tex).
"""
from contextlib import contextmanager

from manim import MathTex, Scene, TexTemplate, Text
from manim.constants import BOLD, NORMAL, SEMIBOLD

import scene as scenefile

EM = 72          # Manim font_size per scene pixel of em (render.py)
SET_AT = 48      # Pango and LaTeX set at this size, then scale (render.py, Manim Lab R2.1)
WEIGHTS = {"normal": NORMAL, "semibold": SEMIBOLD, "bold": BOLD}
# BasicTeX has no preview.sty, which Manim's standalone[preview] class needs, nor
# several packages in Manim's default preamble; dvisvgm crops an article page to
# its ink, so this is all the maths needs (Manim Lab R3.2).
TEX = TexTemplate(documentclass=r"\documentclass{article}\pagestyle{empty}",
                  preamble=r"\usepackage{amsmath}\usepackage{amssymb}")


class ExactFrames:
    """Exactly run_time x fps frames, at 1/fps .. run_time, so a clip never repeats
    the previous clip's last frame and always ends on the step's final state (Manim Lab R2.2)."""
    theme_data = None

    def get_time_progression(self, run_time, description, n_iterations=None, override_skip_animations=False):
        from tqdm import tqdm
        fps = self.theme_data["render"]["fps"]
        n = round(run_time * fps)
        return tqdm([k / fps for k in range(1, n + 1)], desc=description, disable=True)


class StepScene(ExactFrames, Scene):
    scene_data = theme_data = mode = out = None

    def setup(self):
        self._at = 0

    def ink(self, key, opacity=False):
        """A palette colour in this render's theme; with opacity=True, (hex, 0..1)."""
        v = self.theme_data[self.mode][key]
        hexa, pct = (v[0], v[1]) if isinstance(v, list) else (v, 100)
        return (hexa, pct / 100) if opacity else hexa

    def words(self, text, px=16, weight="normal", colour="fg", mono=False):
        font = self.theme_data["fonts"]["mono" if mono else "body"]["family"]
        m = Text(text, font=font, font_size=SET_AT, weight=WEIGHTS[weight], color=self.ink(colour))
        return m.scale(px * EM / SET_AT)

    def tex(self, *parts, px=24, colour="fg"):
        m = MathTex(*parts, tex_template=TEX, font_size=SET_AT, color=self.ink(colour))
        return m.scale(px * EM / SET_AT)

    @contextmanager
    def step(self):
        steps = self.scene_data["steps"]
        i = self._at
        if i >= len(steps):
            raise scenefile.SceneError(f"{self.scene_data['id']}: the code plays more steps than the scene file's {len(steps)}")
        step = steps[i]
        fps = self.theme_data["render"]["fps"]
        self.next_section(f"step-{i + 1:02d}")
        start = self.renderer.time
        yield step
        frames = round((self.renderer.time - start) * fps)
        want = step["move_ms"] * fps // 1000
        if frames > want:
            raise scenefile.SceneError(f"{self.scene_data['id']} step {i + 1}: its animations take {frames} frames, "
                                       f"more than move_ms {step['move_ms']} allows ({want})")
        if frames < want:
            self.wait((want - frames) / fps, frozen_frame=False)
        self.camera.get_image().save(self.out / f"step-{i + 1:02d}.png")
        self._at += 1

    def tear_down(self):
        if self._at != len(self.scene_data["steps"]):
            raise scenefile.SceneError(f"{self.scene_data['id']}: the code played {self._at} steps; "
                                       f"the scene file has {len(self.scene_data['steps'])}")
