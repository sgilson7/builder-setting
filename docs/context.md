# Context: reading Builder without re-reading it

Every call a coding agent makes re-reads its whole context, so a token read once is paid for on every later call until the context is compacted. In six Builder projects measured in November 2026, start-up alone took the context from 42k to between 125k and 241k tokens before the plan. Long sessions then ran at 306k–377k on average, with peaks above 950k, and 43–52% of all tokens re-read were context above 200k. This page says how a Builder project keeps that down without dropping any of Builder's rules: it asks for the few pieces it needs, keeps what it learned in a short file, and measures the result.

## How to read Builder

Builder's documents and code are cut into **cards** by `tools/ask.py`:
- one card per section of a document;
- one per spec row (`spec.D20`) and one per `CLAUDE.md` rule (`claude.r14`);
- one per function, Rust item or test in the code, naming `path:line`.

Cards are cut from the files each time the script runs, so they are never stale.

- `python3 tools/ask.py --start` prints the start pack: the cards an opening entry needs, about 2.5k tokens.
- `python3 tools/ask.py "your question"` prints the three cards that best answer it; `--code` or `--docs` narrows to one kind, `-k 5` gives more.
- `python3 tools/ask.py --card spec.D20` prints one card in full.

Open a Builder file only when a card points to it, and then only the lines it names. Read `CLAUDE.md`, `BRIEF.md`, `BUILDER-SPEC.md` and `GLOSSARY.md` in full as before (rule 1). Cite a card in the journal or in `STATE.md` as `card:<id>`; `scripts/journal_check.py` and `scripts/context_check.py` fail on a citation to a card that does not exist.

The ranking is keyword search (BM25) over the cards, in the standard library, so it works offline and with any agent. `tests/builderqa.json` in the reference repository holds real start-up questions with the cards that answer them, and the reference check fails when a right card falls out of the top five.

## Digests of earlier projects

A project named under References in `BRIEF.md` is read through its **digest** when it has one: one page saying what the project is, what worked, what to copy, and which files and cards hold it. Make one with `python3 tools/digest.py ../ape-race --out ../refs/ape-race.md`, then fill in its "What to copy" section once; every later project reads that page instead of the project's transcripts. `ask.py` searches digests in `$BUILDER_REFS` or `../refs/` as `ref.<name>` cards. `python3 tools/digest.py --check FILE` checks a digest's form.

## STATE.md, and compaction

`STATE.md` is the project's long-term memory, at most two pages:
- where the build is, naming its latest commit;
- the decisions in force, with their IDs;
- what is next;
- the files and line ranges the next step needs (`path:line`), not their contents.

Rewrite it at each milestone (a stage boundary, a finished feature, a deploy), after each request recorded in `TRIAGE.md`, and before a handoff. When the context passes about 200k tokens, rewrite it, commit, and ask the person to type `/compact`: an agent cannot compact itself. After a compaction or in a new session, read `STATE.md` and ask for cards; do not re-read files it already summarises. In Claude Code, `.claude/settings.json` runs `tools/context/after_compact.py` after every compaction, and it puts `STATE.md` back in front of the agent. `./scripts/check.sh` and `./scripts/quick-check.sh` keep their full output in `notes/runs/` and print only what passed, the step reached and the first errors (`BUILDER_LOUD=1` prints everything; CI does). Other long commands go through `./scripts/quiet.sh`, which does the same.

`scripts/context_check.py` checks that `STATE.md` stays within two pages and names a commit that exists. It also checks that every card the file cites exists, and fails when `TRIAGE.md` changed after `STATE.md` (or a filled-in `HANDOFF.md`) was last rewritten.

## Your own work: by pointer

Builder's cards stop being the cost once a project is under way: in the first trial, no Builder file or card was needed after the opening entry, and the context grew from the work itself (files written, code read, journal edits). The agent gets its own work back by pointer (rule 24): `STATE.md` names the files and line ranges the next step needs, and after a compaction the agent opens only those. Before reading a long file again, it reads the file's outline and opens one part.

Round four tried a work index instead (`tools/ask.py --mine` over the project's journal, notebook, commits, code and tool results, with optional embeddings). In the platformer trials the agent with the index asked it once in 208 calls and re-read 29 of its own files after compactions anyway. Round five dropped it: Builder ships the plain arm, with a 300k compaction cap. The index is kept on the branch `fold-round-4-memory`.

## Hooks

`template/.claude/settings.json` sets a compaction cap of 300k tokens (`CLAUDE_CODE_AUTO_COMPACT_WINDOW`) and runs two small scripts in `tools/context/`:

- `after_compact.py`, after a compaction: puts `STATE.md` back in front of the agent.
- `after_tool.py`, after each tool call: the first time the context passes 200k tokens (`BUILDER_CONTEXT_WARN`, or two thirds of a lower compaction cap), and at each further 100k, it tells the agent to rewrite `STATE.md` and ask for `/compact`. Claude Code compacts a little under its cap (at about 167k under a 200k cap, and 88–93k under a 120k cap, in the platformer trials), so under the template's 300k cap the warning at 200k leaves room to rewrite `STATE.md` and finish a step first.

A hook's message reaches the agent as context beside the tool's result, so the advice arrives with the long result it is about; it is aimed at the next time.

## Editing in place

Change anything longer than about 200 lines with edits, not by writing it again whole (rule 25): a rewrite sends all of it again, and both copies stay in the context. In the first trial, one 340-line template was rewritten whole three times.

## Measuring

`python3 tools/tokens.py` reads this session's transcript and adds a row to `notes/tokens.md`:
- the context at the first plan or journal entry;
- the peak and mean context;
- the number of compactions;
- the total re-read.

A handoff quotes the latest row. The numbers at the top of this page came from the same measurements.

The trial harness that measured Builder versions against each other (`harness/`) is kept on the branch `fold-round-4-memory`.

## What this does not change

Every Builder requirement, default and check stays as it was. The core, shim and page rules, the nine stages, the journal, the second-order notebook, triage and the deploy grant all work the same way. This page changes how the agent finds them and its own work, and how much of either it carries.
