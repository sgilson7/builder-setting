#!/usr/bin/env python3
"""Run by Claude Code after a compaction (.claude/settings.json, SessionStart "compact").

Whatever this prints is put back in front of the agent: STATE.md, and how to
get the rest without re-reading. It looks for STATE.md in this project, or,
when the session was started in the folder above it, in the newest project
folder there.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]


def find_state(start):
    for cand in [start / "STATE.md"] + sorted(start.glob("*/STATE.md"), key=lambda p: -p.stat().st_mtime):
        if cand.exists():
            return cand
    return None


def main():
    state = find_state(Path.cwd()) or find_state(HERE)
    print("The context was just compacted. Builder's rules still hold (CLAUDE.md is loaded).")
    if state:
        print(f"Read this first; it is the project's long-term memory ({state}):\n")
        print(state.read_text())
    print("Ask Builder through its cards (python3 tools/ask.py \"question\"), and open only the files and "
          "lines STATE.md points to.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
