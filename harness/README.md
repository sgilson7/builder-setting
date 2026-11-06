# Trial harness

An instrument for testing a version of Builder: run a build inside it the way you normally would, then measure how far token use was held down and find where the agent did not follow Builder. It is not part of the template, and a trial's agent never sees it: `trial.sh` leaves `harness/` out of the copy of Builder it puts in the trial.

## Run a trial

```bash
harness/trial.sh rhythm-1                       # ~/Documents/BuilderTrials/rhythm-1, then launches claude there
harness/trial.sh bridge-1 --refs ~/Documents/Builder/refs   # copy game digests in as refs/
harness/trial.sh bridge-cap --compact-window 200000         # also compact at about 200k tokens
```

`trial.sh` does four things before it launches `claude`:
- copies Builder at this repository's current commit into `builder/`, so commit first; uncommitted changes are left out, and it says so;
- writes `OPENING.md` for you to paste, which is the folder opening with Builder already in place;
- installs hooks in `.claude/settings.json`: one puts `STATE.md` back after every compaction, and two log each session start and compaction to `harness/events.jsonl`;
- records the commit, branch, Claude Code version and settings in `harness/trial.json`.

Then build as you normally would: paste the opening with its slots filled, then your description. Answer chips, play, ask for changes. The trial can run over several sessions in the same folder.

`--compact-window N` sets `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, so Claude Code compacts when the context nears N tokens, less its summary buffer. Without it, compaction happens where it always has, and only the procedure (rule 21) asks for `STATE.md`. Run one trial each way to see what the cap costs and saves.

## Analyse it

```bash
python3 harness/analyze.py ~/Documents/BuilderTrials/rhythm-1          # report, metrics and the project's checks
python3 harness/analyze.py ~/Documents/BuilderTrials/rhythm-1 --full   # also ./scripts/check.sh in the project
```

It reads every transcript Claude Code kept for the trial folder and writes `harness/report.md` and `harness/metrics.json` in it. It also adds a row to `~/Documents/BuilderTrials/index.md`, so trials sit side by side. The report has six parts:

1. **Token use** beside the baseline: the median of six projects built before the cards (`baseline.json`). It gives the context at the first plan, the peak, the mean, compactions, the total re-read, the start-up share, and the share above 200k.
2. **How Builder was read.**
   - `ask.py` calls, split into the start pack, questions and single cards.
   - Every read of a file under `builder/`: whether a card pointed to it first, whether it was a range or the whole file, its size, and the tokens it carried. A read carries its size times the calls it stayed in context before a compaction.
   - Transcripts read.
3. **Memory and output.** `STATE.md` rewrites set against compactions, whether the hook put `STATE.md` back, long tool outputs, check runs with and without `quiet.sh`, and images.
4. **Process.**
   - The order of the first writes: brief, journal, plan, code.
   - Answer-chip runs and check runs.
   - Subagents, set against the brief's Autonomy.
   - Deploy commands, set against the brief's grant.
5. **The project's checks, run now:** journal, context, notebook and test tags; with `--full`, the whole `check.sh`.
6. **Where Builder slipped.** Each finding has a severity, the call it happened at, the evidence and the tokens it carried, ranked so the costliest come first.

`python3 harness/analyze.py --session FILE.jsonl` gives the same report for one old session, without the checks. `--baseline FILE...` rebuilds `baseline.json`.

## What it cannot see

The harness can't tell why the agent did something. A read of a Builder file whose path no earlier card printed counts as "no card first", even if the agent had a good reason. Token counts come from the usage figures Claude Code records for each call. Image tokens are counted only as images, and a subagent's tokens are its own transcript's, which the report counts but does not add to the main session's figures. Severity is a judgement written into `analyze.py`. Read the evidence before acting on a finding.
