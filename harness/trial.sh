#!/usr/bin/env bash
# Start a Builder trial: a clean folder with this branch's Builder in it, hooks that
# log compactions, and the opening to paste. Then launch claude there.
#
#   harness/trial.sh NAME                        a trial in ~/Documents/BuilderTrials/NAME
#   harness/trial.sh NAME --compact-window 200000   ask Claude Code to compact at about 200k tokens
#   harness/trial.sh NAME --refs ~/Documents/Builder/refs   copy game digests in as refs/
#   harness/trial.sh NAME --no-launch            set up only
#   harness/trial.sh NAME --memory off           the control arm: no work index, no read advice, keyword ranking
#   harness/trial.sh NAME --prompt FILE          copy a filled-in opening in as PROMPT.md
#   harness/ab.sh NAME --prompt FILE ...         an A/B pair: NAME-index and NAME-plain
#
# Afterwards: python3 harness/analyze.py ~/Documents/BuilderTrials/NAME
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
[ $# -ge 1 ] || { sed -n '2,10p' "$0"; exit 2; }
NAME="$1"; shift
WINDOW=""; REFS=""; LAUNCH=1; MEMORY=on; PROMPT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --compact-window) WINDOW="$2"; shift 2 ;;
    --refs) REFS="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --prompt) PROMPT="$2"; shift 2 ;;
    --no-launch) LAUNCH=0; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done
case "$MEMORY" in on|off) ;; *) echo "--memory is on or off"; exit 2 ;; esac
if [ "$MEMORY" = on ] && [ ! -x "$HOME/.cache/builder/embed-venv/bin/python" ]; then
  echo "note: no embedding model on this machine, so the work index ranks by keywords only; run template/scripts/setup-embed.sh first for hybrid ranking"
fi
TRIALS="${BUILDER_TRIALS:-$HOME/Documents/BuilderTrials}"
DIR="$TRIALS/$NAME"
[ -e "$DIR" ] && { echo "$DIR exists; pick another name"; exit 1; }

COMMIT="$(git -C "$REPO" rev-parse --short HEAD)"
BRANCH="$(git -C "$REPO" branch --show-current)"
DIRTY="$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ')"
[ "$DIRTY" = "0" ] || echo "note: $DIRTY uncommitted change(s) in $REPO are NOT in the trial; it uses commit $COMMIT"

mkdir -p "$DIR/builder" "$DIR/harness" "$DIR/.claude"
git -C "$REPO" archive HEAD | tar -x -C "$DIR/builder"
rm -rf "$DIR/builder/harness"   # the agent under test does not see the harness
[ -n "$REFS" ] && cp -R "$REFS" "$DIR/refs"

# hooks: STATE.md back after a compaction; the context warning after each tool call (both arms);
# the read advice only with the work index on; session starts and compactions logged for the harness
python3 - "$DIR/.claude/settings.json" "$MEMORY" "$WINDOW" "$DIR" <<'PY'
import json, sys
out, memory, window, d = sys.argv[1:5]
ctx = '"$CLAUDE_PROJECT_DIR"/builder/template/tools/context'
log = ("python3 -c 'import json,sys,time; d=json.load(sys.stdin); d[\"at\"]=time.time(); "
       f"open(\"{d}/harness/events.jsonl\",\"a\").write(json.dumps(d)+chr(10))'")
hooks = {
    "SessionStart": [{"matcher": "compact", "hooks": [{"type": "command", "command": f"python3 {ctx}/after_compact.py"}]},
                     {"hooks": [{"type": "command", "command": log}]}],
    "PreCompact": [{"hooks": [{"type": "command", "command": log}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": f"python3 {ctx}/after_tool.py"}]}],
}
if memory == "on":
    hooks["PreToolUse"] = [{"matcher": "Read", "hooks": [{"type": "command", "command": f"python3 {ctx}/before_read.py"}]}]
env = {"BUILDER_MEMORY": memory, "BUILDER_HARNESS_LOG": f"{d}/harness/hooks.jsonl"}
if window:
    env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = window
json.dump({"env": env, "hooks": hooks}, open(out, "w"), indent=2)
PY
[ -n "$PROMPT" ] && cp "$PROMPT" "$DIR/PROMPT.md"

CLAUDE_VERSION="$(claude --version 2>/dev/null | head -1 || echo unknown)"
python3 - "$DIR/harness/trial.json" <<PY
import json, sys, time
json.dump({"name": "$NAME", "created": time.strftime("%Y-%m-%d %H:%M:%S"), "builder_commit": "$COMMIT",
           "builder_branch": "$BRANCH", "uncommitted_changes_left_out": int("$DIRTY"),
           "claude_version": "$CLAUDE_VERSION", "compact_window": "$WINDOW" or None,
           "refs": "$REFS" or None, "dir": "$DIR", "memory": "$MEMORY",
           "prompt": "$PROMPT" or None}, open(sys.argv[1], "w"), indent=2)
PY

cat > "$DIR/OPENING.md" <<'TXT'
Paste this, with the slots filled, then your description of the game or tool.

Builder is already in this folder as builder/ (do not clone it). Use Builder
to constrain and direct your work as [ROLE: the game's co-designer and
developer | the tool's developer]. The goal is a page on GitHub Pages that
anyone can open in a browser, so put running well in the browser first.

Earlier projects built with Builder, to read for what works:
[REFERENCES, or "none"]. List them under References in BRIEF.md. When one
has a digest in refs/, name the digest.

First, read Builder through its cards (python3 <project>/tools/ask.py
--start, then ask.py "question"; open a Builder file only where a card
points) and write the design journal's opening entry: how you will use
Builder for this [game | tool], the rules you will hold to and what holds
each, and your questions as answer chips.

[PERMISSIONS: e.g. "Do not deploy." / "You may create a public repository
named ____ and deploy it to GitHub Pages when the checks pass." /
"Do not use subagents."]
TXT

echo "trial ready: $DIR (Builder $BRANCH @ $COMMIT)"
if [ -n "$PROMPT" ]; then echo "prompt to paste: $DIR/PROMPT.md (the part below its line)"; else echo "opening to paste: $DIR/OPENING.md"; fi
echo "work index: $MEMORY; compaction window: ${WINDOW:-the default}"
echo "when you are done: python3 $HERE/analyze.py $DIR"
if [ "$LAUNCH" = 1 ]; then
  cd "$DIR"
  if [ -n "$WINDOW" ]; then
    echo "launching claude with CLAUDE_CODE_AUTO_COMPACT_WINDOW=$WINDOW"
    exec env CLAUDE_CODE_AUTO_COMPACT_WINDOW="$WINDOW" claude
  fi
  exec claude
fi
