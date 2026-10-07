# Adopting Builder

## Tools Builder suits first

Builder suits a small browser application whose behaviour can be stated apart from its interface, so that the rules fit in a deterministic core with fast tests, and whose deployment benefits from static hosting. Classroom tools are a good first case: a teacher can describe what the tool should do, the rules are small enough to test exhaustively on hand-computed cases, and a static page needs no server to configure, secure or pay for.

Examples built this way include an assignment-perturbation workbench, a PDF redactor that runs in the browser, warm-ups and exit tickets drawn from a question bank, practice results aggregated by topic from files students hand in, rubric-based feedback drafts, and several games whose rules (a fight simulation, a city's flood, a belt of cups) live in the core.

## Four moves to start

1. Choose a tool whose core behaviour you can state without describing the screen.
2. Put those rules in the core, with tests whose expected values you worked out by hand.
3. Use the plan and the second-order notebook to bring decisions into view while the agent works.
4. Make deployment wait for a person-led check: use the tool, compare a hand-computed case, then deploy and run the browser check against the live page.

## Where the default build stops

The default build is static files with no off-origin request on load, and some features cannot be met that way:

- **Shared state between people while the tool is in use.** A help request routed to a teacher, live class analytics, or a teacher watching a group needs information to reach another person's device. A static tool can sometimes meet the purpose by letting people move files (students save a result file; the teacher opens all of them), and that is a change to the feature the person has to accept.
- **A live model.** A feature that asks a generative model for output at the moment of use needs a server or a third-party call. A static tool can sometimes meet the purpose by generating the content in advance and shipping it as a file, or by having the teacher write it. Feedback Drafts does the second: the teacher writes the comment bank once, and the tool composes drafts from it.
- **Accounts, identity or access control across people.**
- **A third-party service** such as a whiteboard or a document store.

A project that needs one of these can still keep its rules in a tested core. The rest of the design (the server, its data handling and its approvals) needs its own checks, and the browser check's off-origin rule has to be changed deliberately and recorded in `BUILDER-SPEC.md`.

## What you need

Rust with the `wasm32-unknown-unknown` target, `wasm-bindgen-cli` at the pinned version, Python 3 with Playwright for the browser check, a static host, and a coding agent that reads `CLAUDE.md` or `AGENTS.md`. The agent can do the build work. The person supplies the brief, reads the plan, uses the result, and decides the boundaries the brief left open.
