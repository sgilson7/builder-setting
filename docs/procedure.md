# The nine-stage procedure

Each Builder build follows nine stages. The person owns four of them and the agent owns five. Each stage carries a label naming a step from two AI-literacy procedures taught to computing students: the four parts of a strong prompt (B1–B4) and working a problem with a chatbot (C1–C5). The labels are used as a naming scheme, so that a student who has met the steps in a mathematics course can recognise the same move when directing a coding agent.

| Stage | Who | Label | What happens | File |
| --- | --- | --- | --- | --- |
| 1 Brief | **person** | C1 Frame the problem and set the rules; B1 Establish context | Define the tool, the conditions for done, the decisions that stay with the person, and how much the agent may do alone. Paste the original request word for word. | `BRIEF.md` |
| 2 Plan | agent | B2 Require step-by-step justification | Turn the brief into decisions in build order, each with its reason and the test that will show it holds. Then stop. | `PLAN.md` |
| 3 Read the plan | **person** | C3 Interrogate the claim | Accept the plan, revise it, or answer its open questions. A plan that is not approved goes back to stage 2. | `PLAN.md` |
| 4 Measure | agent | B2 | Record the starting state: toolchain, test count, check result. | `MEASUREMENTS.md` |
| 5 Build with tests | agent | B2 | Implement in small steps. Each core rule lands with its test, and each new test is broken once and seen failing. | code, tests |
| 6 Second-order notebook | agent | B3 Build in self-questioning | Record assumptions, surprises, divergences from the plan, and work the person must do, when they are noticed. | `SECOND-ORDER.md` |
| 7 Use and triage | **person** | C4 Verify against hand-computed cases | Use the build. Compare at least one result with a case worked out by hand. File each concrete change. Triage rows return to stage 5. | `TRIAGE.md` |
| 8 Deploy and check | **person** | C4 | Decide to deploy, deploy, and run the browser check against the live origin. | `BUILDER_ORIGIN=… tests/browser/check.py` |
| 9 Handoff | agent | C5 Consolidate in your own words | Record what changed, what passed, what remains, and what the next session must not assume. | `HANDOFF.md` |

B4 (plan the corrective dialogue) has no stage of its own. A prompt set writes it out: when a check fails, record the file and line, what was expected and what happened, and fix the rule in the core. C2 (elicit one step with its rule named) is done by stage 2's reasons.

## Approving the plan in advance

A person may approve the plan in advance and let the agent run through stages 2 to 6 and 9 without stopping, as the prompt sets in `prompts/sets/` do. That is faster, and it defers the person's review of the plan to after the build. When the stops are set aside, make stage 7 the gate: the person uses the tool and checks a hand-computed case before stage 8. Record in `BRIEF.md` that the plan was approved in advance.

## Who deploys

The agent does not deploy on its own judgement. In a project where the person has explicitly told the agent to deploy, record that instruction in `BRIEF.md`, and still run the browser check against the live origin afterwards.
