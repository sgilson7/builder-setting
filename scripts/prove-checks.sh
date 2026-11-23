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
export BUILDER_LOUD=1   # each planted defect is judged on the full output
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
  # the example's journal sits beside it, as a project's does
  rm -rf "$WORK/p-journal"; cp -R "$ROOT/examples/minimal-journal" "$WORK/p-journal"
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


# ---- Added with the second round of reference defaults ----

fresh
mkdir -p "$WORK/p/data/shaders"
printf '#version 300 es\nprecision highp float;\nout vec4 o;\nvoid main() { o = vec4(0.82, 0.45, 1.0, 1.0); }\n' > "$WORK/p/data/shaders/scene.frag"
expect_failure "a tuning number in a shader" "number in a shader" boundary

fresh
mkdir -p "$WORK/p/web/lib"
printf 'export const stopsAt = 10;\n' > "$WORK/p/web/lib/rule.js"
expect_failure "a copy of a rule in a nested page file" "number in the page" boundary

fresh
printf '\nfunction leave(next) { window.location.href = next; }\n' >> "$WORK/p/web/app.js"
expect_failure "a page that navigates on its own" "the page navigates" boundary

fresh
printf '\nif (!navigator.webdriver) document.body.requestPointerLock();\n' >> "$WORK/p/web/app.js"
expect_failure "a page that behaves differently under automation" "behave the same under the browser check" boundary

fresh
printf '\nlocalStorage.setItem("count", "0");\n' >> "$WORK/p/web/app.js"
expect_failure "browser storage in the page" "browser storage in the page" \
  cargo test -q -p tool_core --test no_storage

copy_test() { cargo test -q -p tool_core --test copy; }

fresh
"$PY" - "$WORK/p/data/counter.json" <<'EOF2'
import json, sys; p = sys.argv[1]; d = json.load(open(p))
d["add_label"] = "Add to the tally"
json.dump(d, open(p, "w"), indent=2)
EOF2
expect_failure "a word the glossary rules out" "is ruled out for" copy_test

fresh
"$PY" - "$WORK/p/data/counter.json" <<'EOF2'
import json, sys; p = sys.argv[1]; d = json.load(open(p))
d["intro"] = "Let us delve into counting."
json.dump(d, open(p, "w"), indent=2)
EOF2
expect_failure "a stock phrase in a string" "(TONE.md)" copy_test

fresh
"$PY" - "$WORK/p/GLOSSARY.md" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
s = s.replace("How much one press of Add or Remove changes the count.", "Each press of Add or Remove changes the count by 3.")
open(p, "w").write(s)
EOF2
expect_failure "a rule's number typed into the glossary" "{placeholder}" copy_test

fresh
mkdir -p "$WORK/p/web/vendor"
printf 'export const lib = 0;\n' > "$WORK/p/web/vendor/lib.js"
(cd "$WORK/p/web/vendor" && printf '%s  lib.js\n' "$(printf 'something else' | shasum -a 256 | cut -d' ' -f1)" > SHA256SUMS)
expect_failure "a vendored file that does not match its checksum" "does not match its SHA256SUMS" ./scripts/build.sh

fresh
printf '[{"name": "a break no test sees", "file": "web/style.css", "find": "box-sizing", "replace": "box-sizing", "test": "adding_stops_at_the_maximum"}]\n' > "$WORK/p/tests/breaks.json"
expect_failure "a break its test does not catch" "still passes with the behaviour broken" "$PY" scripts/break_tests.py

fresh
printf '[]\n' > "$WORK/p/tests/breaks.json"
expect_failure "an empty list of breaks" "the proof would prove nothing" "$PY" scripts/break_tests.py

notebook() { "$PY" scripts/notebook_check.py; }

fresh
"$PY" - "$WORK/p/SECOND-ORDER.md" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = "| R1.1 | | | | | | |"
assert old in s
s = s.replace(old, "| R1.1 | finding | The count starts at 0. | It does. | Nothing. | | finished |")
open(p, "w").write(s)
EOF2
expect_failure "a notebook row with a status the procedure does not use" "has status 'finished'" notebook

fresh
"$PY" - "$WORK/p/SECOND-ORDER.md" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = "| R1.1 | | | | | | |"
assert old in s
s = s.replace(old, "| R1.1 | worklist | The labels were written by the agent. | No teacher has read them. | Listed for the person. | | person |")
open(p, "w").write(s)
EOF2
expect_failure "a person's notebook row that the handoff does not name" "R1.1 is the person's to do" notebook

fresh
"$PY" - "$WORK/p/SECOND-ORDER.md" "$WORK/p/HANDOFF.md" <<'EOF2'
import sys; p, h = sys.argv[1:]; s = open(p).read()
old = "| R1.1 | | | | | | |"
assert old in s
s = s.replace(old, "| 13 | worklist | The labels were written by the agent. | No teacher has read them. | Listed for the person. | | person |")
open(p, "w").write(s)
open(h, "a").write("\nPress 13 times to reach the maximum.\n")
EOF2
expect_failure "a notebook row numbered outside the rounds" "13 is not a round number" notebook

fresh
"$PY" - "$WORK/p/PLAN.md" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = "| 1 | | | |"
assert old in s
s = s.replace(old, "| 1 | The count stops at the maximum. | The brief says so. | adding_stops_at_the_maximum |")
open(p, "w").write(s)
EOF2
expect_failure "a plan with decisions and an empty notebook" "SECOND-ORDER.md has no rows, but PLAN.md holds decisions" notebook

journal() { env -u CI "$PY" scripts/journal_check.py; }

fresh
rm -rf "$WORK/p-journal"
expect_failure "a started build with no journal" "the journal is missing" journal

fresh
"$PY" - "$WORK/p-journal/index.html" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = 'data-kind="reading"'
assert old in s
s = s.replace(old, 'data-kind="plan"')
open(p, "w").write(s)
EOF2
expect_failure "a journal with no opening entry" "the journal has no opening entry" journal

fresh
"$PY" - "$WORK/p-journal/index.html" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = 'data-kind="reading">'
assert old in s
s = s.replace(old, 'data-kind="reading" data-blank>')
open(p, "w").write(s)
EOF2
expect_failure "an opening entry left blank" "still the template's blank one" journal

fresh
"$PY" - "$WORK/p/SECOND-ORDER.md" "$WORK/p/HANDOFF.md" <<'EOF2'
import sys; p, h = sys.argv[1:]; s = open(p).read()
old = "| R1.1 | | | | | | |"
assert old in s
s = s.replace(old, "| R1.1 | worklist | The labels were written by the agent. | No teacher has read them. | Listed for the person. | | person |")
open(p, "w").write(s)
open(h, "a").write("\nOpen for the person: R1.1.\n")
EOF2
expect_failure "a person's notebook row the journal does not name" "R1.1 is the person's to do and the journal does not name it" journal

fresh
"$PY" - "$WORK/p-journal/index.html" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = "<h4>Where I stop</h4>"
assert old in s
s = s.replace(old, "<p>Recorded as R4.2 and answered in T9.</p>" + old)
open(p, "w").write(s)
EOF2
expect_failure "a journal that cites a notebook row that does not exist" "the journal cites R4.2" journal
expect_failure "a journal that cites a triage row that does not exist" "the journal cites T9" journal

fresh
(cd "$WORK/p-journal" && git init -q && git add -A && git -c user.name=prove -c user.email=prove@invalid commit -qm journal)
"$PY" - "$WORK/p-journal/index.html" <<'EOF2'
import re, sys; p = sys.argv[1]; s = open(p).read()
s2 = re.sub(r'\n    <article class="entry" id="brief".*?</article>', "", s, flags=re.S)
assert s2 != s
open(p, "w").write(s2)
EOF2
expect_failure "a journal entry removed since the journal's last commit" "entry brief was in the journal's last commit and is gone" journal

# Answer chips, and the entries D20 and ENTRIES.md rules 8 to 12 ask for.
# ask DEFAULTS: put one question in the example journal's decisions.json, with
# the given default flags for options A and B, and draw its chips.
ask() {
  "$PY" - "$WORK/p-journal" "$1" "$2" <<'EOF2'
import json, sys; d, a, b = sys.argv[1], sys.argv[2] == "1", sys.argv[3] == "1"
p = d + "/decisions.json"; data = json.load(open(p))
data["questions"] = [{"id": "MC-Q1", "page": "reading", "question": "Should Reset return to 0?",
  "context": "The brief does not say.", "blocks": "the reset rule",
  "options": [{"key": "A", "text": "Yes", "default": a}, {"key": "B", "text": "No", "default": b}]}]
json.dump(data, open(p, "w"))
EOF2
  (cd "$WORK/p" && "$PY" tools/journal/decisions.py "$WORK/p-journal" >/dev/null 2>&1 || true)
}
# add_entry KIND ATTRS DATE BODY: a new entry at the top of the reading page
add_entry() {
  "$PY" - "$WORK/p-journal/index.html" "$@" <<'EOF2'
import sys; p, kind, attrs, date, body = sys.argv[1:]; s = open(p).read()
old = '    <article class="entry" id="opening"'
assert old in s
new = (f'    <article class="entry" id="{kind}-{date}" data-kind="{kind}" {attrs}>'
       f'<div class="stamp"><time datetime="{date}">{date}</time><span>{kind}</span></div>'
       f'<div class="entry-body">{body}</div></article>\n')
open(p, "w").write(s.replace(old, new + old, 1))
EOF2
}

fresh; ask 0 0
expect_failure "a question with no default" "MC-Q1 has 0 defaults" journal

fresh; ask 1 1
expect_failure "a question with two defaults" "MC-Q1 has 2 defaults" journal

fresh; ask 1 0
"$PY" - "$WORK/p-journal/decisions.json" <<'EOF2'
import json, sys; p = sys.argv[1]; d = json.load(open(p))
d["questions"][0]["question"] = "Should Reset return to the starting value?"
json.dump(d, open(p, "w"))
EOF2
expect_failure "chips left out of date with decisions.json" "out of date with decisions.json" journal

fresh; ask 1 0
(cd "$WORK/p" && "$PY" tools/journal/decisions.py "$WORK/p-journal" --answers "MC-Q1: A" >/dev/null)
expect_failure "an answer no agreed entry cites" "MC-Q1 was answered (A) and no agreed entry cites it" journal

fresh; ask 1 0
(cd "$WORK/p" && "$PY" tools/journal/decisions.py "$WORK/p-journal" --answers "MC-Q1: B" >/dev/null)
add_entry agreed "" 2026-10-20 "<h3>Your answers</h3><p>MC-Q1: B.</p>"
expect_failure "an answer that overrides the default with no triage row" "not the default A, and no TRIAGE.md row cites it" journal

fresh
add_entry mockups "" 2026-10-20 "<h3>The counter, drawn</h3><figure><img src=\"img/counter.svg\" alt=\"The counter\"></figure>"
add_entry live 'data-commit="abc1234"' 2026-10-21 "<h3>Published</h3>"
"$PY" - "$WORK/p-journal/index.html" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = 'class="live-now" data-commit=""'
assert old in s
open(p, "w").write(s.replace(old, 'class="live-now" data-commit="abc1234"'))
EOF2
expect_failure "a deploy after mockups with no against-the-mockup entry" "with no 'against' entry" journal

fresh
add_entry live 'data-commit="abc1234"' 2026-10-21 "<h3>Published</h3>"
expect_failure "a Live now page that names an older deploy" "Live now says nothing is deployed" journal

fresh
add_entry plan "" 2026-10-20 "<h3>The plan</h3><p>Build the counter, then the reset.</p>"
expect_failure "a plan entry with no picture or animation" "plan entry plan-2026-10-20 has no picture or animation" journal

fresh
add_entry plan "" 2026-10-20 "<h3>The plan</h3><!--FLOW id=nowhere--><!--/FLOW-->"
expect_failure "an animation placed with no scene file" "flows/nowhere.json does not exist" journal

fresh
add_entry research "" 2026-10-20 "<h3>What other counters do</h3><p>Two counters, unnamed.</p>"
expect_failure "a research entry with no source" "links no source" journal

fresh
add_entry intake "" 2026-10-20 "<h3>Your notes, read</h3><p>A summary of the notes.</p>"
expect_failure "an intake entry that does not quote its input" "does not quote the input" journal

fresh
printf '\n## References\n\n- **Ribbit King** (`../ribbit-king`): the scorecard\n' >> "$WORK/p/BRIEF.md"
expect_failure "a reference the opening entry does not name" "names Ribbit King under References" journal

fresh
mkdir -p "$WORK/p/extra" && echo "a new file" > "$WORK/p/extra/notes.txt"
expect_failure "a file no test tag covers" "no rule in tests/tags.toml covers extra/notes.txt" "$PY" scripts/quick_check.py --guard

fresh
(cd "$WORK/p" && ./scripts/build.sh >/dev/null)
"$PY" - "$WORK/p/dist" <<'EOF2'
import pathlib, shutil, sys; d = pathlib.Path(sys.argv[1])
wasm = next(d.rglob("*_bg.wasm")); glue = wasm.with_name(wasm.name.replace("_bg.wasm", ".js"))
(d / "pixel").mkdir()
shutil.copy(glue, d / "pixel" / glue.name)
(d / "pixel" / wasm.name).write_bytes(wasm.read_bytes() + b"\0")
EOF2
expect_failure "two views that load different engines" "the views load different WebAssembly modules" "$PY" scripts/wasm_imports.py dist

# Kits: each kit's tests, run inside a project by scripts/check-kits.sh.
kit_copy() { rm -rf "$WORK/kits"; cp -R "$ROOT/kits" "$WORK/kits"; }
kits() { BUILDER_KITS="$WORK/kits" "$ROOT/scripts/check-kits.sh" "$@"; }

fresh; kit_copy
"$PY" - "$WORK/kits/online/crates/core/src/online.rs" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = "*world = self.snapshots[&from].clone();"
assert old in s
open(p, "w").write(s.replace(old, "let _ = &from;"))
EOF2
expect_failure "rollback that never restores the world" "a_late_input_that_differs_rolls_back_to_the_world_of_a_copy_fed_on_time" kits online

fresh; kit_copy
"$PY" - "$WORK/kits/saves/crates/core/src/save.rs" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = "pub const VERSION: u32 = 2;"
assert old in s
open(p, "w").write(s.replace(old, "pub const VERSION: u32 = 3;"))
EOF2
expect_failure "a save version bumped with no migration step" "a save from a deployed build no longer loads" kits saves

fresh; kit_copy
"$PY" - "$WORK/kits/saves/crates/core/src/save.rs" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
old = '            let level = v.remove("level").unwrap_or(json!(1));'
assert old in s
open(p, "w").write(s.replace(old, old + '\n            v.remove("wood");'))
EOF2
expect_failure "a migration that loses a field" "the field \"wood\" is gone or changed after loading" kits saves

# The style pack and the art pipeline live in template/, not the example.
mkdir -p "$WORK/leak/template/styles/default" "$WORK/leak/template/web"
cp "$ROOT/template/styles/default/palette.json" "$WORK/leak/template/styles/default/"
pack_hex="$("$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(next(v for k,v in d.items() if not k.startswith("_")))' "$ROOT/template/styles/default/palette.json")"
printf 'body { color: %s; }\n' "$pack_hex" > "$WORK/leak/template/web/style.css"
rm -rf "$WORK/p"; mkdir -p "$WORK/p"
expect_failure "a default-style colour in the template's CSS" "default-style token" \
  "$PY" "$ROOT/scripts/check-style-leak.py" "$WORK/leak"

rm -rf "$WORK/art"; mkdir -p "$WORK/art"
(cd "$ROOT/template" && tar --exclude=__pycache__ -cf - tools tests/art_check.py data/art.json styles) | (cd "$WORK/art" && tar -xf -)
printf '\nSTRAY = "#123456"\n' >> "$WORK/art/tools/art/artlib.py"
expect_failure "a colour literal in the art code" "colour literal" "$PY" "$WORK/art/tests/art_check.py"

# The office-intake kit's tests, each against a planted defect in a copy of the kit.
kit_fresh() {
  rm -rf "$WORK/k" "$WORK/p"; mkdir -p "$WORK/k/kits" "$WORK/k/template" "$WORK/p"
  (cd "$ROOT/kits" && tar --exclude=__pycache__ -cf - office-intake) | (cd "$WORK/k/kits" && tar -xf -)
  for f in BRIEF GLOSSARY TRIAGE LICENSES; do cp "$ROOT/template/$f.md" "$WORK/k/template/"; done
}
kit_tests() { "$PY" -m unittest discover -s "$WORK/k/kits/office-intake/tests"; }
kit_edit() {  # kit_edit FILE OLD NEW: a scripted edit that asserts it matched
  "$PY" - "$WORK/k/kits/office-intake/$1" "$2" "$3" <<'EOF2'
import sys; p, old, new = sys.argv[1:]; s = open(p).read()
assert old in s, old
open(p, "w").write(s.replace(old, new))
EOF2
}

kit_fresh
kit_edit tools/intake/layout.json '"private_sheets": ["Team"]' '"private_sheets": []'
expect_failure "an intake that reads the Team sheet" "test_no_private_text_reaches_any_output" kit_tests

kit_fresh
kit_edit tools/intake/intake.py 'bad = leaks(out_text, private_words(files))' 'bad = []'
expect_failure "an intake with its name guard switched off" "test_a_name_in_the_text_stops_the_intake_before_it_writes" kit_tests

kit_fresh
kit_edit tools/intake/intake.py 'missing.append(f"{names['"'"'design'"'"']}: the heading \"{h}\"")' 'pass'
expect_failure "an intake that does not report a missing heading" "test_a_missing_heading_is_reported" kit_tests

kit_fresh
kit_edit tools/intake/layout.json '"10. AI use statement"' '"10. AI use statement", "11. Credits"'
expect_failure "a template missing a heading the layout names" "test_the_blank_templates_match_the_layout" kit_tests

kit_fresh
kit_edit tools/intake/intake.py '        return "tool", {**tool, "private_sheets": LAYOUT["private_sheets"]}' '        return "game", LAYOUT'
expect_failure "an intake that reads a tool folder as a game" "test_a_tool_design_document_lands_in_the_brief_with_nothing_missing" kit_tests

kit_fresh
kit_edit tools/intake/intake.py '    for name in (LAYOUT["files"]["data"], LAYOUT["tool"]["files"]["data"]):' '    for name in (LAYOUT["files"]["data"],):'
expect_failure "a name guard that skips the tool workbook's Team sheet" "test_a_name_from_a_tool_team_sheet_stops_the_intake" kit_tests

kit_fresh
kit_edit tools/intake/intake.py '        if PurePosixPath(path).suffix.lower() in IMAGES:' '        if True:'
expect_failure "an intake that copies audio from inside the slides" "test_the_presentation_recording_is_never_copied" kit_tests

kit_fresh
kit_edit tools/intake/intake.py '        if p.stem.lower() == recording_stem.lower() and p.suffix.lower() != PurePosixPath(names["pitch"]).suffix:' '        if False:'
expect_failure "an intake that copies the recording file" "test_the_presentation_recording_is_never_copied" kit_tests

kit_fresh
kit_edit tools/intake/layout.json '"5. Inputs and outputs",' '"5. Inputs, outputs and errors",'
expect_failure "a tool template missing a heading the layout names" "test_the_blank_templates_match_the_layout" kit_tests

kit_fresh
"$PY" - "$WORK/k/kits/office-intake/templates/GameDesign.docx" <<'EOF2'
import re, shutil, sys, zipfile
p = sys.argv[1]; tmp = p + ".tmp"
with zipfile.ZipFile(p) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "docProps/core.xml":
            s = data.decode()
            s2 = re.sub(r"<dc:creator\s*/>|<dc:creator>[^<]*</dc:creator>", "<dc:creator>A Planted Author</dc:creator>", s)
            assert s2 != s
            data = s2.encode()
        zout.writestr(item, data)
shutil.move(tmp, p)
EOF2
expect_failure "a blank template that carries an author's name" "test_the_blank_templates_carry_no_author" kit_tests

# Context (D24-D26): cards, STATE.md, digests and quiet runs
context() { "$PY" scripts/context_check.py; }

fresh
add_entry research '' 2026-11-06 '<h3>Read</h3><p>From <a href="https://example.org/">a source</a>, held by card:claude.r99.</p>'
expect_failure "a journal entry citing a card that does not exist" "cites card:claude.r99, which does not exist" journal

fresh
"$PY" -c "import sys; open(sys.argv[1], 'a').write('\n' + 'Too much carried over. ' * 400)" "$WORK/p/STATE.md"
expect_failure "a STATE.md longer than two pages" "STATE.md is" context

fresh
(cd "$WORK/p" && git init -q && git add -A && git -c user.name=p -c user.email=p@p commit -qm planted)
sed -i.bak 's/^Commit: .*/Commit: 0123abc/' "$WORK/p/STATE.md" && rm "$WORK/p/STATE.md.bak"
expect_failure "a STATE.md naming a commit the repository does not have" "names commit 0123abc, which this repository does not have" context

fresh
printf '\n`card:claude.r99`\n' >> "$WORK/p/STATE.md"
expect_failure "a STATE.md citing a card that does not exist" "STATE.md cites card:claude.r99" context

fresh
mkdir -p "$WORK/refs"
(cd "$WORK/p" && "$PY" tools/digest.py "$WORK/p" --out "$WORK/refs/planted.md" >/dev/null)
"$PY" - "$WORK/p/BRIEF.md" <<'EOF2'
import sys; p = sys.argv[1]; s = open(p).read()
s += "\n## References\n\n- **Planted** (../refs/planted.md): its counter\n"
open(p, "w").write(s)
EOF2
expect_failure "a digest named in the brief whose What to copy was never written" "still says TO FILL" context

fresh
expect_failure "a quiet run that would hide a failing command" "FAILED (exit 3)" ./scripts/quiet.sh sh -c 'echo planted failure; exit 3'

# the next two need Builder itself on disk: a copy of this repository, minus builds
builder_copy() {
  rm -rf "$WORK/b"; mkdir -p "$WORK/b"
  (cd "$ROOT" && tar --exclude=./template/target --exclude=./template/dist --exclude=./template/.venv \
     --exclude=./examples --exclude=./.venv --exclude=./.git --exclude='*/target' -cf - .) | (cd "$WORK/b" && tar -xf -)
}
cards_in_copy() { BUILDER_HOME="$WORK/b" "$PY" "$WORK/b/template/tools/ask.py" "$@"; }

fresh; builder_copy
sed -i.bak 's/^## How to read Builder$/## Reading Builder/' "$WORK/b/docs/context.md" && rm "$WORK/b/docs/context.md.bak"
expect_failure "a renamed heading that drops a card from the start pack" "the start pack names card docs.context.how-to-read-builder" cards_in_copy --check

fresh; builder_copy
sed -i.bak 's/^## Copying a kit$/## Bringing one in/' "$WORK/b/kits/README.md" && rm "$WORK/b/kits/README.md.bak"
expect_failure "a renamed heading that BuilderQA's answer depended on" "names card kits.readme.copying-a-kit, which does not exist" cards_in_copy --qa "$WORK/b/tests/builderqa.json"

# Round four (D28-D29): quiet checks, a STATE.md kept current, the deck, the context hooks
# and the codebase-guide kit; round five: the 300k compaction cap
plant() {  # plant FILE OLD NEW: a scripted edit that asserts it matched
  "$PY" - "$1" "$2" "$3" <<'EOF2'
import sys; p, old, new = sys.argv[1:]; s = open(p).read()
assert old in s, (p, old)
open(p, "w").write(s.replace(old, new, 1))
EOF2
}

fresh
printf '\npub fn   badly_formatted( ) {}\n' >> "$WORK/p/crates/core/src/counter.rs"
expect_failure "a failing step in a quiet check.sh still names itself" "last step: == 1/9 format" env -u BUILDER_LOUD -u CI ./scripts/check.sh

fresh
(cd "$WORK/p" && git init -q && git add -A && git -c user.name=p -c user.email=p@p commit -qm planted \
  && printf '| T9 | "make the counter count by twos" | planted | | | | |\n' >> TRIAGE.md \
  && git -c user.name=p -c user.email=p@p commit -qam "planted request")
expect_failure "a request recorded after STATE.md was last rewritten" "TRIAGE.md changed in" context

fresh
(cd "$WORK/p" && "$PY" tools/journal/present.py >/dev/null)
add_entry research '' 2026-11-07 '<h3>Later</h3><p>From <a href="https://example.org/">a source</a>.</p>'
expect_failure "a deck built before the journal's newest entry" "the deck is out of date" "$PY" tools/journal/present.py --check

tools_copy() { rm -rf "$WORK/t"; mkdir -p "$WORK/t"; (cd "$ROOT/template" && tar --exclude=__pycache__ -cf - tools .claude) | (cd "$WORK/t" && tar -xf -); }
tools_tests() { BUILDER_HOME="$ROOT" BUILDER_TOOLS="$WORK/t/tools" "$PY" -m unittest discover -s "$ROOT/tests" -p test_context_tools.py; }
tools_copy; plant "$WORK/t/tools/context/after_tool.py" 'if band <= seen.get(sid, -1):' 'if False:'
expect_failure "a context warning repeated on every call" "test_warns_once_past_200k" tools_tests
tools_copy; plant "$WORK/t/tools/context/after_tool.py" 'return min(mark, cap * 2 // 3) if cap > 0 else mark' 'return mark'
expect_failure "a warning mark the compaction cap never lets the context reach" "test_under_a_200k_cap" tools_tests

tools_copy; plant "$WORK/t/tools/context/after_compact.py" '        print(state.read_text())' '        pass'
expect_failure "STATE.md left out after a compaction" "test_state_comes_back_and_no_index_is_asked" tools_tests
tools_copy; plant "$WORK/t/.claude/settings.json" '"300000"' '"200000"'
expect_failure "the template's compaction cap set back to 200k" "test_the_template_compacts_at_300k" tools_tests

# Round five: the journal's animations (tools/journal/animate.py), each test against a planted defect
anim_tests() { BUILDER_TOOLS="$WORK/t/tools" "$PY" -m unittest discover -s "$ROOT/tests" -p test_journal_animate.py; }
tools_copy; plant "$WORK/t/tools/journal/animate.py" 'for s in f["steps"])' 'for s in [])'
expect_failure "an animation with no step list as text" "test_a_placed_scene_becomes_a_figure" anim_tests
tools_copy; plant "$WORK/t/tools/journal/animate.py" '.replace("</", "<\\/")' ''
expect_failure "a step whose words end the scene's script early" "test_closing_script_text" anim_tests
tools_copy; plant "$WORK/t/tools/journal/animate.py" '    if fresh != page:' '    if False:'
expect_failure "a page left out of date with its scene files" "test_an_edited_scene_leaves" anim_tests
tools_copy; plant "$WORK/t/tools/journal/animate.py" '            page = page.rstrip("\n") + "\n" + block + "\n"' '            pass'
expect_failure "a page with no </body> left without the engine" "test_a_page_without_a_closing_body_tag" anim_tests
tools_copy; plant "$WORK/t/tools/journal/animate.py" '        if p.stem not in placed:' '        if False:'
expect_failure "a scene file placed in no entry" "test_a_scene_placed_in_no_entry" anim_tests
tools_copy; plant "$WORK/t/tools/journal/animate.py" '    if status == "measured" and not' '    if False and not'
expect_failure "a measured scene that does not say where its steps came from" "test_a_measured_scene_says" anim_tests
tools_copy; plant "$WORK/t/tools/journal/animate.py" '    if status not in STATUS:' '    if False:'
expect_failure "a scene with no status" "test_a_scene_without_a_status" anim_tests
tools_copy; plant "$WORK/t/tools/journal/flowscene/check.py" '                    if (a, b) not in drawn:' '                    if False:'
expect_failure "the journal's copy of the scene check lets a mark cross empty space" "test_a_mark_between_unjoined_boxes" anim_tests

guide_copy() { rm -rf "$WORK/g"; mkdir -p "$WORK/g"; (cd "$ROOT/kits" && tar --exclude=__pycache__ -cf - codebase-guide) | (cd "$WORK/g" && tar -xf -); }
guide_tests() { "$PY" -m unittest discover -s "$WORK/g/codebase-guide/tests"; }
guide_copy; plant "$WORK/g/codebase-guide/tools/guide/excerpts.py" "if must not in lines[first - 1]:" "if False:"
expect_failure "an excerpt whose function moved" "test_moved_function_fails" guide_tests
guide_copy; plant "$WORK/g/codebase-guide/scripts/target_unchanged.py" "added = sorted(set(now) - set(then))" "added = []"
expect_failure "an install inside the read-only codebase" "test_edit_addition_and_install_fail" guide_tests
guide_copy; plant "$WORK/g/codebase-guide/scripts/target_unchanged.py" "        if manifest.exists():" "        if False:"
expect_failure "a manifest written over" "test_manifest_is_written_once" guide_tests
guide_copy; plant "$WORK/g/codebase-guide/tools/guide/labels.py" 'elif kind == "proposed":' 'elif False:'
expect_failure "a proposed part that shows code" "test_proposed_part_with_code_fails" guide_tests
guide_copy; plant "$WORK/g/codebase-guide/tools/guide/labels.py" "            if not cited:" "            if False:"
expect_failure "a measured part with no code" "test_measured_part_without_code_fails" guide_tests


# The Manim kit's tests, each against a planted defect in a copy of the kit.
manim_copy() { rm -rf "$WORK/m" "$WORK/p"; mkdir -p "$WORK/m" "$WORK/p"; (cd "$ROOT/kits" && tar --exclude=__pycache__ -cf - manim) | (cd "$WORK/m" && tar -xf -); }
manim_tests() { "$PY" -m unittest discover -s "$WORK/m/manim/tests/manim"; }
manim_page() { BUILDER_ENGINES=chromium "$PY" "$WORK/m/manim/tests/manim/page_check.py"; }
M="$WORK/m/manim"
manim_copy; plant "$M/deck/scenes/sample-flow.json" '"move_ms": 800' '"move_ms": 810'
expect_failure "a committed scene file whose move is not whole frames" "test_the_committed_scenes_are_valid" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" "if nid not in nodes:" "if False:"
expect_failure "a scene naming a missing node" "test_a_scene_naming_a_missing_node_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" 'for nid in s.get("light", []):' "for nid in []:"
expect_failure "a lit node the scene lacks" "test_a_lit_node_that_does_not_exist_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" 'if not s["t"].strip():' "if False:"
expect_failure "a step without words" "test_a_step_without_words_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" "    if isinstance(value, float):" "    if False:"
expect_failure "a fraction in a scene file" "test_a_scene_with_a_fraction_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" 'if s["move_ms"] % fm:' "if False:"
expect_failure "a move that is not whole frames" "test_a_move_that_is_not_whole_frames_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" 'if s["move_ms"] < scene["fade_ms"]:' "if False:"
expect_failure "a move shorter than the fade" "test_a_move_shorter_than_the_fade_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" "            if style not in styles:" "            if False:"
expect_failure "a text style the theme lacks" "test_a_text_style_the_theme_lacks_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" "sort_keys=True" "sort_keys=False"
expect_failure "a scene hash that depends on key order" "test_the_scene_hash_ignores_key_order" manim_tests
manim_copy; plant "$M/tools/manim/geometry.py" "s = min(sx, sy)" "s = max(sx, sy)"
expect_failure "an edge that leaves its box at the farther edge" "test_the_border_point_by_hand" manim_tests
manim_copy; plant "$M/tools/manim/geometry.py" "return 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3" "return 3 * u * u * t * p1 + 3 * u * t * t * p2"
expect_failure "an ease without its cubic term" "test_the_css_ease_by_hand" manim_tests
manim_copy; plant "$M/tools/manim/mp4.py" "for k in range(n))" "for k in range(n)) + 1"
expect_failure "an MP4 reader that counts one frame too many" "test_the_reader_counts_frames_in_a_hand_built_file" manim_tests
manim_copy; plant "$M/tools/manim/mp4.py" '        raise ValueError("not an MP4 file: no ftyp box first")' "        return {}"
expect_failure "an MP4 reader that accepts any file" "test_the_reader_refuses_a_file_that_is_not_mp4" manim_tests
manim_copy; plant "$M/deck/media/sample-flow/manifest.json" '"clip": "light/step-03.mp4"' '"clip": "light/step-04.mp4"'
expect_failure "a manifest naming a clip that does not exist" "test_every_step_has_a_clip_and_a_final_frame_in_each_theme" manim_tests
manim_copy; plant "$M/tools/manim/manifest.py" 'if m["scene_sha256"] != scenefile.scene_hash(scene):' "if False:"
expect_failure "a scene edited after its render, unseen" "test_a_scene_edited_after_its_render_is_stale" manim_tests
manim_copy; plant "$M/tools/manim/manifest.py" 'if m["theme_sha256"] != scenefile.scene_hash(theme):' "if False:"
expect_failure "a changed theme, unseen" "test_a_changed_theme_makes_the_render_stale" manim_tests
manim_copy; plant "$M/tools/manim/manifest.py" 'if scenefile.sha256(data) != row["sha256"] or len(data) != row["bytes"]:' "if False:"
expect_failure "a swapped clip, unseen" "test_a_swapped_clip_fails_its_hash" manim_tests
manim_copy; plant "$M/tools/manim/manifest.py" "if not clip.exists() or not png.exists():" "if not clip.exists():"
expect_failure "a missing final frame, unseen" "test_a_missing_final_frame_fails" manim_tests
manim_copy; plant "$M/tools/manim/manifest.py" 'if info["frames"] != step["move_ms"] // fm or info["ms"] != step["move_ms"]:' "if False:"
expect_failure "a clip whose length disagrees with the scene" "test_a_clip_whose_length_disagrees_with_the_scene_fails" manim_tests
manim_copy; plant "$M/data/manim/budget.json" '"clip_bytes": 1048576' '"clip_bytes": 40000'
expect_failure "a clip over the budget" "test_the_media_fits_the_budget" manim_tests
manim_copy; plant "$M/tools/manim/manifest.py" 'if biggest > budget["clip_bytes"]:' "if False:"
expect_failure "a clip budget that is not checked" "test_a_tight_budget_fails" manim_tests
manim_copy; plant "$M/tools/manim/theme.py" 'name = "--" + k.replace("_", "-")' 'name = "--" + k'
expect_failure "theme CSS that is not what theme.json writes" "test_the_theme_css_matches_theme_json" manim_tests
manim_copy; plant "$M/README.md" '`deck/fonts/PublicSans-wght.ttf`' '`deck/fonts/PublicSans.ttf`'
expect_failure "a font without its licence row" "test_every_font_the_renderer_registers_is_in_licenses" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" 'if not (ROOT / scene["code"]).is_file():' "if False:"
expect_failure "a code scene without its code" "test_a_code_scene_whose_code_is_missing_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" 'if s["move_ms"] <= 0 or s["move_ms"] % fm:' 'if s["move_ms"] <= 0:'
expect_failure "a code step that is not whole frames" "test_a_code_step_that_is_not_whole_frames_is_refused" manim_tests
manim_copy; plant "$M/tools/manim/scene.py" '        scene["code_sha256"] = sha256((ROOT / scene["code"]).read_bytes())' "        pass"
expect_failure "code left out of its scene's hash" "test_the_code_is_part_of_the_render_it_made" manim_tests
manim_copy; plant "$M/tests/manim/test_manim.py" "lambda m: \" \" if m[0].startswith(\"/\") else '\"\"'" 'lambda m: ""'
expect_failure "a JavaScript scanner that blanks code too" "test_code_of_blanks_comments_and_strings" manim_tests
manim_copy; plant "$M/deck/manim/player.js" "const steps = scene.steps, last = steps.length - 1;" "const steps = scene.steps, last = steps.length - 2;"
expect_failure "a number in the player" "test_the_player_holds_no_number_but_0_and_1" manim_tests
manim_copy; plant "$M/deck/manim/player.js" "      words(now, steps[i].t);" "      now.innerHTML += steps[i].t;"
expect_failure "step words set as HTML" "test_the_player_parses_no_html" manim_tests
manim_copy; plant "$M/deck/manim/player.js" "if (!animate || reduceQ.matches) {" "if (!animate) {"
expect_failure "a player that plays clips under reduced motion" "reduced motion: sample-flow's Next plays no clip" manim_page
manim_copy; plant "$M/deck/manim/player.js" $'      clearTimeout(timer);\n      vid.pause();\n' ""
expect_failure "a Pause that leaves the clip playing" "FAIL Pause stops the clip and the timer" manim_page

manim_site() { "$PY" -m unittest discover -s "$WORK/m/manim/tests/manim" -p "test_site.py"; }
manim_copy; printf '<!-- edited by hand -->\n' >> "$M/deck/flow/index.html"
expect_failure "a site page edited by hand" "test_the_pages_on_disk_are_current" manim_site
manim_copy; plant "$M/tools/manim/sitepages.py" "base = f' data-manim-base=\"{pre}\"' if pre else ''" "base = ''"
expect_failure "an animation's page without data-manim-base" "test_every_animation_has_its_own_route" manim_site
manim_copy; plant "$M/tools/manim/sitepages.py" "own = f'{s[\"scene\"]}/' if unit else f'{u[\"id\"]}/{s[\"scene\"]}/'" "own = f'{s[\"scene\"]}/'"
expect_failure "the deck links to a page by the wrong folder" "test_every_link_on_the_site_resolves" manim_site
manim_copy; plant "$M/tools/manim/sitepages.py" "n = rows[i + 1]" "n = rows[i]"
expect_failure "the pager's Next points at its own page" "test_the_pager_walks_every_animation_in_deck_order" manim_site
manim_copy; plant "$M/tools/manim/sitepages.py" "if dupes or missing or unlisted:" "if dupes or missing:"
expect_failure "a scene in no unit" "test_a_scene_in_no_unit_is_refused" manim_site
manim_copy; plant "$M/data/manim/site.json" '"All {n} animations as one deck"' '"All 2 animations as one deck"'
expect_failure "a count typed into site.json" "test_counts_are_computed" manim_site
manim_copy; plant "$M/tools/manim/publish.py" "kept = {k: scene[k] for k in SCENE_KEEP}" "kept = scene"
expect_failure "scene files published whole, source and all" "test_nothing_published_names_a_source" manim_site
manim_copy; plant "$M/tools/manim/publish.py" '"manim/page.js", ' ''
expect_failure "page.js left out of the published site" "test_every_file_a_page_needs_is_published" manim_site
manim_copy; plant "$M/deck/manim/deck.js" "if (k < 0 || k > slides.length - 1) return;" "if (k < 0 || k > slides.length - 2) return;"
expect_failure "a number in the slide script" "test_the_player_holds_no_number_but_0_and_1" manim_tests
manim_copy; plant "$M/deck/manim/page.js" "else localStorage.setItem(key, pick.value);" "else localStorage.removeItem(key);"
expect_failure "a theme forgotten between pages" "FAIL the theme chosen on one page holds on the next" manim_page

# The FlowScene kit's tests, each against a planted defect in a copy of the kit.
flow_copy() { rm -rf "$WORK/f" "$WORK/p"; mkdir -p "$WORK/f" "$WORK/p"; (cd "$ROOT/kits" && tar --exclude=__pycache__ -cf - flowscene) | (cd "$WORK/f" && tar -xf -); }
flow_tests() { "$PY" -m unittest discover -s "$WORK/f/flowscene/tests/flowscene"; }
flow_page() { BUILDER_ENGINES=chromium "$PY" "$WORK/f/flowscene/tests/flowscene/page_check.py"; }
F="$WORK/f/flowscene"
flow_copy; plant "$F/deck/flows/sample.json" '{"path": ["page", "api"], "kind": "req"}], "t": "The page sends' '{"path": ["page", "db"], "kind": "req"}], "t": "The page sends'
expect_failure "a committed scene with a mark between unjoined boxes" "test_the_committed_scenes_are_valid" flow_tests
flow_copy; plant "$F/tools/flowscene/check.py" "                for nid in path:" "                for nid in []:"
expect_failure "a path through a missing node" "test_a_path_through_a_missing_node_is_refused" flow_tests
flow_copy; plant "$F/tools/flowscene/check.py" "for a, b in zip(path, path[1:]):" "for a, b in []:"
expect_failure "a mark between unjoined boxes" "test_a_mark_between_unjoined_nodes_is_refused" flow_tests
flow_copy; plant "$F/tools/flowscene/check.py" 'if not (c["first"] <= a <= b <= last):' "if False:"
expect_failure "a highlight outside its excerpt" "test_a_highlight_outside_its_excerpt_is_refused" flow_tests
flow_copy; plant "$F/tools/flowscene/check.py" 'if s["c"] not in code:' "if False:"
expect_failure "an excerpt the scene lacks" "test_an_excerpt_the_scene_lacks_is_refused" flow_tests
flow_copy; plant "$F/tools/flowscene/check.py" "if not isinstance(v, str) or not v.strip():" "if not isinstance(v, str):"
expect_failure "a step without words" "test_a_step_without_words_is_refused" flow_tests
flow_copy; plant "$F/tools/flowscene/check.py" 'if m.get("kind") not in MARK_KINDS:' "if False:"
expect_failure "an unknown mark kind" "test_an_unknown_mark_kind_is_refused" flow_tests
flow_copy; plant "$F/tools/flowscene/check.py" "if isinstance(v, bool) or not isinstance(v, int):" "if False:"
expect_failure "a fraction in a node" "test_a_fraction_in_a_node_is_refused" flow_tests
flow_copy; plant "$F/deck/flowscene/engine.js" "L.restart)" "L.restartNow)"
expect_failure "a label the sample page lacks" "test_every_label_the_engine_reads_is_on_the_sample_page" flow_tests
flow_copy; plant "$F/deck/flowscene/engine.js" 'htmlEl("button", "fx-play", ctl, L.play)' 'htmlEl("button", "fx-play", ctl, "Play")'
expect_failure "a word written into the engine" "test_the_engine_holds_no_words_of_its_own" flow_tests
flow_copy; plant "$F/deck/flowscene/engine.js" 'now.textContent = (at + 1) + ". " + step.t;' 'now.innerHTML = (at + 1) + ". " + step.t;'
expect_failure "step words set as HTML" "test_the_engine_parses_no_html" flow_tests
flow_copy; plant "$F/deck/flowscene/engine.js" "      if (reduced()) { items.forEach(it => place(it, 1)); done(); return; }
" ""
expect_failure "an engine that ignores reduced motion" "FAIL reduced motion: the mark is placed at once" flow_page
flow_copy; plant "$F/deck/flowscene/engine.js" "function stop() { playing = false; clearTimeout(timer); bPlay.textContent = L.play; }" "function stop() { bPlay.textContent = L.play; }"
expect_failure "a Pause that leaves the timer running" "FAIL Pause holds the step" flow_page

echo
echo "caught $pass, missed $fail"
if [ $((pass + fail)) -eq 0 ]; then
  echo "no planted defects ran: the proof would prove nothing" >&2
  exit 1
fi
[ "$fail" -eq 0 ]
