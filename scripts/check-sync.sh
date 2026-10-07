#!/usr/bin/env bash
# The files a project inherits from template/ must be the same in
# examples/minimal/, so the example demonstrates the template people copy.
set -euo pipefail
cd "$(dirname "$0")/.."
SHARED="
.gitignore
CLAUDE.md
AGENTS.md
BUILDER-SPEC.md
scripts/build.sh
scripts/check.sh
scripts/serve.py
scripts/setup.sh
scripts/mutants.sh
scripts/wasm_imports.py
tests/browser/check.py
crates/core/tests/boundary.rs
crates/shim/Cargo.toml
crates/core/Cargo.toml
Cargo.toml
"
bad=0
for f in $SHARED; do
  if ! cmp -s "template/$f" "examples/minimal/$f"; then
    echo "differs: template/$f examples/minimal/$f"; bad=1
  fi
done
if ! cmp -s BUILDER-SPEC.md template/BUILDER-SPEC.md; then
  echo "differs: BUILDER-SPEC.md template/BUILDER-SPEC.md"; bad=1
fi
[ "$bad" -eq 0 ] && echo "template and example agree on $(echo $SHARED | wc -w | tr -d ' ') shared files"
exit "$bad"
