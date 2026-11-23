# Brief for writing code scenes

Hand this file to whoever writes the scenes, a person or an agent, with a list of scene IDs and what each should show. It is Manim Lab's brief for the thirty-seven CSC 226 animations, with the course taken out. Read it to the end before writing a scene. Paths are relative to the project's root.

## Files, per scene ID

- `deck/scenes/ID.json`, the scene file: `id`, `title`, `summary` (one sentence: what it shows and the result), `source` (what it was made from; kept in the project, never published), `width` 960, `height` 540, `code` `"animations/ID.py"`, and `steps`, each `{t, move_ms, hold_ms}`.
- `animations/ID.py`: `class Animation(StepScene)`, with each step's animations inside `with self.step():` (see `tools/manim/stepscene.py` and `animations/sample-dots.py`).
- Render: `.venv-manim/bin/python tools/manim/build.py deck/scenes/ID.json`. It writes `deck/media/ID/{light,dark}/step-NN.{mp4,png}` and `manifest.json`, in 10 to 40 seconds.

## Rules

1. **Write every animation from scratch.** Do not copy or adapt code from Manim's example gallery, other people's repositories or the web. Draw with Manim's primitives: no downloaded images or SVGs, and no images from the source material.
2. **Integers in the scene file.** `move_ms` is a whole number of frames, a multiple of 20 at 50 fps. Pick one rule for `hold_ms` and keep it; CSC 226 used `1000 + 30 × len(t)`, so a step of 100 characters holds 4000 ms.
3. A step's animations must fit in its `move_ms`. The renderer pads a shorter step and fails a longer one. Keep `move_ms` between 1200 and 6000, and a scene between 4 and 7 steps.
4. **Colours only through `self.ink(key)`**, never a hex value, so both themes work. The keys are in `data/manim/theme.json`. Text through `self.words(...)` (at least 14 px; `mono=True` for bit strings and code), maths through `self.tex(...)` (plain `article` template, amsmath and amssymb).
5. Units are scene pixels with the origin at the centre and y up: x from -480 to 480, y from -270 to 270. Keep 24 px clear of every edge. Nothing may overlap by accident or run off the frame.
6. **Size.** Each clip at most 1 MiB; a whole scene (both themes, clips and frames) ideally under 3 MB and never over 6 MB. Thousands of moving objects make large clips; use hundreds.
7. **Step words** (`t`): plain English, present tense, the step's point first, at most about 45 words. They are shown as text under the player and on the scene's own page, so the picture should carry its own labels too. Use `backticks` only for bit strings and code. Follow the project's `TONE.md` and `GLOSSARY.md`.
8. **Check every number by computation** before it goes into a step: enumerate counts, sums and algorithm traces in Python, and keep the result for the report. Source materials can be wrong (one CSC 226 file gave 1 + … + n as n(n−1)/2); use the correct value and report the error.
9. **Look at every render.** Open each step's light frame and at least two dark frames per scene. Fix overlaps, clipping, unreadable text and wrong colours, and render again until they are clean.
10. Touch only your own scenes' files. Do not edit `tools/`, `deck/manim/`, `tests/`, other scenes, or the project's notebook and state files. If the harness is in the way, report it.

## Report

For each scene: its ID, its number of steps, the numbers checked and how, the bytes of `deck/media/ID`, the largest clip, and anything changed from the brief or any error found in the source. Then list anything you could not do.
