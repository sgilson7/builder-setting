# Manim Calc journal

The design journal a Builder agent kept while it built Manim Calc, the tool at <https://sgilson7.github.io/builder-setting/>, from a one-line description: "a simple calculator program with interactive Manim animations in the browser". Open `index.html` to read it.

It shows the journal working on a real build:

- the opening entry, which reads Builder and the description back as numbered rules, with what holds each;
- the questions put to the person as answer chips (CM-Q1 to CM-Q6), each with the default the agent built on;
- the plan entry, with a FlowScene animation placed by `tools/journal/animate.py`;
- the build entry, with screenshots of the running tool and the divergences from the plan.

A project's journal is its own repository and is never pushed. This copy is kept here as an example, taken from its last commit unchanged. Its entries cite rows (T, R, S) in the project's own `SECOND-ORDER.md` and `TRIAGE.md`, and the project's source is not in this repository. Its one animation is still marked proposed, though the tool is built: redrawing a scene from the build once it exists is something the journal rules ask for and no check enforces yet.
