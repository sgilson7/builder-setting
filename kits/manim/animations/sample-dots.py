"""The kit's sample code scene: twelve dots regrouped three ways.

Code scene for deck/scenes/sample-dots.json (tools/manim/stepscene.py). Each
dot is its own object, so the dots can move to new places together, which a
scene file of boxes and lines cannot describe.
"""
import numpy as np
from manim import Dot, FadeIn, FadeOut, LaggedStart, VGroup

from stepscene import StepScene

COUNT, GAP, RADIUS, LABEL_Y = 12, 40, 9, -110
KEYS = ("req", "msg", "res")


def grid(rows):
    """Where each dot goes when the twelve make `rows` rows."""
    cols = COUNT // rows
    return [np.array([(k % cols - (cols - 1) / 2) * GAP, ((rows - 1) / 2 - k // cols) * GAP + 20, 0.0])
            for k in range(COUNT)]


class Animation(StepScene):
    def construct(self):
        dots = VGroup(*[Dot(p, radius=RADIUS, color=self.ink(KEYS[0])) for p in grid(3)])
        label = self.words("3 × 4 = 12", px=22, weight="semibold").move_to([0, LABEL_Y, 0])
        with self.step():
            self.play(LaggedStart(*[FadeIn(d, scale=0.5) for d in dots], lag_ratio=0.06), FadeIn(label), run_time=1.2)
        for rows, text, key in ((2, "2 × 6 = 12", KEYS[1]), (1, "1 × 12 = 12", KEYS[2])):
            new = self.words(text, px=22, weight="semibold").move_to([0, LABEL_Y, 0])
            with self.step():
                self.play(*[d.animate.move_to(p).set_color(self.ink(key)) for d, p in zip(dots, grid(rows))],
                          FadeOut(label), FadeIn(new), run_time=1.2)
            label = new
