# Instructions for a coding agent in the Builder reference repository

`CLAUDE.md` holds the same rules. This file is for work on the reference repository itself. A project copied from `template/` has its own `CLAUDE.md`.

1. `template/` is what people copy. `examples/minimal/` is a copy of it with one small rule. Files listed in `scripts/check-sync.sh` must stay byte-identical between the two, and `BUILDER-SPEC.md` at the root must match `template/BUILDER-SPEC.md`.
2. Keep the three categories apart in every document: Builder requirements, reference defaults, project decisions. Do not promote a convention from one tool into a requirement.
3. Run `./scripts/check.sh` before handing off. It checks the template, the example, the sync, the links, and that each planted defect is caught.
4. A new check is not finished until `scripts/prove-checks.sh` plants a defect it must catch and sees it fail.
5. Do not describe a check as proving more than it does. The browser check describes one path in three engines; the mutation score describes how much current behaviour the tests pin down.
6. Do not name the paper's title or venue in this repository while it is under review.
7. Do not push, tag or publish a release on your own judgement.
