#!/usr/bin/env bash
# Test each kit's core code inside a project, as a project that copies it would.
#
# A kit is files to copy, not a crate, so nothing else compiles it. For each
# kit with Rust in crates/core/src/, this copies examples/minimal into a
# scratch directory, adds the kit's modules to the core (and whatever else the
# kit's README tells a project to copy for its tests), and runs the core's
# unit tests and the boundary scan. The kit's own web files and fences are
# not wired into the page here; each kit's README says how.
#
#   ./scripts/check-kits.sh [kit ...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/builder-kits.XXXXXX")"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$WORK/target}"
trap 'rm -rf "$WORK"' EXIT

KITS="${BUILDER_KITS:-$ROOT/kits}"   # prove-checks.sh points this at a planted copy
kits=("$@")
if [ ${#kits[@]} -eq 0 ]; then
  for d in "$KITS"/*/crates/core/src; do kits+=("$(basename "$(dirname "$(dirname "$(dirname "$d")")")")"); done
fi

for kit in "${kits[@]}"; do
  K="$KITS/$kit"
  P="$WORK/$kit"
  rm -rf "$P"; mkdir -p "$P"
  (cd "$ROOT/examples/minimal" && tar --exclude=./target --exclude=./dist --exclude=./.venv -cf - .) | (cd "$P" && tar -xf -)
  for f in "$K"/crates/core/src/*.rs; do
    m="$(basename "$f" .rs)"
    cp "$f" "$P/crates/core/src/$m.rs"
    printf '\npub mod %s;\n' "$m" >> "$P/crates/core/src/lib.rs"
  done
  # a kit's core-level tests that need no web wiring, and the files they read
  if [ -f "$K/check-kits.list" ]; then
    while read -r from to; do
      if [ -z "$from" ] || [ "${from#\#}" != "$from" ]; then continue; fi
      if [ "$from" = "-" ]; then rm -f "$P/$to"; continue; fi
      mkdir -p "$(dirname "$P/$to")"; rm -rf "$P/$to"; cp -R "$K/$from" "$P/$to"
    done < "$K/check-kits.list"
  fi
  printf '\n== kit %s: format, lint, core tests and boundary scan\n' "$kit"
  if ! out="$(cd "$P" && cargo fmt --all -- --check 2>&1 && cargo clippy -q -p tool_core --all-targets -- -D warnings 2>&1 && cargo test -q -p tool_core --no-fail-fast 2>&1)"; then
    printf '%s\n' "$out" | grep -v "^\.*$"
    echo "FAIL kit $kit: its code fails the project's checks"
    exit 1
  fi
  echo "kit $kit: passes inside a copy of examples/minimal"
done
