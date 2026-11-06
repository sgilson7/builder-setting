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
- the cards the next session needs.

Rewrite it at each milestone (a stage boundary, a finished feature, a deploy) and before a handoff. After a compaction or in a new session, read `STATE.md` and ask for cards; do not re-read files it already summarises. In Claude Code, `.claude/settings.json` runs `tools/context/after_compact.py` after every compaction, and it puts `STATE.md` back in front of the agent. Long tool output goes to a file through `./scripts/quiet.sh`, which prints only what passed, what failed and the first error.

`scripts/context_check.py` checks that `STATE.md` stays within two pages and names a commit that exists. It also checks that every card the file cites exists.

## Measuring

`python3 tools/tokens.py` reads this session's transcript and adds a row to `notes/tokens.md`:
- the context at the first plan or journal entry;
- the peak and mean context;
- the number of compactions;
- the total re-read.

A handoff quotes the latest row. The numbers at the top of this page came from the same measurements.

To test a version of Builder itself, [`harness/`](../harness/README.md) runs a build in a clean folder with that version and reports how far token use was held down, beside the earlier projects, and each place the agent did not follow these rules, with what it cost.

## What this does not change

Every Builder requirement, default and check stays as it was. The core, shim and page rules, the nine stages, the journal, the second-order notebook, triage and the deploy grant all work the same way. This page changes only how the agent finds them.
