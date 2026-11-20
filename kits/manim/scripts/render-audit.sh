#!/usr/bin/env bash
# The render audit: render every scene again into a scratch folder and require
# the same bytes as the committed deck/media (Manim Lab R2.6). The everyday check reads
# the manifests and needs no Manim; this one needs .venv-manim and ffmpeg and
# takes about twenty seconds, so it runs outside check.sh: after a change to
# the renderer, the theme or a scene, and before a handoff (Manim Lab PLAN.md P6).
#
#   ./scripts/render-audit.sh
#
# Exits non-zero, naming each file, when a fresh render differs from the
# committed one or a file is on one side only. A difference on another machine
# may be a different Cairo, Pango or x264 rather than a stale render: the
# manifest records the Manim and ffmpeg versions to compare.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv-manim/bin/python
if [ ! -x "$PY" ]; then
  echo "no .venv-manim: run ./scripts/setup-manim.sh first" >&2
  exit 2
fi
fresh="$(mktemp -d)"
trap 'rm -rf "$fresh"' EXIT
"$PY" tools/manim/build.py --out "$fresh"
if diff -rq deck/media "$fresh"; then
  echo "render audit: a fresh render matches deck/media byte for byte"
else
  echo "render audit FAILED: the files above differ from a fresh render" >&2
  exit 1
fi
