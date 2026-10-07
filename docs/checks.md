# What each check establishes

`./scripts/check.sh` runs six steps. Each one establishes something specific, and each leaves something for another check or a person. The right-hand column is the part to remember.

| Check | Command | Establishes | Does not establish |
| --- | --- | --- | --- |
| Format and lint | `cargo fmt --check`; `cargo clippy -D warnings` | the code is formatted and clippy finds nothing | anything about behaviour |
| Core suite | `cargo test --workspace` | the rules hold on the cases the tests state | that the stated cases are the intended behaviour; that is the brief's and the person's |
| Boundary tests | `crates/core/tests/boundary.rs`, inside `cargo test` | no I/O name and no float, hash map or clock in core source; no dependency outside the allowlist; no branch, loop or `?` in the shim; no numeric literal, arithmetic or network API in page JavaScript; no absolute URL in `web/`; a CSP on every page | a rule hidden in the page by other means (a string comparison, a lookup table); the scans read source text, not meaning |
| Release build | `scripts/build.sh` | the module builds with the pinned `wasm-bindgen` | |
| WebAssembly import audit | `scripts/wasm_imports.py dist` | the module's imports, each followed into the generated glue and any snippet, name no network API; the glue holds one `fetch`, which loads the module; when `wasm-tools` is installed, its import list matches the script's | the page's own JavaScript; vendored modules the page loads separately |
| Browser check | `tests/browser/check.py` | in Chromium, Firefox and WebKit, on load, a 10 s idle and the project's interactions: no uncaught error, console error, CSP violation, off-origin request, WebSocket, popup, worker or service worker; the interactions' hand-computed values were drawn | features the interactions never start; behaviour on another day, browser version or network |

## Show that a check can fail

A check that has only been seen passing has not been shown to check anything. `scripts/prove-checks.sh` copies `examples/minimal`, plants one defect at a time, runs the check meant to catch it, and requires that check to fail with the message that names the defect. The planted defects include a float, a `println!` and a hash map in the core, a dependency outside the allowlist, a branch in the shim, a copy of a rule in the page, an absolute URL, a missing CSP, an import that reaches `sendBeacon`, an off-origin fetch assembled at run time (once with the CSP in place and once without it), a console error, and a broken rule seen by both the core suite and the browser check.

One finding from writing that script: with the CSP in place, the browser blocks a forbidden fetch before it becomes a request, so a check that only listens for requests sees nothing. The browser check therefore records CSP violations as their own failure.

For each new behaviour test in a project, do the same by hand: break the behaviour once, watch the test fail, restore it, and note the message in `SECOND-ORDER.md`.

## Mutation testing

Mutation testing deliberately makes small changes to the code and reruns the tests. A planted change is caught when those tests fail.

```bash
cargo install cargo-mutants --locked
./scripts/mutants.sh
```

It is kept out of `check.sh` because it takes minutes. The share caught measures how much current behaviour the tests pin down. It is not a bug rate, and it says nothing about whether that behaviour is the intended one. Each missed mutant is one of three things: an equivalent change that cannot be detected, a missing test for a rule the brief states, or a boundary the brief has not decided. The first needs nothing; the second needs a test; the third needs the person.

## Deployed pages

After the person deploys, run the same browser check against the live origin:

```bash
BUILDER_ORIGIN=https://example.github.io/my-tool python3 tests/browser/check.py
```

A deploy is not finished until that passes.

## What stays with a person

Whether the tool does what the brief asked, whether its content is right, whether the boundaries the tests pin down are the intended ones, and whether the tool is fit for a class. The checks narrow what a person has to read; they do not replace the reading.
