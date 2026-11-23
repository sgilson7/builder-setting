# Kits

A kit is a set of files a project copies on purpose when its brief needs something the template leaves out. The template does not include any kit, and a project that never copies one is a complete Builder project. Which kits exist, and what each changes, is the table under "The kits".

Each kit says three things in its README:

- which reference default it changes, if any, and how;
- which files to copy and where they go;
- which tests come with it, and what each one was seen to catch.

A kit never changes a Builder requirement. When a project copies a kit that changes a reference default, it records the change in the table at the end of its own `BUILDER-SPEC.md` ("Changes to the defaults in this project") and in `SECOND-ORDER.md`. A kit's README gives the row to paste.

## The kits

| Kit | For | Changes |
| --- | --- | --- |
| [`online/`](online/) | peer-to-peer play between browsers, introduced by a room code or by pasted codes, with a rollback session (D23) | D3 and D4 for `web/net/` only, through a fence test; uses R7's allowance for a declared off-origin feature |
| [`saves/`](saves/) | progress that survives a reload and a deploy: a versioned save, old saves loaded on every check, a file the player keeps, a playtest file to send back | D17 for `web/save/store.js` only, through a fence test |
| [`canvas/`](canvas/) | a page that draws on a 2D canvas from a draw list the core builds; screenshots of still scenes | none |
| [`realtime/`](realtime/) | games with a fixed tick: pointer lock with a fallback, taps between ticks, Q16.16 maths, seeded chance, probes, frame counting | none |
| [`mobile/`](mobile/) | touch screens: pointer events, a CSS touch baseline, a manifest, a tablet pass in the browser check | D4 (adds `manifest-src 'self'`), D7 (adds a tablet engine) |
| [`privacy/`](privacy/) | tools that handle a reader's own data and promise to keep it on the device | tightens D4 and D7; changes nothing else |
| [`office-intake/`](office-intake/) | a game designed by students in Word, PowerPoint and Excel templates, copied into a new project by an intake script that keeps students' names out | none |
| [`codebase-guide/`](codebase-guide/) | a project that explains an existing codebase: excerpts checked against it, the codebase kept read-only, measured and proposed parts kept apart | none |
| [`manim/`](manim/) | deck and journal animations rendered with Manim, played step by step, with a still for reduced motion; a set of them published as a site with a page per animation | none |
| [`flowscene/`](flowscene/) | deck and journal animations of how code runs through a system: boxes, marks along the lines between them, and the code at each step, drawn in SVG from a scene file | none |

For animation, choose by what has to move. A system's requests, replies and events, with the code beside each step, are FlowScene's: they stay text, weigh kilobytes and change with an edit. Mathematics, shapes that turn into other shapes and many objects at once are Manim's: they are rendered to video at build time and cost megabytes. Each kit's README says more, and a deck can use both.

## Copying a kit

1. Read the kit's README to the end before copying anything.
2. Copy the files to the paths it names. Paths in a kit mirror a project's layout: `kits/online/web/net/config.js` goes to `web/net/config.js`.
3. Add the module lines it names to `crates/core/src/lib.rs`.
4. Make the edits it names to existing files. Each edit is shown in full, so a scripted edit can assert that it matched.
5. Paste its row into the project's change table, if it changes a default.
6. Add a row to `tests/breaks.json` for each kit test the project keeps, and run `scripts/break_tests.py`. Each kit test was seen failing with its behaviour broken when the kit was written; the project's copy needs the same proof.
7. Run `./scripts/check.sh`.

The reference repository runs each kit's core tests inside a copy of the minimal example (`scripts/check-kits.sh`), so a kit's code passes the project's format, lint and boundary checks as shipped.

## Where the kits come from

The kits collect patterns from games and tools built on Builder or alongside it. Peter (GitHub [ptonkle](https://github.com/ptonkle)), who co-designed Builder, wrote the online transport design, the draw-list renderer and the screenshot path in Mandible and Ape Race. The other sources are the author's own projects: Floodline and Vagrancy (the first transport lessons), Ribbit King, Level Twenty and Raiders of the Lost Mart (online play), Pursuer and Long Time Comin' (realtime input), Slushline (touch screens), Status Trends (privacy), Idle Game and CHUMWORLD (saves), the ToyTalk and SnapClass guides (codebase guides), and Manim Lab, with the SnapClass guide's FlowScene and the MerryQuery deck (Manim animations, and the FlowScene kit, which carries the SnapClass guide's engine at the author's request). Each kit names what it took from which. The code in the kits was written fresh for them.
