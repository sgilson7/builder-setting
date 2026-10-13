# The nine-stage procedure

Each Builder build follows nine stages. The person owns four of them and the agent owns five. Each stage carries a label naming a step from two AI-literacy procedures taught to computing students: the four parts of a strong prompt (B1–B4) and working a problem with a chatbot (C1–C5). The labels are used as a naming scheme, so that a student who has met the steps in a mathematics course can recognise the same move when directing a coding agent.

| Stage | Who | Label | What happens | File |
| --- | --- | --- | --- | --- |
| 1 Brief | **person** | C1 Frame the problem and set the rules; B1 Establish context | Describe the tool in your own words. The description goes into the brief word for word; the rest of the brief (done means, decisions that stay with the person, accessibility, style, words, autonomy) is written from it, by the person or by the agent for the person to read. Terms from the person's field go into `GLOSSARY.md`. | `BRIEF.md`, `GLOSSARY.md` |
| 2 Plan | agent | B2 Require step-by-step justification | Turn the brief into decisions in build order, each with its reason and the test that will show it holds. Then stop. | `PLAN.md` |
| 3 Read the plan | **person** | C3 Interrogate the claim | Accept the plan, revise it, or answer its open questions. A plan that is not approved goes back to stage 2. | `PLAN.md` |
| 4 Measure | agent | B2 | Record the starting state: toolchain, test count, check result. | `MEASUREMENTS.md` |
| 5 Build with tests | agent | B2 | Implement in small steps. Each core rule lands with its test, and each new test is broken once and seen failing. | code, tests |
| 6 Second-order notebook | agent | B3 Build in self-questioning | Record assumptions, surprises, divergences from the plan, and work the person must do, when they are noticed. | `SECOND-ORDER.md` |
| 7 Use and triage | **person** | C4 Verify against hand-computed cases | Use the build. Compare at least one result with a case worked out by hand. Each request, in plain words, becomes a numbered row (T1, T2 …); the commit that answers it cites the number. Triage rows return to stage 5. | `TRIAGE.md` |
| 8 Publish and check | **person**, or the agent when the brief grants it | C4 | Publish with `scripts/publish.sh` (it refuses uncommitted changes and records the commit it was built from) and run the browser check against the live address. | `BUILDER_ORIGIN=… tests/browser/check.py` |
| 9 Handoff | agent | C5 Consolidate in your own words | Record what changed, what passed, what remains, and what the next session must not assume. | `HANDOFF.md` |

B4 (plan the corrective dialogue) has no stage of its own. A prompt set writes it out: when a check fails, record the file and line, what was expected and what happened, and fix the rule in the core. C2 (elicit one step with its rule named) is done by stage 2's reasons.

## Approving the plan in advance

A person may approve the plan in advance and let the agent run through stages 2 to 6 and 9 without stopping, as the prompt sets in `prompts/sets/` do. That is faster, and it defers the person's review of the plan to after the build. When the stops are set aside, make stage 7 the gate: the person uses the tool and checks a hand-computed case before stage 8. Record in `BRIEF.md` that the plan was approved in advance.

## Who deploys

The agent does not deploy on its own judgement. In a project where the person has explicitly told the agent to deploy, record that instruction in `BRIEF.md`, and still run the browser check against the live origin afterwards.

## Starting from a description

The projects behind this round of Builder mostly began as a few paragraphs of plain prose from a friend of the author who does not write code. The author rewrote each into a brief in the shape above and started the build. [`prompts/start-from-description.md`](../prompts/start-from-description.md) gives that rewriting step to the agent: a person who does not write code clones the repository, starts an agent in it, and describes the tool. The agent keeps the description word for word at the top of the brief, writes the rest of the brief from it, asks only what blocks the build, and records every other decision in the notebook. The person's later requests, also in prose, become numbered triage rows.

## Numbered requests and experiments

- **Numbered requests.** Peter's commits cite "(feedback 1)" through "(feedback 27)" and TRIAGE rows; code comments cite the row that asked for them. The habit stopped in his last fourteen commits, which is why `scripts/publish.sh` writes "Built from <commit>" itself and does not leave it to memory.
- **TRY commits.** An experiment can go live from a branch as one commit whose message says what it tries and how to undo it: "TRY: the sky follows the exact speed. Built from branch try/speed, commit 04b9d26. Revert this commit to go back." An experiment the person keeps becomes a TRIAGE row with the disposition *try*, then *done*.

## Recording failure

A divergence row says what was assumed, what turned out to be true and what changed. Three kinds recur and are worth naming in the row: *reversion* (the build quietly swaps in the textbook rule the design departs from), *a check that cannot fail* (the form is right and the assertion is empty, or the test compares a value with the function under test), and *a miscount* (a count or a size off by one, a unit helper misread). The rule each produced goes into `CLAUDE.md` when it applies to every later session.

## Several agents at once

Agents running in parallel on one machine have collided in three ways: `git stash -u` in one session took another session's files (Raiders), a fixed port served another game's screenshots (Ribbit King), and cargo's shared package lock stalled a session for half an hour (Slushline). Give each agent its own working copy, serve on port 0, and test from a copy taken with `git archive` when another session may be editing.
