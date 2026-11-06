#!/usr/bin/env bash
# Start a Builder trial: a clean folder with this branch's Builder in it, hooks that
# log compactions, and the opening to paste. Then launch claude there.
#
#   harness/trial.sh NAME                        a trial in ~/Documents/BuilderTrials/NAME
#   harness/trial.sh NAME --compact-window 200000   ask Claude Code to compact at about 200k tokens
#   harness/trial.sh NAME --refs ~/Documents/Builder/refs   copy game digests in as refs/
#   harness/trial.sh NAME --no-launch            set up only
#
# Afterwards: python3 harness/analyze.py ~/Documents/BuilderTrials/NAME
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
[ $# -ge 1 ] || { sed -n '2,10p' "$0"; exit 2; }
NAME="$1"; shift
WINDOW=""; REFS=""; LAUNCH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --compact-window) WINDOW="$2"; shift 2 ;;
    --refs) REFS="$2"; shift 2 ;;
    --no-launch) LAUNCH=0; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done
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

# hooks: put STATE.md back after a compaction, and log each compaction and session start
cat > "$DIR/.claude/settings.json" <<JSON
{
  "hooks": {
    "SessionStart": [
      { "matcher": "compact", "hooks": [ { "type": "command", "command": "python3 \"\$CLAUDE_PROJECT_DIR\"/builder/template/tools/context/after_compact.py" } ] },
      { "hooks": [ { "type": "command", "command": "python3 -c 'import json,sys,time; d=json.load(sys.stdin); d[\"at\"]=time.time(); open(\"$DIR/harness/events.jsonl\",\"a\").write(json.dumps(d)+chr(10))'" } ] }
    ],
    "PreCompact": [
      { "hooks": [ { "type": "command", "command": "python3 -c 'import json,sys,time; d=json.load(sys.stdin); d[\"at\"]=time.time(); open(\"$DIR/harness/events.jsonl\",\"a\").write(json.dumps(d)+chr(10))'" } ] }
    ]
  }
}
JSON

CLAUDE_VERSION="$(claude --version 2>/dev/null | head -1 || echo unknown)"
python3 - "$DIR/harness/trial.json" <<PY
import json, sys, time
json.dump({"name": "$NAME", "created": time.strftime("%Y-%m-%d %H:%M:%S"), "builder_commit": "$COMMIT",
           "builder_branch": "$BRANCH", "uncommitted_changes_left_out": int("$DIRTY"),
           "claude_version": "$CLAUDE_VERSION", "compact_window": "$WINDOW" or None,
           "refs": "$REFS" or None, "dir": "$DIR"}, open(sys.argv[1], "w"), indent=2)
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
echo "opening to paste: $DIR/OPENING.md"
echo "when you are done: python3 $HERE/analyze.py $DIR"
if [ "$LAUNCH" = 1 ]; then
  cd "$DIR"
  if [ -n "$WINDOW" ]; then
    echo "launching claude with CLAUDE_CODE_AUTO_COMPACT_WINDOW=$WINDOW"
    exec env CLAUDE_CODE_AUTO_COMPACT_WINDOW="$WINDOW" claude
  fi
  exec claude
fi
