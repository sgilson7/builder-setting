# Prompt set C: feedback drafts from a teacher's rubric

The source request is Team 4's Feedback Generator in a six-week teacher–developer co-design program (manuscript under review; details withheld): teachers wanted "teacher-editable drafts for feedback based on student work and rubric information", inspected and revised before sharing, with student submissions kept separate from course-wide materials. As described, that feature needs a generative model while the teacher uses it, which falls outside a static Builder tool. This prompt set keeps the purpose and moves the generation to authoring time: the comments come from a bank the teacher writes, or generates beforehand with any tool, and ships as a file. The teacher reads the student's work, picks a level for each criterion, and the tool composes a draft that the teacher edits and copies. Student work never enters the tool.

Give everything below the line, unchanged, to a fresh coding-agent session whose working directory holds only a copy of `template/` from this repository. Its labels are the AI-literacy step labels the procedure uses (`B1`–`B4`, `C1`–`C5`).

---

## Brief (B1 establish context; C1 frame the problem and set the rules)

You are building a static browser tool for a teacher who writes individual feedback on student projects. This directory is a copy of the Builder template: read `CLAUDE.md` and `BUILDER-SPEC.md` first, and keep to them.

The tool has two parts on one page.

**Rubric.** The teacher opens a rubric file (JSON) or starts from the sample rubric the page loads by default. A rubric has a title, an opening line, a closing line, a setting for whether the draft shows points, and one or more criteria; each criterion has a name and two to six levels; each level has a label, a whole number of points, and the comment the teacher wants a student at that level to read. In the page the teacher can edit any of those texts and numbers, add a criterion (it starts with copies of the first criterion's level labels and points, and empty comments), remove a criterion (not the last one), and save the rubric as a file to reuse.

**Draft.** The teacher types an optional student name, picks one level for each criterion, and can type a personal note. When every criterion has a level, the tool composes a feedback draft: the opening line (with the name if one was given), one paragraph per criterion with its name, its level label, its points if the rubric shows points, and the level's comment; then the total ("N of M points") if the rubric shows points; then the personal note if any; then the closing line. The draft appears in an editable text box. The teacher edits it and copies it, or saves it as a text file. "Next student" clears the name, the levels and the note and keeps the rubric. Until every criterion has a level, the tool names the criteria still missing and shows no draft.

Nothing is sent anywhere and nothing is stored between visits: the page uses no browser storage. Student names and notes stay in the page until the teacher clears them or closes it.

Keep to the template's architecture and its checks: every rule in `crates/core`, a shim in `crates/shim` that decides nothing, a page in `web/` that draws what the core returns, content in `data/`, `./scripts/check.sh` as the full check.

Rules:
(a) The core depends only on serde and serde_json.
(b) The shim decides nothing.
(c) The page keeps no copy of a rule: composing the draft, the total, which criteria are missing, and every rubric validation and edit happen in the core.
(d) Nothing runs anywhere but static hosting, and the page makes no request to another origin.
(e) The core uses no floats, hash maps, or clocks, so the same inputs always give the same draft.
(f) Every new test is broken once and watched failing before it is kept.

What you may not decide alone: adding any network request, any third-party script or service, any model, any browser storage, or any way for student information to leave the teacher's device. If something seems to need one, stop and say so.

Write the sample rubric yourself as clearly marked sample content: a project-report rubric with four criteria and four levels each (points 1 to 4), with a short comment for every level. The page must say on screen that the rubric is sample content to check or replace.

The plan is approved in advance: write `PLAN.md`, then continue through the agent's stages without waiting. Commit after each working step with a message that says what changed. Do not push and do not deploy.

## Plan (B2 require step-by-step justification)

Before writing code, write `PLAN.md`: each decision with the reason for it and the test that will show it holds, in build order. Fill in `MEASUREMENTS.md` with the starting state of the template. Then build in the order of the plan, and put each core rule's test in the same change as the rule.

## Notebook (B3 build in self-questioning; C3 interrogate the claim)

Keep `SECOND-ORDER.md` while you work: one row per assumption, surprise, or open item, with a kind (divergence from the plan, finding, or worklist item for the teacher) and a status (done, open, or person). Before you finish, list three assumptions about how a teacher will use the tool and check each against this brief.

## Corrective dialogue (B4 plan the corrective dialogue)

When a test or check fails, write down the file and line, what was expected, and what happened, and fix the rule in the core, never in the page.

## Checks (C4 verify against hand-computed cases)

Include core tests whose expected values you worked out by hand: the full draft text for one set of choices on the sample rubric, with and without a name, a note, and points; the total for that set; the list of missing criteria for a partial set; and the rubric after adding and after removing a criterion. Include tests that a rubric file with a missing field, a criterion with one level or seven, negative or non-integer points, or a removal of the last criterion is rejected with a message the page shows, never a crash. Keep the template's boundary tests passing. In `tests/browser/interactions.py`, drive the tool the way a teacher would: check that the sample banner shows, pick levels for every criterion, type a name and a note, compare the draft with the text you worked out by hand, edit a comment and see the draft change, add and remove a criterion, save the rubric and open the saved file again, and press "Next student".

Done means: `./scripts/check.sh` passes, including the browser check in Chromium, Firefox and WebKit; `README.md` says what the tool does, how to build, test and serve it, and that the sample rubric is sample content.

## Handoff (C5 consolidate in your own words)

Finish with `HANDOFF.md`: what was built, what passed (the end of `./scripts/check.sh`), what is open, and what the teacher should check by hand before using the tool with a class.
