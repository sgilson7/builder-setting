#!/usr/bin/env bash
# Show that each Builder check can fail.
#
# A check that has only been seen passing has not been shown to check
# anything. For each planted defect below, this script copies
# examples/minimal into a scratch directory, plants the defect, runs the one
# check meant to catch it, and requires that check to FAIL with the message
# that names the defect. A planted defect that passes is a broken check, and
# this script exits non-zero.
#
#   ./scripts/prove-checks.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/examples/minimal"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/builder-prove.XXXXXX")"
export CARGO_TARGET_DIR="$WORK/target"   # shared, so each copy rebuilds little
trap 'rm -rf "$WORK"' EXIT

PY="${BUILDER_PYTHON:-}"
if [ -z "$PY" ]; then
  for c in "$SRC/.venv/bin/python" "$ROOT/template/.venv/bin/python" "$ROOT/.venv/bin/python"; do
    if [ -x "$c" ]; then PY="$c"; break; fi
  done
  PY="${PY:-python3}"
fi
case "$PY" in /*) ;; *) PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")" ;; esac

pass=0; fail=0
fresh() {
  rm -rf "$WORK/p"; mkdir -p "$WORK/p"
  (cd "$SRC" && tar --exclude=./target --exclude=./dist --exclude=./.venv -cf - .) | (cd "$WORK/p" && tar -xf -)
  # build.sh reads the module from target/; point it at the shared target dir
  ln -s "$CARGO_TARGET_DIR" "$WORK/p/target"
}

# expect_failure NAME EXPECTED-TEXT COMMAND...
expect_failure() {
  local name="$1" expected="$2"; shift 2
  local out status=0
  out="$(cd "$WORK/p" && "$@" 2>&1)" || status=$?
  if [ "$status" -ne 0 ] && grep -qF -- "$expected" <<<"$out"; then
    printf '  caught   %s\n' "$name"; pass=$((pass + 1))
  else
    printf '  MISSED   %s (exit %s; expected text: %s)\n' "$name" "$status" "$expected"
    printf '%s\n' "$out" | tail -15 | sed 's/^/           | /'
    fail=$((fail + 1))
  fi
}

boundary() { cargo test -q -p tool_core --test boundary; }
browser() { ./scripts/build.sh >/dev/null && BUILDER_ENGINES=chromium BUILDER_IDLE=1 "$PY" tests/browser/check.py; }
browser_planted() { BUILDER_ENGINES=chromium BUILDER_IDLE=1 "$PY" tests/browser/check.py; }

echo "Planted defects, each against the check meant to catch it:"

fresh
cat >> "$WORK/p/crates/core/src/counter.rs" <<'EOF'
pub fn half(x: u32) -> f64 { x as f64 / 2.0 }
EOF
expect_failure "a float in the core" "(float)" boundary

fresh
cat >> "$WORK/p/crates/core/src/counter.rs" <<'EOF'
pub fn shout() { println!("hello"); }
EOF
expect_failure "printing from the core" "(input/output)" boundary

fresh
cat >> "$WORK/p/crates/core/src/counter.rs" <<'EOF'
pub fn index() -> std::collections::HashMap<u32, u32> { Default::default() }
EOF
expect_failure "a hash map in the core" "(hash map)" boundary

fresh
printf '\n[dev-dependencies]\nwasm-bindgen = "=0.2.127"\n' >> "$WORK/p/crates/core/Cargo.toml"
expect_failure "a dependency outside the allowlist" "dependencies outside the allowlist" boundary

fresh
"$PY" - "$WORK/p/crates/shim/src/lib.rs" <<'EOF'
import sys; p = sys.argv[1]; s = open(p).read()
s = s.replace("tool_core::api::act(settings_json, state_json, action)",
              'if action == "add" { tool_core::api::act(settings_json, state_json, "reset") } else { tool_core::api::act(settings_json, state_json, action) }')
open(p, "w").write(s)
EOF
expect_failure "a decision in the shim" "the shim makes decisions" boundary

fresh
"$PY" - "$WORK/p/web/app.js" <<'EOF'
import sys; p = sys.argv[1]; s = open(p).read()
s = s.replace('el("add").disabled = !view.can_add;', 'el("add").disabled = view.count >= 10;')
open(p, "w").write(s)
EOF
expect_failure "a copy of a core rule in the page" "number in the page" boundary

fresh
printf '<img src="https://example.invalid/pixel.gif" alt="">\n' >> "$WORK/p/web/index.html"
expect_failure "an absolute URL in the page" "absolute URL" boundary

fresh
"$PY" - "$WORK/p/web/index.html" <<'EOF'
import re, sys; p = sys.argv[1]; s = open(p).read()
s = re.sub(r'  <meta http-equiv="Content-Security-Policy"[^>]*>\n', "", s)
open(p, "w").write(s)
EOF
expect_failure "a page with no Content-Security-Policy" "no Content-Security-Policy" boundary

fresh
cat >> "$WORK/p/crates/shim/src/lib.rs" <<'EOF'

#[wasm_bindgen]
extern "C" {
    #[wasm_bindgen(js_namespace = navigator, js_name = sendBeacon)]
    fn beacon(url: &str) -> bool;
}

#[wasm_bindgen]
pub fn ping() -> bool {
    beacon("/collect")
}
EOF
expect_failure "a WebAssembly import that reaches sendBeacon" "reaches sendBeacon" \
  bash -c './scripts/build.sh >/dev/null && "$0" scripts/wasm_imports.py dist' "$PY"

# The next two get past the source scans on purpose (the URL is assembled at
# run time and the error is raised after the build), so only the browser
# check stands between them and a deploy.
fresh
(cd "$WORK/p" && ./scripts/build.sh >/dev/null 2>&1)
printf '\nfetch(["https:", "", "example.invalid", "x"].join("/")).catch(() => {});\n' >> "$WORK/p/dist/app.js"
expect_failure "an off-origin fetch the page's CSP blocks" "FAIL no Content-Security-Policy violation" browser_planted

fresh
(cd "$WORK/p" && ./scripts/build.sh >/dev/null 2>&1)
printf '\nfetch(["https:", "", "example.invalid", "x"].join("/")).catch(() => {});\n' >> "$WORK/p/dist/app.js"
"$PY" - "$WORK/p/dist/index.html" <<'EOF'
import re, sys; p = sys.argv[1]; s = open(p).read()
s = re.sub(r'  <meta http-equiv="Content-Security-Policy"[^>]*>\n', "", s)
open(p, "w").write(s)
EOF
expect_failure "the same fetch with the CSP stripped from the built page" "FAIL no off-origin request" browser_planted

fresh
(cd "$WORK/p" && ./scripts/build.sh >/dev/null 2>&1)
printf '\nconsole.error("planted");\n' >> "$WORK/p/dist/app.js"
expect_failure "a console error" "FAIL no console error" browser_planted

fresh
"$PY" - "$WORK/p/crates/core/src/counter.rs" <<'EOF'
import sys; p = sys.argv[1]; s = open(p).read()
s = s.replace("(state.count + s.step).min(s.max)", "state.count + s.step")
open(p, "w").write(s)
EOF
expect_failure "a broken rule (no stop at the maximum), core suite" "adding_stops_at_the_maximum" \
  cargo test -q -p tool_core --lib
expect_failure "the same broken rule, browser check" "FAIL Add steps by 3 and stops at 10" browser

echo
echo "caught $pass, missed $fail"
[ "$fail" -eq 0 ]
