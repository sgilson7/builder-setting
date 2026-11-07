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
add_entry mockups "" 2026-10-20 "<h3>The counter, drawn</h3>"
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

# Round four (D27-D29): quiet checks, a STATE.md kept current, the deck, the work index,
# the context hooks, the codebase-guide kit and the trial harness's own test
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

fresh
plant "$WORK/p/BRIEF.md" "## Autonomy" "## Permissions"
expect_failure "a renamed heading that WorkQA's answer depended on" "names card mine.brief.autonomy, which does not exist" \
  env BUILDER_PROJECT="$WORK/p" "$PY" "$ROOT/template/tools/ask.py" --mine --qa "$ROOT/tests/workqa.json"

tools_copy() { rm -rf "$WORK/t"; mkdir -p "$WORK/t"; (cd "$ROOT/template" && tar --exclude=__pycache__ -cf - tools) | (cd "$WORK/t" && tar -xf -); }
tools_tests() { BUILDER_HOME="$ROOT" BUILDER_TOOLS="$WORK/t/tools" "$PY" -m unittest discover -s "$ROOT/tests" -p test_context_tools.py; }
tools_copy; plant "$WORK/t/tools/ask.py" 'EMBED_MODEL + "\n" + c["title"] + "\n" + c["text"]' 'EMBED_MODEL + "\n" + c["title"]'
expect_failure "a vector kept after its card's text changed" "test_changed_text_is_embedded_again" tools_tests
tools_copy; plant "$WORK/t/tools/ask.py" 'for ranking, w in ((lex[:100], 1.0), (sem, SEM_WEIGHT)):' 'for ranking, w in ((lex[:100], 0.01), (sem, 1.0)):'
expect_failure "a fusion that lets the model bury keyword ranking's first card" "test_a_card_first_by_keywords" tools_tests
tools_copy; plant "$WORK/t/tools/ask.py" 'if orig.is_file() and orig.read_bytes() == path.read_bytes():' 'if False:'
expect_failure "Builder's own scripts counted as the project's work" "test_a_file_still_as_the_template" tools_tests
tools_copy; plant "$WORK/t/tools/context/after_tool.py" 'if band <= seen.get(sid, -1):' 'if False:'
expect_failure "a context warning repeated on every call" "test_warns_once_past_200k" tools_tests
tools_copy; plant "$WORK/t/tools/context/before_read.py" 'if i.get("offset") or i.get("limit") or not path.is_file():' 'if not path.is_file():'
expect_failure "read advice for a read that already took a range" "test_long_whole_read_gets_its_parts" tools_tests
tools_copy; plant "$WORK/t/tools/context/after_tool.py" 'return min(mark, cap * 2 // 3) if cap > 0 else mark' 'return mark'
expect_failure "a warning mark the compaction cap never lets the context reach" "test_under_a_200k_cap" tools_tests
tools_copy; plant "$WORK/t/tools/context/before_read.py" 'if b"\0" in raw[:8192]:' 'if False:'
expect_failure "read advice on an image" "test_an_image_gets_no_advice" tools_tests
tools_copy; plant "$WORK/t/tools/context/after_compact.py" "cards = push_cards(state)" 'cards = ""'
expect_failure "no cards pushed after a compaction" "test_after_a_compaction_the_next_steps_cards" tools_tests

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

harness_copy() { rm -rf "$WORK/h"; mkdir -p "$WORK/h/template"; (cd "$ROOT" && tar --exclude=__pycache__ -cf - harness) | (cd "$WORK/h" && tar -xf -);
  cp -R "$ROOT/template/tools" "$WORK/h/template/tools"; }
harness_tests() { "$PY" -m unittest discover -s "$WORK/h/harness/tests"; }
harness_copy; plant "$WORK/h/harness/analyze.py" "    for rx in BASH_WRITE[2:]:" "    for rx in []:"
expect_failure "STATE.md written through a heredoc, missed" "test_state_written_through_a_heredoc" harness_tests
harness_copy; plant "$WORK/h/harness/analyze.py" 'p = path if path.startswith("/") else "/" + path' 'p = path'
expect_failure "a Builder file read with cat, missed" "test_builder_file_read_with_cat" harness_tests
harness_copy; plant "$WORK/h/harness/analyze.py" 'out = [p for p in dict.fromkeys(out) if not p.startswith("/dev/")' 'out = [p for p in dict.fromkeys(out + ["notes/STATE.md"]) if not p.startswith("/dev/")'
expect_failure "HTML in a heredoc counted as a STATE.md rewrite" "test_state_written_through_a_heredoc" harness_tests
harness_copy; plant "$WORK/h/harness/analyze.py" "if fp in known and n > REWRITE_LINES:" "if False:"
expect_failure "a whole-file rewrite, missed" "test_whole_rewrite_is_counted" harness_tests
harness_copy; plant "$WORK/h/harness/analyze.py" "if d <= r[0] < nxt and r[2] in before]" "if False]"
expect_failure "a file re-read after a compaction, missed" "test_reread_after_compaction" harness_tests
harness_copy; plant "$WORK/h/harness/analyze.py" "if CHECK_CMD.search(seg) and not CHECK_SKIP.match(seg):" "if CHECK_CMD.search(seg):"
expect_failure "cat of a check script counted as a check run" "test_cat_of_a_check_script" harness_tests
harness_copy; plant "$WORK/h/harness/analyze.py" "    if cd:" "    if False:"
expect_failure "a journal written by Python after cd, missed" "test_journal_written_by_python" harness_tests
harness_copy; plant "$WORK/h/harness/analyze.py" 'if d["named"] and not d["opened"]:' 'if False:'
expect_failure "a digest's code rewritten without being opened, missed" "test_a_digest_read_and_its_code" harness_tests

echo
echo "caught $pass, missed $fail"
if [ $((pass + fail)) -eq 0 ]; then
  echo "no planted defects ran: the proof would prove nothing" >&2
  exit 1
fi
[ "$fail" -eq 0 ]
