#!/usr/bin/env python3
"""Run by Claude Code after each tool call (.claude/settings.json, PostToolUse).

One job, quiet unless needed: the context warning (rule 21). When the
context passes 200k tokens ($BUILDER_CONTEXT_WARN), and again at each further
100k, it tells the agent once: rewrite STATE.md, then ask the person to type
/compact. Under a compaction cap ($CLAUDE_CODE_AUTO_COMPACT_WINDOW; the
template sets 300k) the mark is two thirds of the cap when that is lower:
Claude Code compacts at about five sixths of it, so a 200k mark under a 200k
cap is never reached, and two thirds left 7 to 25 calls before each
compaction in the platformer trials. Under the template's 300k cap the mark
is 200k.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib  # noqa: E402

def warn_at():
    mark = int(os.environ.get("BUILDER_CONTEXT_WARN", "200000"))
    try:
        cap = int(os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "0"))
    except ValueError:
        cap = 0
    return min(mark, cap * 2 // 3) if cap > 0 else mark


WARN = warn_at()
STEP = 100_000


def warn(data, proj):
    ctx = hooklib.last_context(data.get("transcript_path"))
    if not ctx or not proj:
        return
    state = proj / "notes" / "index" / "context-warn.json"
    seen = {}
    try:
        seen = json.loads(state.read_text())
    except (OSError, ValueError):
        pass
    sid = data.get("session_id", "session")
    band = -1 if ctx < WARN else (ctx - WARN) // STEP
    if band <= seen.get(sid, -1):
        if band < seen.get(sid, -1):          # compacted: start again
            seen[sid] = band
            state.write_text(json.dumps(seen))
        return
    seen[sid] = band
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(seen))
    hooklib.tell("PostToolUse",
                 f"The context is now about {ctx // 1000}k tokens, past the {WARN // 1000}k mark (rule 21). Every later "
                 "call re-reads all of it. At the next stopping point: rewrite STATE.md (where the build is, the latest "
                 "commit, decisions in force, what is next, and file:line pointers for what you would otherwise re-read), "
                 "commit, and ask the person to type /compact. Afterwards, start from STATE.md and open only the "
                 "lines it points to.")


def main():
    data = hooklib.hook_input()
    proj = hooklib.project()
    warn(data, proj)
    return 0


if __name__ == "__main__":
    sys.exit(main())
