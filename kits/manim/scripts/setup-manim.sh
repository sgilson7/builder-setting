#!/usr/bin/env bash
# Make .venv-manim: Manim Community, pinned, in its own virtual environment beside
# the browser check's .venv. Needs Homebrew cairo and pango and Python 3.11-3.14.
#
#   ./scripts/setup-manim.sh
#
# pycairo has no macOS wheel and builds against Homebrew's cairo through pkg-config.
# When pkg-config is not installed, the PyPI package pkgconf supplies one; its native
# binary is used directly, because its pkg-config wrapper fails under meson
# (Manim Lab SECOND-ORDER.md R1.5). Every install goes through `python -m pip`, never a `pip`
# script, whose shebang can point at another venv (Manim Lab R1.3).
set -euo pipefail
cd "$(dirname "$0")/.."
PYBIN="${PYBIN:-python3.14}"
command -v "$PYBIN" >/dev/null || PYBIN=python3
[ -x .venv-manim/bin/python ] || "$PYBIN" -m venv .venv-manim
PY=.venv-manim/bin/python
if ! command -v pkg-config >/dev/null; then
  "$PY" -m pip install --quiet pkgconf
  PKG_CONFIG="$("$PY" -c 'import pkgconf, pathlib; print(pathlib.Path(pkgconf.__file__).parent / ".bin" / "pkgconf")')"
  export PKG_CONFIG
fi
BREW="$(brew --prefix 2>/dev/null || echo /opt/homebrew)"
MACPC="$(ls -d "$BREW"/Library/Homebrew/os/mac/pkgconfig/"$(sw_vers -productVersion | cut -d. -f1)" 2>/dev/null || true)"
export PKG_CONFIG_PATH="$BREW/lib/pkgconfig:$BREW/share/pkgconfig${MACPC:+:$MACPC}${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
"$PY" -m pip install --quiet -r requirements-manim.txt
"$PY" -c 'import manim; print("Manim", manim.__version__, "ready in .venv-manim")'
