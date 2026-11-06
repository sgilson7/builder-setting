#!/usr/bin/env bash
# Set up an A/B pair of trials: one prompt, one cap, the work index on in one
# arm and off in the other. Everything else is the same commit of Builder,
# the same digests and the same hooks (the context warning runs in both).
#
#   harness/ab.sh platformer --prompt harness/prompts/platformer.md \
#       --compact-window 200000 --refs ~/Documents/Builder/refs
#
# Makes ~/Documents/BuilderTrials/NAME-index and NAME-plain, launches neither,
# and says which to run first (a coin flip, so order is not a hidden factor).
# Afterwards:
#   python3 harness/analyze.py ~/Documents/BuilderTrials/NAME-index
#   python3 harness/analyze.py ~/Documents/BuilderTrials/NAME-plain
#   python3 harness/analyze.py --compare ~/Documents/BuilderTrials/NAME-index ~/Documents/BuilderTrials/NAME-plain
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ $# -ge 1 ] || { sed -n '2,15p' "$0"; exit 2; }
NAME="$1"; shift
"$HERE/trial.sh" "$NAME-index" --memory on --no-launch "$@"
"$HERE/trial.sh" "$NAME-plain" --memory off --no-launch "$@"
TRIALS="${BUILDER_TRIALS:-$HOME/Documents/BuilderTrials}"
if [ $((RANDOM % 2)) -eq 0 ]; then first="$NAME-index"; second="$NAME-plain"; else first="$NAME-plain"; second="$NAME-index"; fi
cat <<TXT

Two trials are ready. Run them one at a time, $first first (a coin flip):

  cd $TRIALS/$first && claude      # paste PROMPT.md's text below its line
  cd $TRIALS/$second && claude     # the same text

The cap and the work-index switch are in each folder's .claude/settings.json,
so start claude in the folder itself, not from elsewhere. Answer or steer both
the same way. When both are done, run the three analyze.py lines at the top
of harness/ab.sh.
TXT
