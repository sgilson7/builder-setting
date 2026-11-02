# The design journal

The person reads four things in a Builder build: the brief, the plan, the notebook and the tool. In the games built after Builder's first release, a fifth grew up beside them: a design journal, an HTML page of dated entries where the agent shows the person what was asked, how it read the request, what it decided and on what default, what the build looks like, and what changed from the plan. The person reviewed the games from their journals and answered in them by number. From this version the template starts every project with one (reference default D19).

## What the journal is

A static page beside the project, by default `../<project>-journal/`, kept as its own git repository and never pushed. It holds draft screenshots and the person's reference material (photos of a real place, a pet, a floor plan), which have rights questions a public repository should not carry. `python3 tools/journal/new_journal.py` starts it from `tools/journal/index.html`. It works opened from disk; an agent that can publish it to a private page may, unless the brief says the content is confidential.

The repository's files stay the record. `SECOND-ORDER.md`, `TRIAGE.md` and `HANDOFF.md` keep their checks, and every journal entry cites the rows it reports. The journal is a view onto those files with pictures added, laid out so that the person reads in one place and answers by number.

## The opening entry

Before it plans, the agent reads Builder and the brief back to the person. The entry has fixed parts: what Builder asks of the agent, in its own words; what this project adds or changes; facts measured before any edit; numbered rules, each with what holds it; the prefix for questions; where the agent stops; and the questions, each with a recommendation and what it blocks.

Builder's argument for tests is that an instruction weakens over a long session and a failing test does not. The opening entry applies the same argument to the collaboration. The agent's reading of the rules exists at first only in its context, where a summary can drop it. Written as numbered rules with a column saying what holds each, the reading becomes something the person can correct before the plan is built on it. When the person answers, the rules that apply to every later session go under "Rules agreed for this project" in `CLAUDE.md` and `AGENTS.md`, and the ones the core can enforce become tests. That is the step the notebook takes when a row produces a rule, taken before the work starts:

| Where the rule lives | Who still sees it |
| --- | --- |
| the conversation | no one, after a context summary |
| the journal's opening entry | the person, before the plan |
| `CLAUDE.md` and `AGENTS.md` | every later session |
| a test in `check.sh` | no one needs to: it holds without being read |

In the Ape Race map workspace, the opening entry ended with eight questions; the answer to one of them ("A CLAUDE.md for this workspace?") produced the thirteen rules every later session there starts from, each pointing back to the journal for its reason.

## Entries

`tools/journal/ENTRIES.md` lists the kinds of entry and what each holds. Each stage of the procedure leaves one:

| Stage | Entry |
| --- | --- |
| 0 (before the plan) | *reading*, then *agreed* once the person answers |
| 1 Brief | *brief*: the description word for word, and where each requirement lands; *research* when the design leans on other work; *intake* for a long input such as a transcript |
| 2 Plan | *plan*, *mockups*: diagrams drawn from the numbers the code will use |
| 3 Read the plan | *for you*: each decision as answer chips, with the default the agent builds on and the alternatives |
| 4 Measure | *measured* |
| 5 Build | *screenshots*: pictures of the running build, with the weak spots named |
| 6 Notebook | *divergences*: plan, what happened, what changed, citing rows |
| 7 Use and triage | *against*: each mockup beside the build; *ready for you*; *your fixes*, one per triage round |
| 8 Publish | *live*, and the Live now page rewritten |

When the plan is approved in advance, stages 2 to 6 run without stopping and the *for you* entry lists the defaults the agent is building on; an answer that differs becomes a triage row citing the question ("T14, from WG-Q8").

Each kind carries the AI-literacy label of the step it asks the reader to take, as the stages do in [`procedure.md`](procedure.md): the brief entry asks the reader to check the agent's restatement (A1), a divergence entry marks the first point where the plan stopped matching what was measured (A3), and a *for you* entry asks the reader to decide how far to rely on each default before reading the result (A0).

## Answer chips

A question for the person is data in the journal's `decisions.json`: an id, the page it sits on, what waits on the answer, and two or more options with exactly one default. `tools/journal/decisions.py` draws each one as a card with a letter per option, the default marked and a box for a note, plus "Go with the defaults for the rest" and "Copy answers". The page saves answers in the person's browser. Where the journal is published as a claude.ai artifact with the `db` capability, it also saves them to the artifact's `answers` collection, so the agent reads them directly. "Copy answers" gives one line (`XX-Q1: A; XX-Q2: B (a note)`) to paste to any agent. `decisions.py --answers` records what came back, and prints which answers need only an *agreed* entry and which also need a triage row because they differ from the default.

The chips came from Idle Game's journal on 2026-10-25 (122 questions by the end), then ToyTalk's and Chumworld Arena's. Before them the person typed answers out ("IG-Q14: A; IG-Q15: C; …", "SP-Q13: alternative"); after them the reply was one line, sent sixteen times: "the answers are in the log, build it". A co-designer could answer on a phone, and the build could go ahead on the defaults while a question stayed open.

## Live now, and a page per round

The journal keeps a fixed Live now page: what is deployed, from which commit, what changed since the deploy before, and a screenshot of each change. It is rewritten on every deploy, and its `data-commit` must match the newest *live* entry's. Each planning round gets its own page and a link in the nav. In CHUMWORLD the person asked for a page describing "whats deployed right now" and then for it to be rewritten after each deploy; in Idle Game they asked "which tab is this planning round on?" Both are now the template's default, and a journal with an address is republished after every entry.

## What the check establishes

`scripts/journal_check.py`, step 8 of a project's check, fails when a build with a description has no journal, when the opening entry is missing or still blank, when an entry has no id or kind, when a *person* row in `SECOND-ORDER.md` is not named in the journal, when the journal cites a notebook or triage row that does not exist, when an entry in the journal's last commit is gone, when `decisions.json` gives a question no default or two or the chips do not match it, when an answer is cited by no *agreed* entry or an override by no triage row, when a deploy after mockups has no *against* entry, when Live now names another commit than the newest deploy, when a *research* entry links no source or an *intake* entry quotes nothing, and when the opening entry skips a project the brief lists under References. On CI, where the journal is usually absent, a missing journal is reported and not failed. `scripts/prove-checks.sh` plants seventeen defects against it.

It checks form and links. It cannot tell whether an entry is right, whether a picture shows what its caption says, or whether the agent left something out.

## What the journal cannot show

The agent writes the journal about its own work. It chooses the shots, the weak spots and the wording, and a well-made page can raise confidence beyond what the checks support. The person's use of the tool, with a case worked out by hand, stays the check that can catch what the journal leaves out. A *review* entry, in which the person or a second model checks an entry against the build and says what it could not verify, is the journal's way of recording that check.

An entry written after the fact is a different record from one written as the work happened. It carries the kind *retrospective* and names its sources.

## Where it came from

Peter's Ape Race kept a design-journal skill in its repository: a home page of cards and a timeline, one page per map, entries newest first and never removed, screenshots of the running game. The Ape Race map workspace built on it with a reading entry, decisions with defaults, divergence entries and a numbered request scheme, and Long Time Comin' adopted that shape from its sixteenth round. The template's journal is written for Builder from those, with the opening entry required.
