# Releases

## Versions

Version 0.1.0 is the first public version of the template, the minimal example and the checks. A version is a git tag on the commit whose `./scripts/check.sh` passed in CI.

## The live example

`scripts/publish-example.sh` builds `examples/minimal` and force-pushes it to the `gh-pages` branch, which GitHub Pages serves. Run it after `./scripts/check.sh` passes, then run the example's browser check against the live origin with `BUILDER_ORIGIN` set. Publishing is the person's action.

## A frozen snapshot for the paper

The paper should refer to one immutable snapshot. When the camera-ready version is due:

1. Run `./scripts/check.sh` and confirm CI passed on the commit.
2. Tag the commit with an annotated tag whose name says it is the paper's snapshot, and create a GitHub release from that tag.
3. Archive the release (for example through Zenodo's GitHub integration) so that it has a DOI.
4. Put the DOI and the tag in `CITATION.cff`, `CITATION.bib` and the paper.

Choosing the tag's name, creating the release and archiving it are the author's actions.

## An anonymous artifact for review

A venue with double-anonymous review may need an artifact that does not identify the authors. This repository is public under its author's account, so it is not anonymous, and the review version of the paper should not link to it. Instead:

1. Make an anonymised copy of a fixed commit with a service built for the purpose (such as anonymous.4open.science), or export the tree without its git history.
2. Run `scripts/anonymity-check.sh <directory>` on the export. It lists every line that names the author, the account, the institution or a personal site, and exits non-zero if it finds one.
3. Remove or neutralise each line it lists: `LICENSE`, `CITATION.cff`, `CITATION.bib`, the clone URL in `README.md`, the Feedback Drafts link, and anything else it reports.
4. Check that the anonymised copy still passes `./scripts/check.sh`.
