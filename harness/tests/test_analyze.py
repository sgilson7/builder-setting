"""The harness proves itself: a made-up transcript with planted slips that
analyze.py must find, and look-alikes it must not count.

Each planted slip is one the first trial's report missed or got wrong:
STATE.md written through a shell heredoc, a Builder file read with cat,
code written outside crates/ and web/, a file rewritten whole, and a file
read again after a compaction. scripts/prove-checks.sh breaks each detector in
a copy of analyze.py and requires this test to fail.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analyze", HERE / "analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)

LONG = "\n".join(f"line {i}" for i in range(260))


def transcript(calls):
    """calls: [(context tokens, [(tool name, input, result text)])] as Claude Code JSONL."""
    rows, n = [], 0
    for ctx, uses in calls:
        n += 1
        content = []
        results = []
        for j, (name, inp, out) in enumerate(uses):
            tid = f"t{n}_{j}"
            content.append({"type": "tool_use", "id": tid, "name": name, "input": inp})
            results.append({"type": "tool_result", "tool_use_id": tid, "content": out})
        rows.append({"type": "assistant", "message": {"id": f"m{n}", "usage": {"input_tokens": 10, "cache_read_input_tokens": ctx},
                                                      "content": content}})
        if results:
            rows.append({"type": "user", "message": {"content": results}})
    return "\n".join(json.dumps(r) for r in rows) + "\n"


class Planted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        calls = [
            (42_000, [("Bash", {"command": "cat builder/CLAUDE.md"}, "x" * 4000)]),
            (50_000, [("Bash", {"command": "python3 proj/tools/ask.py --start"}, "cards")]),
            (60_000, [("Bash", {"command": "cat > notes/page.html <<'EOF'\n<p>see <code>STATE.md</code> and > STATE.md</p>\nEOF"}, "")]),
            (70_000, [("Write", {"file_path": "/w/proj-journal/index.html", "content": "<article>"}, "ok")]),
            (80_000, [("Write", {"file_path": "/w/proj/PLAN.md", "content": "# Plan"}, "ok")]),
            (90_000, [("Write", {"file_path": "/w/proj/tools/guide/build.py", "content": "print(1)"}, "ok")]),
            (100_000, [("Bash", {"command": "python3 - <<'EOF'\nimport pathlib\npathlib.Path(\"STATE.md\").write_text(\"# State\")\nEOF"}, "")]),
            (150_000, [("Write", {"file_path": "/w/proj/web/big.js", "content": LONG}, "ok")]),
            (180_000, [("Read", {"file_path": "/w/proj/web/notes.md"}, "y" * 6000)]),
            (220_000, [("Write", {"file_path": "/w/proj/web/big.js", "content": LONG}, "ok")]),
            (240_000, []),
            (60_000, [("Read", {"file_path": "/w/proj/web/notes.md"}, "y" * 6000)]),      # after a compaction
            (70_000, [("Bash", {"command": "python3 tools/ask.py --mine \"deck counts\""}, "cards")]),
        ]
        cls.tmp = Path(tempfile.mkdtemp())
        p = cls.tmp / "s.jsonl"
        p.write_text(transcript(calls))
        cls.f = analyze.analyse([p])

    def test_state_written_through_a_heredoc_counts_and_html_does_not(self):
        self.assertEqual(self.f["memory"]["state_writes"], [7])

    def test_builder_file_read_with_cat_is_seen(self):
        self.assertEqual([r["path"] for r in self.f["reading"]["reads"]], ["CLAUDE.md"])

    def test_code_outside_crates_and_web_counts(self):
        self.assertEqual(self.f["process"]["code_first_write"], 6)

    def test_whole_rewrite_is_counted(self):
        self.assertEqual(self.f["memory"]["rewrites"], 1)
        self.assertTrue(any("rewrote big.js whole" in s["what"] for s in self.f["slips"]))

    def test_reread_after_compaction_and_recall_are_counted(self):
        self.assertEqual(self.f["tokens"]["compactions"], 1)
        self.assertEqual(self.f["memory"]["rereads_after_compaction"], 1)
        self.assertEqual(self.f["memory"]["mine_asks_after_compaction"], 1)

    def test_same_length_compares_equal_spans(self):
        sl = analyze.same_length([100, 100], {"a": [50, 50, 999], "b": [10]})
        self.assertEqual((sl["trial"], sl["baseline_median"], sl["baseline_sessions"]), (200, 100, 1))


class Platformer(unittest.TestCase):
    """Look-alikes from the platformer pair's transcripts."""

    def test_journal_written_by_python_through_a_name_after_cd(self):
        cmd = "cd /w/game-journal && python3 - <<'EOF'\np='index.html'; s=open(p).read()\nopen(p,'w').write(s)\nEOF"
        self.assertEqual([analyze.classify(w) for w in analyze.bash_writes(cmd)], ["journal"])

    def test_helper_called_with_a_path_counts(self):
        cmd = "python3 - <<'EOF'\ndef sub(p, pairs):\n    open(p,'w').write('')\nsub('web/app.js',[])\nEOF"
        self.assertIn("web/app.js", analyze.bash_writes(cmd))

    def test_cat_of_a_check_script_is_not_a_check_run(self):
        self.assertFalse(analyze.check_runs("cat web/app.js tests/browser/check.py scripts/build.sh"))
        self.assertTrue(analyze.check_runs("cargo fmt --all && ./scripts/check.sh 2>&1 | tail -15"))


if __name__ == "__main__":
    unittest.main()
