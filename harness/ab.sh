#!/usr/bin/env bash
# Set up an A/B pair of trials: one prompt, one cap, the work index on in one
# arm and off in the other. Everything else is the same commit of Builder,
# the same digests and the same hooks (the context warning runs in both).
#
#   harness/ab.sh platformer --prompt harness/prompts/platformer.md \
#       --compact-window 200000 --refs ~/Documents/Builder/refs
#
# Options of its own:
#   --also-cap N     a third arm, NAME-index<N/1000>k: the work index on and the
#                    cap at N, to test whether recall makes a lower cap safe
#   --first ARM      run this arm first (plain, index, or the third arm's name);
#                    the rest follow in coin-flip order. Without it, all coin flips.
#
# Makes ~/Documents/BuilderTrials/NAME-index and NAME-plain (and the third),
# launches none, and says the order. Afterwards:
#   python3 harness/analyze.py ~/Documents/BuilderTrials/NAME-<arm>     (each arm)
#   python3 harness/analyze.py --compare ~/Documents/BuilderTrials/NAME-index ~/Documents/BuilderTrials/NAME-plain [third]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ $# -ge 1 ] || { sed -n '2,19p' "$0"; exit 2; }
NAME="$1"; shift
ALSO=""; FIRST=""; PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --also-cap) ALSO="$2"; shift 2 ;;
    --first) FIRST="$2"; shift 2 ;;
    *) PASS+=("$1"); shift ;;
  esac
done
"$HERE/trial.sh" "$NAME-index" --memory on --no-launch "${PASS[@]}"
"$HERE/trial.sh" "$NAME-plain" --memory off --no-launch "${PASS[@]}"
ARMS=("$NAME-index" "$NAME-plain")
if [ -n "$ALSO" ]; then
  THIRD="$NAME-index$((ALSO / 1000))k"
  # the same options with the cap replaced: trial.sh takes the last --compact-window given
  "$HERE/trial.sh" "$THIRD" --memory on --no-launch "${PASS[@]}" --compact-window "$ALSO"
  ARMS+=("$THIRD")
fi
TRIALS="${BUILDER_TRIALS:-$HOME/Documents/BuilderTrials}"
ORDER=()
if [ -n "$FIRST" ]; then
  case "$FIRST" in "$NAME-"*) ;; *) FIRST="$NAME-$FIRST" ;; esac
  printf '%s\n' "${ARMS[@]}" | grep -qx "$FIRST" || { echo "--first: no arm $FIRST" >&2; exit 2; }
  ORDER+=("$FIRST")
fi
REST=()
for a in "${ARMS[@]}"; do [ "$a" = "$FIRST" ] || REST+=("$a"); done
# coin flips for the rest (Fisher-Yates), so order is not a hidden factor
for ((i = ${#REST[@]} - 1; i > 0; i--)); do j=$((RANDOM % (i + 1))); t="${REST[i]}"; REST[i]="${REST[j]}"; REST[j]="$t"; done
ORDER+=("${REST[@]}")
echo
echo "${#ORDER[@]} trials are ready. Run them one at a time, in this order:"
echo
n=1
for a in "${ORDER[@]}"; do
  echo "  $n. cd $TRIALS/$a && claude      # paste PROMPT.md's text below its line"
  n=$((n + 1))
done
cat <<TXT

The cap and the work-index switch are in each folder's .claude/settings.json,
so start claude in the folder itself, not from elsewhere. Answer or steer every
arm the same way. When all are done, run the analyze.py lines at the top of
harness/ab.sh.
TXT
printf '%s\n' "${ORDER[@]}" > "$TRIALS/$NAME-order.txt"
