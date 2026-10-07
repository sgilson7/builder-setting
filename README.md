# Builder

Builder is a reusable technical setting for small browser tools built with coding agents: application rules live in a fast-tested Rust core, a thin WebAssembly shim only moves values across the browser boundary, and a static page renders the result.

The separation gives the agent fast feedback while it builds and leaves a finished artifact that can be checked at the core, the WebAssembly boundary and the browser page. The core's tests run in seconds without a browser, so the agent can rerun all of them after every change. The module's imports show what the compiled code can reach. The browser check shows what the page did on a defined path in three engines.

![Builder's three layers: core, shim and page, with the check that watches each](docs/img/architecture.svg)

## Start a new tool

```bash
git clone https://github.com/sgilson7/builder-setting.git
cp -R builder-setting/template my-tool
cd my-tool
git init
./scripts/setup.sh        # once: Playwright and three browser engines
./scripts/check.sh        # the blank template passes before you change anything
```

Then write `BRIEF.md` and point your coding agent at the directory. It reads `CLAUDE.md` or `AGENTS.md` first, and those send it to `BRIEF.md` and `BUILDER-SPEC.md`. It does not need the research paper.

You need Rust with the `wasm32-unknown-unknown` target, `wasm-bindgen-cli` 0.2.127, and Python 3.

```bash
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.127 --locked
```

## The contract

The full contract is [`BUILDER-SPEC.md`](BUILDER-SPEC.md). It separates **Builder requirements**, which define Builder, from **reference defaults**, which this repository chose so that a copy works at once, and from **project decisions**, which stay with the person building the tool. The requirements in short:

1. The core holds every application rule and performs no input or output.
2. The core's dependencies are on an allowlist.
3. The shim translates values and decides nothing.
4. The page draws what the core returns and does not recompute a rule.
5. The default build is static files and makes no off-origin request while it loads and idles.
6. One command runs the whole check, and CI runs the same command.
7. The agent works through the nine-stage procedure and does not deploy.

When a rule seems to block necessary work, the agent stops and says so rather than loosening the check.

## The check

```bash
./scripts/check.sh
```

| Step | What it establishes |
| --- | --- |
| `cargo fmt --check`, `cargo clippy -D warnings` | the code is formatted and lint-clean |
| `cargo test` | the core's rules hold on the cases the tests state; the boundary tests find no I/O, no dependency outside the allowlist, no decision in the shim and no rule in the page |
| release WebAssembly build | the module builds with the pinned `wasm-bindgen` |
| `scripts/wasm_imports.py` | the module's imports, each followed into the generated glue, name no network API; the one `fetch` in the glue loads the module |
| `tests/browser/check.py` | in Chromium, Firefox and WebKit, the page loaded, idled and ran its interactions with no page error, console error, CSP violation, off-origin request, WebSocket, popup or worker |

A pass describes what happened on that path. It does not show that no feature can ever reach the network: a feature the interactions never start is a feature the check never saw. [`docs/checks.md`](docs/checks.md) says what each check establishes and what still needs a person.

[`scripts/prove-checks.sh`](scripts/prove-checks.sh) plants defects in a copy of the minimal example, one at a time, and requires the check meant to catch each one to fail. Mutation testing (`scripts/mutants.sh` in a project) is a separate, slower audit.

## The procedure

| Stage | Who | Label | File |
| --- | --- | --- | --- |
| 1 Brief | person | C1 Frame the problem and set the rules; B1 Establish context | `BRIEF.md` |
| 2 Plan | agent | B2 Require step-by-step justification | `PLAN.md` |
| 3 Read the plan | person | C3 Interrogate the claim | `PLAN.md` |
| 4 Measure | agent | B2 | `MEASUREMENTS.md` |
| 5 Build with tests | agent | B2 | code and tests |
| 6 Second-order notebook | agent | B3 Build in self-questioning | `SECOND-ORDER.md` |
| 7 Use and triage | person | C4 Verify against hand-computed cases | `TRIAGE.md` |
| 8 Deploy and check | person | C4 | `BUILDER_ORIGIN=… tests/browser/check.py` |
| 9 Handoff | agent | C5 Consolidate in your own words | `HANDOFF.md` |

The labels name steps from two AI-literacy procedures taught to computing students: the four parts of a strong prompt (B1–B4) and working a problem with a chatbot (C1–C5). [`docs/procedure.md`](docs/procedure.md) describes each stage.

## Examples and prompts

- [`examples/minimal/`](examples/minimal/) is a bounded counter: one rule in the core, its tests, the shim, a page, a browser interaction and the full check. It exists to show the parts, and nothing more.
- [`prompts/`](prompts/) holds the prompts for starting from a brief, reviewing a plan and auditing the boundary, and a template for writing a prompt set.
- [`prompts/sets/C-feedback-drafts.md`](prompts/sets/C-feedback-drafts.md) is a prompt set written from a teacher request in a co-design program. A fresh agent session built [Feedback Drafts](https://github.com/sgilson7/feedback-drafts) from it, starting from `template/`. The session record is in that repository.

## Documentation

[Architecture](docs/architecture.md) · [Procedure](docs/procedure.md) · [Checks](docs/checks.md) · [Adoption](docs/adoption.md) · [Mapping to the paper](docs/paper-mapping.md) · [Releases](docs/release.md)

## Citation

Cite the version you used. [`CITATION.cff`](CITATION.cff) and [`CITATION.bib`](CITATION.bib) describe this repository. A paper describing Builder is under review, and its reference will be added here when it can be cited.

## License

MIT. See [`LICENSE`](LICENSE).
