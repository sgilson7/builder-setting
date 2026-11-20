#!/usr/bin/env bash
# The reference repository's full check. CI runs this same file.
#
# 1. the template and the example agree on the files a project inherits
# 2. every relative link in the Markdown resolves
# 3. the default style pack stays inside template/styles/
# 3a. Builder's cards are in order, and BuilderQA finds a right card in the top five for each question
# 3b. the work index answers WorkQA at or above its floor, and the trial harness passes its own test
# 4. the blank template passes its own check, and each of its breaks is caught
# 5. the minimal example passes its own check, and each of its breaks is caught
# 6. the office-intake, codebase-guide and manim kits' tests pass
# 7. each kit's core code passes the project's checks inside a copy of the example
# 8. each planted defect is caught by the check meant to catch it
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
step() { printf '\n\033[1m#### %s\033[0m\n' "$*"; }

PY="${BUILDER_PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY=python3; fi
fi
export BUILDER_PYTHON="$PY"

step "sync: template and example"
./scripts/check-sync.sh

step "links"
"$PY" scripts/check-links.py

step "style leak: scripts/check-style-leak.py"
"$PY" scripts/check-style-leak.py

step "cards: template/tools/ask.py --check, and BuilderQA (tests/builderqa.json)"
"$PY" template/tools/ask.py --check
"$PY" template/tools/ask.py --qa tests/builderqa.json

step "work index: tools/ask.py --mine over examples/minimal (tests/workqa.json), and the trial harness's own test"
BUILDER_PROJECT=examples/minimal "$PY" template/tools/ask.py --mine --qa tests/workqa.json
"$PY" -m unittest discover -s harness/tests
"$PY" -m unittest discover -s tests -p test_context_tools.py

step "template: ./scripts/check.sh"
(cd template && ./scripts/check.sh)

step "template: scripts/break_tests.py"
(cd template && "$PY" scripts/break_tests.py)

step "examples/minimal: ./scripts/check.sh"
(cd examples/minimal && BUILDER_LOUD=1 ./scripts/check.sh)   # loud: a quiet run would leave a log in the example, and WorkQA reads its notes

step "examples/minimal: scripts/break_tests.py"
(cd examples/minimal && "$PY" scripts/break_tests.py)

step "kits/office-intake: its tests"
"$PY" -m unittest discover -s kits/office-intake/tests

step "kits/codebase-guide: its tests"
"$PY" -m unittest discover -s kits/codebase-guide/tests

step "kits/manim: its tests (no Manim needed)"
"$PY" -m unittest discover -s kits/manim/tests/manim

step "kits: scripts/check-kits.sh"
./scripts/check-kits.sh

step "planted defects: scripts/prove-checks.sh"
./scripts/prove-checks.sh

printf '\n\033[1mREFERENCE REPOSITORY CHECK PASSED\033[0m\n'
