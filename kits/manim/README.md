# Manim kit

For a deck or journal whose animations should be rendered video rather than drawn by the page: maths, many objects moving at once, shapes that turn into other shapes. The kit renders each animation with [Manim Community](https://www.manim.community/) into one clip and one final frame per step, in light and dark. A small player then shows them in the page with Play, Pause, Back, Next, Restart and every step as text. Under reduced motion the player shows each step's final frame and plays nothing.

It changes no reference default. The renderer runs at build time, outside the core, like the art pipeline. The player obeys D3 even though it sits outside `web/`: it holds no number but 0 and 1, and every time and path comes from the scene file or the manifest. Clips, frames and fonts load from the page's own origin, so D4's `default-src 'self'` already allows them.

## When to use it, and when not

Measured in Manim Lab, which rebuilt two deck animations beside their originals:

- **Bytes.** A node-and-edge animation of 8 steps was 32 KB as FlowScene and 4.5 MB as Manim media, 140 times as much. A 4-step one was 90 times. About three quarters of the media is the final-frame PNGs, not the clips.
- **Edits.** Changing one word in a label means a render (8 to 40 seconds on a laptop) and new media to commit. Text inside the picture can't be selected, searched or translated. The step words under the player are still text.
- **Toolchain.** Building needs Python 3.11 to 3.14, Manim, Cairo, Pango and FFmpeg, plus BasicTeX and dvisvgm for maths. Viewing needs only a browser.
- **What it buys.** Exact frames, fixed at build time and checked byte for byte; a true still for reduced motion; one render that plays in a deck, a page or a lecture video; and animations that a page of boxes and lines cannot describe.

Use it where the animation *is* the explanation and changes rarely. For boxes and arrows that change with the text, keep drawing them in the page.

## Where it comes from

Manim Lab (2026-11), a Builder project that tried Manim for the SnapClass guide's FlowScene animations and the MerryQuery deck's stepper. It rebuilt one of each beside its original and added three discrete-maths animations FlowScene could not draw. The palette in `data/manim/theme.json` is those two decks' colours. `tools/manim/geometry.py` ports FlowScene's border-to-border edge rule (the SnapClass guide's `engine.js`, lines 102 to 120). Comments that cite `Manim Lab R2.1` and similar refer to rows of that project's `SECOND-ORDER.md`. The rest was written for the lab.

## What to copy

Paths mirror a project's layout: `kits/manim/tools/manim/render.py` goes to `tools/manim/render.py`.

| From the kit | What it does |
| --- | --- |
| `tools/manim/scene.py` | reads and checks a scene file (stdlib only): integers only, steps in whole frames, every node, style and code file it names is there |
| `tools/manim/render.py` | renders one scene in one theme under Manim; a scene file of nodes and edges, or a code scene |
| `tools/manim/stepscene.py` | the base class for code scenes: `with self.step():`, theme colours (`ink`), text (`words`), maths (`tex`) |
| `tools/manim/build.py` | renders every scene (or those named) in both themes, remuxes each clip so the same render gives the same bytes, writes the manifest |
| `tools/manim/manifest.py` | what a render was made from (scene, code, theme, renderer, fonts, Manim and FFmpeg versions) and each file's hash; says when a render is stale; the size budget |
| `tools/manim/mp4.py` | reads an MP4's frame count and length without FFmpeg (stdlib only) |
| `tools/manim/geometry.py` | edge end points and the CSS ease, shared by the renderer and the tests |
| `tools/manim/theme.py` | writes `deck/manim/theme.css` from `data/manim/theme.json` |
| `data/manim/theme.json`, `data/manim/budget.json` | palette, fonts, text styles and frame rate; size limits for the media |
| `deck/manim/player.js`, `player.css`, `theme.css` | the player and its styles |
| `deck/fonts/` | Public Sans and JetBrains Mono (SIL OFL 1.1), with their licences and `SHA256SUMS` |
| `deck/scenes/sample-flow.json`, `deck/scenes/sample-dots.json`, `animations/sample-dots.py`, `deck/media/sample-*` | a scene file and a code scene, rendered; delete them once the project has its own |
| `deck/sample.html` | a page with both players: the markup to copy |
| `tests/manim/test_manim.py` | 29 tests that need no Manim |
| `tests/manim/page_check.py` | the sample page in Chromium, Firefox and WebKit (Playwright) |
| `scripts/setup-manim.sh`, `requirements-manim.txt` | Manim, pinned, in `.venv-manim` |
| `scripts/render-audit.sh` | renders everything again and requires the committed bytes |

Then, in the project:

1. Run `./scripts/setup-manim.sh` (needs Homebrew `cairo` and `pango`, and FFmpeg). Add `.venv-manim/` to `.gitignore`.
2. Paste the rows under "Licences" into `LICENSES.md`, and change `test_every_font_the_renderer_registers_is_in_licenses` to read `LICENSES.md` in place of this README (the line is marked).
3. Add a step to `scripts/check.sh`: `python3 -m unittest discover -s tests/manim`. Add `tests/manim/page_check.py` beside the browser check, and a rule to `tests/tags.toml` covering `tools/manim/**`, `deck/**`, `animations/**` and `data/manim/**`.
4. Add a row to `tests/breaks.json` for each test under "Tests", and run `scripts/break_tests.py`.

## Writing an animation

**A scene file** (`deck/scenes/ID.json`) describes boxes, lines, marks that move along them, a token, and the steps. `tools/manim/scene.py` documents every field; `sample-flow.json` is a small one. Every number is an integer, in pixels and milliseconds. A step's `move_ms` is a whole number of frames (20 ms at 50 fps). Each step has words, `t`, which the player shows as text, with `` `backticks` `` set as code.

**A code scene** is a scene file with `"code": "animations/ID.py"` and steps of `{t, move_ms, hold_ms}`. The module defines `class Animation(StepScene)`, and its `construct()` wraps each step's animations in `with self.step():`. The step is padded to exactly `move_ms`; one that runs longer fails the render. `animations/sample-dots.py` is a small one. Units are scene pixels with the origin at the centre and y up. Use `self.ink("req")` for colours, `self.words(...)` for text and `self.tex(...)` for maths, so both themes and the fonts stay right. Editing the code makes the render stale, as editing the scene file does.

**Maths** needs BasicTeX and dvisvgm (`brew install --cask basictex`, `brew install dvisvgm`). `stepscene.py` sets maths with a plain `article` template, because BasicTeX lacks `preview.sty`, which Manim's default template needs.

**Render** with `.venv-manim/bin/python tools/manim/build.py` (or name scene files). Commit `deck/media/`. **Show it** with `<div data-manim="ID"></div>`, the labels script and `player.js`, as `deck/sample.html` does. Serve the page; opened from disk, the player can't fetch its files and says so.

## Tests

Run the tests from the repository root:

```bash
python3 -m unittest discover -s kits/manim/tests/manim
```

Each test listed here was seen to fail against a planted defect in `scripts/prove-checks.sh`:

| Test | Planted defect it catches |
| --- | --- |
| `test_the_committed_scenes_are_valid` | a committed scene file's move is not whole frames |
| `test_a_scene_naming_a_missing_node_is_refused` | the check for an edge's nodes is switched off |
| `test_a_lit_node_that_does_not_exist_is_refused` | the check for a step's lit nodes is switched off |
| `test_a_step_without_words_is_refused` | a step with blank words passes |
| `test_a_scene_with_a_fraction_is_refused` | the integers-only check is switched off |
| `test_a_move_that_is_not_whole_frames_is_refused` | the whole-frames check is switched off |
| `test_a_move_shorter_than_the_fade_is_refused` | the fade-length check is switched off |
| `test_a_text_style_the_theme_lacks_is_refused` | the text-style check is switched off |
| `test_the_scene_hash_ignores_key_order` | the hash no longer sorts keys |
| `test_the_border_point_by_hand` | an edge leaves its box at the farther edge |
| `test_the_css_ease_by_hand` | the ease drops its cubic term |
| `test_the_reader_counts_frames_in_a_hand_built_file` | the MP4 reader counts one frame too many |
| `test_the_reader_refuses_a_file_that_is_not_mp4` | the MP4 reader accepts any file |
| `test_every_step_has_a_clip_and_a_final_frame_in_each_theme` | a manifest names a missing clip |
| `test_a_scene_edited_after_its_render_is_stale` | the scene-hash check is switched off |
| `test_a_changed_theme_makes_the_render_stale` | the theme-hash check is switched off |
| `test_a_swapped_clip_fails_its_hash` | the file-hash check is switched off |
| `test_a_missing_final_frame_fails` | a missing PNG passes |
| `test_a_clip_whose_length_disagrees_with_the_scene_fails` | the frame-count check is switched off |
| `test_the_media_fits_the_budget` | the clip budget is set below the sample's largest clip |
| `test_a_tight_budget_fails` | the clip budget is not checked |
| `test_the_theme_css_matches_theme_json` | `theme.py` writes keys with underscores |
| `test_every_font_the_renderer_registers_is_in_licenses` | a font's licence row names another file |
| `test_a_code_scene_whose_code_is_missing_is_refused` | the code-file check is switched off |
| `test_a_code_step_that_is_not_whole_frames_is_refused` | a code step's whole-frames check is switched off |
| `test_the_code_is_part_of_the_render_it_made` | the code's hash is left out of the scene |
| `test_code_of_blanks_comments_and_strings` | the test's own JavaScript scanner blanks code too |
| `test_the_player_holds_no_number_but_0_and_1` | a `2` in the player |
| `test_the_player_parses_no_html` | the player sets step words with `innerHTML` |
| `page_check.py`: reduced motion plays no clip | the player ignores `prefers-reduced-motion` |
| `page_check.py`: Pause stops the clip and the timer | Pause leaves the clip playing |

`scripts/render-audit.sh` is outside the everyday check because it needs Manim and takes seconds per scene. Run it after changing the renderer, the theme or a scene. On another machine a different Cairo, Pango or x264 can change bytes without a stale render; each manifest records the versions to compare.

## Licences

Rows to paste into the project's `LICENSES.md`:

| File | What and where from | Licence |
| --- | --- | --- |
| `deck/fonts/PublicSans-wght.ttf` | Public Sans, variable weight, from google/fonts `ofl/publicsans/PublicSans[wght].ttf`; see `deck/fonts/SHA256SUMS` | Copyright 2015 The Public Sans Project Authors. SIL Open Font License 1.1, `deck/fonts/PublicSans-OFL.txt` |
| `deck/fonts/JetBrainsMono-wght.ttf` | JetBrains Mono, variable weight, from google/fonts `ofl/jetbrainsmono/JetBrainsMono[wght].ttf`; see `deck/fonts/SHA256SUMS` | Copyright 2020 The JetBrains Mono Project Authors. SIL Open Font License 1.1, `deck/fonts/JetBrainsMono-OFL.txt` |
| `deck/media/` | rendered by Manim Community 0.22.1 from `deck/scenes/`; the only fonts in the renders are the two above (Manim bundles no font of its own into a render) | the project's licence; the lettering is the fonts above, under the OFL |
| maths in `deck/media/`, if any | Computer Modern outlines, set by LaTeX and turned into paths by dvisvgm | Knuth's licence for Computer Modern; the AMS Type 1 versions under the SIL Open Font License |

Tools, not shipped in the page: Manim Community (MIT), ManimPango (MIT), pycairo (LGPL-2.1-only or MPL-1.1), PyAV (BSD-3-Clause; its FFmpeg encodes with libx264, GPL), FFmpeg (LGPL/GPL), and for maths BasicTeX (LPPL and others) and dvisvgm (GPL-3.0). An encoder's licence covers the encoder, not the videos it writes.
