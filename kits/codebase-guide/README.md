# Codebase guide

For a project whose job is to explain an existing codebase rather than build a new tool: a maintainers' guide, an architecture tour, a rework proposal. The journal is the product. Its pages show the codebase as it runs today and, where asked, as it could be, and every claim about today is tied to lines of the code.

Changes no reference default. The Rust core, shim and page stay in the project for Builder's own records and checks; a guide has little or nothing to put in them, and the project says so in `SECOND-ORDER.md`.

## Where it comes from

Two projects built the same tools separately: the ToyTalk maintenance journal (its excerpt checker and request lifecycles) and the SnapClass guide (a checksum of the read-only codebase, measured and proposed tabs, one build that writes the journal, a deck and a text backup). The code here was written fresh for the kit.

## What to copy

| From the kit | To the project | What it does |
| --- | --- | --- |
| `tools/guide/excerpts.py` | `tools/guide/excerpts.py` | checks every code excerpt the guide shows: file, first and last line, and the text the first line must contain; a function that moved fails and names its new line |
| `scripts/target_unchanged.py` | `scripts/target_unchanged.py` | hashes every file of the codebase and compares with a manifest written once before reading; an edit, an install or a `git init` inside it fails |
| `tools/guide/labels.py` | `tools/guide/labels.py` | checks that each journal part marked `data-guide="measured"` shows checked excerpts and each part marked `"proposed"` shows none |

Then, in the project:

1. Write the codebase's path in `notes/target` (one line). `tools/guide/excerpts.py` and `scripts/target_unchanged.py` read it.
2. Run `python3 scripts/target_unchanged.py --write` once, before reading anything, and commit `notes/target.sha256`.
3. Keep excerpts in `data/excerpts.json`: `"key": ["path/in/codebase", first, last, "text on the first line"]`.
4. Mark each journal tab or entry about the codebase `data-guide="measured"` or `data-guide="proposed"`, and give each excerpt shown on a page `data-excerpt="key"`.
5. Add a step to `scripts/check.sh` (and a rule to `tests/tags.toml`):

   ```bash
   step "guide: codebase unchanged, excerpts in place, measured and proposed kept apart"
   "$PY" scripts/target_unchanged.py
   "$PY" tools/guide/excerpts.py
   "$PY" tools/guide/labels.py
   ```

6. Add a `tests/breaks.json` row for each of the three, as the kit's tests do below.

Counts on a page (routes, tables, files) come from a script that reads the codebase, never from notes; the project's build writes them into the journal. For a presentation of the guide to someone outside the build, use `tools/journal/present.py`, which turns the journal's figures into a deck with comments and the open questions, plus a plain-text copy.

## Tests

`tests/test_guide.py`, against the small codebase in `tests/fixture/`:

| Test | Seen failing when |
| --- | --- |
| a moved function fails and says where it went | the first-line check was removed |
| an edit, an addition or an install in the codebase fails | the checksum compare ignored added files |
| the manifest is written once | `--write` overwrote an existing manifest |
| a proposed part showing code fails | proposed parts were not checked |
| a measured part without code fails | measured parts were not required to cite excerpts |

`scripts/prove-checks.sh` in the reference repository plants each of these breaks in a copy of the kit.

## The row for SECOND-ORDER.md

| R1.n | divergence | the project is a Builder tool with a Rust core | the job is a guide to an existing codebase; the journal is the product | `kits/codebase-guide`: excerpts checked, codebase unchanged, measured and proposed kept apart | | done |
