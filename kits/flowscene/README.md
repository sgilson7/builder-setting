# FlowScene kit

For a deck or journal that explains how a system runs: boxes for its parts, grouped in zones, and marks that carry each request, reply, stream or event between them, one step at a time, beside the code that runs at that step. The page draws everything in SVG from a scene file, so the boxes, labels and code stay text that can be selected, searched and edited.

The template's design journal already plays this engine: `tools/journal/flowscene/` holds the same files, and `tools/journal/animate.py` puts a scene into the journal page (`tools/journal/ENTRIES.md`, Animations). Copy this kit for a deck or another page outside the journal.

It changes no reference default. The engine holds layout and timing numbers, which D3 forbids in `web/`, so it belongs in a deck or journal page and not in a tool's `web/` folder. Its scene files and media load from the page's own origin, so D4's `default-src 'self'` already allows them.

## FlowScene or Manim

Builder has two animation kits. Choose by what the animation has to show.

| Use | For | Examples |
| --- | --- | --- |
| this kit | how code runs through a system: requests between services, the code at each step, flows a reader picks between | the SnapClass guide's request lifecycles, the SnapClass Next and game-AI decks |
| [`kits/manim/`](../manim/) | mathematics and shapes that move or turn into other shapes, many objects at once, a still for reduced motion that is a true final frame | the CSC 226 discrete-mathematics animations |

Measured in Manim Lab, which rebuilt a FlowScene animation in Manim beside the original: an 8-step node-and-edge animation was 32 KB as FlowScene and 4.5 MB as Manim media. A FlowScene label is changed by editing the scene file and reloading; a Manim label needs a render of 8 to 40 seconds and new media to commit. Manim was better where the picture itself has to move: the lab's three discrete-mathematics animations, and the thirty-seven for CSC 226, could not be drawn as boxes and marks.

A deck can use both: a FlowScene for the system and a Manim player for the proof.

## Where it comes from

FlowScene is the author's own engine, written for the SnapClass guide after the ToyTalk journal's request-lifecycle tab and used again in the SnapClass Next and game-AI decks. Manim Lab copied it unchanged to compare against Manim, and the author asked for it to become a Builder kit (Manim Lab T8). `deck/flowscene/engine.js` and `engine.css` are that engine with two changes: every word the reader sees comes from the page's `<script id="flow-labels">`, and `<div data-flow="ID">` loads `flows/ID.json` without a script of its own. The scene checker, the sample, the host tokens and the tests were written for the kit.

## What to copy

Paths mirror a project's layout: `kits/flowscene/tools/flowscene/check.py` goes to `tools/flowscene/check.py`.

| From the kit | What it does |
| --- | --- |
| `deck/flowscene/engine.js`, `engine.css` | the engine and its styles; `window.FlowScene(root, scene, code)` |
| `deck/flowscene/host.css` | the six tokens `engine.css` takes from its page (`--bg --panel --fg --muted --line --accent`), light and dark; leave it out if the page has its own |
| `deck/flows/sample.json` | a sample scene with two flows, code excerpts and a proposed contract; delete it once the project has its own |
| `deck/flowscene-sample.html` | a page with one FlowScene and the labels script: the markup to copy |
| `tools/flowscene/check.py` | checks every scene file (stdlib only); its docstring documents every field |
| `tests/flowscene/test_flowscene.py` | 11 tests, stdlib only |
| `tests/flowscene/page_check.py` | the sample page in Chromium, Firefox and WebKit (Playwright) |

Then, in the project:

1. Add a step to `scripts/check.sh`: `python3 tools/flowscene/check.py` and `python3 -m unittest discover -s tests/flowscene`. Run `tests/flowscene/page_check.py` beside the browser check, and add a rule to `tests/tags.toml` covering `deck/flowscene/**`, `deck/flows/**` and `tools/flowscene/**`.
2. Add a row to `tests/breaks.json` for each test under "Tests", and run `scripts/break_tests.py`.
3. If the page shows code from a codebase the project explains, keep the excerpts in the codebase-guide kit's `data/excerpts.json` as well, so a function that moves fails the check ([`kits/codebase-guide/`](../codebase-guide/)).

## Writing a scene

A scene file, `deck/flows/ID.json`, holds:

- **nodes**: `"id": [x, y, "label", "kind"]`, where x and y are the box's centre in the viewBox and `\n` breaks the label. The kind sets the outline: `svc` (the default), `client`, `store`, `ext` (outside the system, dashed), `mod`, `bus`, `new` (proposed) and `chg` (changed).
- **zones**: rectangles behind the boxes with a label, toned `a` to `d`.
- **edges**: the lines the marks travel, `["a", "b"]`, or `["a", "b", true]` for a dashed one. **via** bends an edge through points: `"a>b": [[x, y]]`.
- **flows**: each with an `id`, a `title` on its tab, a one-sentence `sum`, and steps. A step has words `t`, marks `go` (`{"path": [...], "kind": "req"}`; a path may pass through several nodes), nodes to light without a mark `work`, and either an excerpt `c` with lines `hl` to light, or a contract `x` (`{"h": heading, "body": text}`) for a flow that is proposed and has no code yet.
- **code**: excerpts by key, `{"file", "first", "lines"}`. `hl` counts in the file's line numbers, so `first: 20` with four lines takes `hl` from 20 to 23.

`tools/flowscene/check.py` refuses a scene that names a node it lacks, sends a mark between two boxes with no edge drawn between them, lights a line outside its excerpt, names an excerpt it lacks, or leaves a step without words. Run it after every edit; the engine would otherwise draw the mistake without complaint.

A step's words are shown as text under the picture and in "Every step as text", so the scene is readable without the motion. Under reduced motion the marks are placed at the ends of their paths without moving.

**Show it** with `<div data-flow="ID"></div>`, the labels script and `engine.js`, as `deck/flowscene-sample.html` does. Serve the page; opened from disk, the engine can't fetch the scene file and says so. A page in a subfolder sets `data-flow-base="../"` on an ancestor. A page that builds its scene in JavaScript can still call `FlowScene(root, scene, code)` directly.

## Tests

Run the tests from the repository root:

```bash
python3 -m unittest discover -s kits/flowscene/tests/flowscene
```

Each test listed here was seen to fail against a planted defect in `scripts/prove-checks.sh`:

| Test | Planted defect it catches |
| --- | --- |
| `test_the_committed_scenes_are_valid` | the sample sends a mark between two boxes with no edge |
| `test_a_path_through_a_missing_node_is_refused` | the check for a path's nodes is switched off |
| `test_a_mark_between_unjoined_nodes_is_refused` | the check that each hop follows an edge is switched off |
| `test_a_highlight_outside_its_excerpt_is_refused` | the highlight range check is switched off |
| `test_an_excerpt_the_scene_lacks_is_refused` | the excerpt check is switched off |
| `test_a_step_without_words_is_refused` | blank words pass |
| `test_an_unknown_mark_kind_is_refused` | the mark-kind check is switched off |
| `test_a_fraction_in_a_node_is_refused` | the integers-only check is switched off |
| `test_every_label_the_engine_reads_is_on_the_sample_page` | the engine reads a label the sample page lacks |
| `test_the_engine_holds_no_words_of_its_own` | the engine's Play button has its word written in |
| `test_the_engine_parses_no_html` | the step words are set with `innerHTML` |
| `page_check.py`: reduced motion places the mark at once | the engine ignores `prefers-reduced-motion` |
| `page_check.py`: Pause holds the step | Pause leaves the timer running |

## Licences

The engine is the author's own work, carried into Builder at their request. The kit bundles no font: the page's own fonts, or the system's, set the text.
