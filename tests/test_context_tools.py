"""Tests for the context hooks (template/tools/context/) and the template's
compaction cap. scripts/prove-checks.sh breaks each behaviour in a
copy of the tools ($BUILDER_TOOLS) and requires these tests to fail.

    python3 -m unittest tests/test_context_tools.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(os.environ.get("BUILDER_TOOLS") or Path(__file__).resolve().parents[1] / "template" / "tools")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ask = load(TOOLS / "ask.py", "ask_under_test")


def run_hook(name, data, env=None):
    r = subprocess.run([sys.executable, str(TOOLS / "context" / name)], input=json.dumps(data), capture_output=True,
                       text=True, env={**os.environ, **(env or {})}, timeout=60)
    return r.stdout.strip()


class ContextWarning(unittest.TestCase):
    def transcript(self, d, ctx):
        p = Path(d) / "s.jsonl"
        p.write_text(json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 1, "cache_read_input_tokens": ctx}}}) + "\n")
        return p

    def test_warns_once_past_200k_and_not_below(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "p"
            (proj / "tools").mkdir(parents=True)
            (proj / "STATE.md").write_text("# State\n")
            (proj / "tools" / "ask.py").write_text("")
            env = {"BUILDER_PROJECT": str(proj), "CLAUDE_CODE_AUTO_COMPACT_WINDOW": ""}
            low = {"session_id": "s", "transcript_path": str(self.transcript(d, 150_000)), "tool_name": "Bash", "tool_input": {}}
            self.assertEqual(run_hook("after_tool.py", low, env), "")
            high = {**low, "transcript_path": str(self.transcript(d, 250_000))}
            self.assertIn("past the 200k mark", run_hook("after_tool.py", high, env))
            self.assertEqual(run_hook("after_tool.py", high, env), "")

    def test_under_a_200k_cap_the_mark_is_133k(self):
        # the platformer pair: compacted at about 167k under a 200k cap, so a 200k mark never fired
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "p"
            (proj / "tools").mkdir(parents=True)
            (proj / "STATE.md").write_text("# State\n")
            (proj / "tools" / "ask.py").write_text("")
            env = {"BUILDER_PROJECT": str(proj), "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "200000"}
            at = {"session_id": "s", "transcript_path": str(self.transcript(d, 140_000)), "tool_name": "Bash", "tool_input": {}}
            self.assertIn("past the 133k mark", run_hook("after_tool.py", at, env))


class AfterCompaction(unittest.TestCase):
    def test_state_comes_back_and_no_index_is_asked(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / "tools").mkdir()
            (proj / "STATE.md").write_text("# State\n\n## What is next\n\nTune the vine release boost.\n")
            (proj / "tools" / "ask.py").write_text("import sys\nprint('── card:mine.code.vine.release')\n")
            r = subprocess.run([sys.executable, str(TOOLS / "context" / "after_compact.py")], input="{}", capture_output=True,
                               text=True, cwd=proj, timeout=60)
            self.assertIn("Tune the vine release boost.", r.stdout)
            self.assertNotIn("card:mine", r.stdout)


class CompactionCap(unittest.TestCase):
    SETTINGS = TOOLS.parent / ".claude" / "settings.json"

    def test_the_template_compacts_at_300k_and_the_warning_comes_at_200k(self):
        env = json.loads(self.SETTINGS.read_text()).get("env", {})
        self.assertEqual(env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW"), "300000")
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "p"
            (proj / "tools").mkdir(parents=True)
            (proj / "STATE.md").write_text("# State\n")
            (proj / "tools" / "ask.py").write_text("")
            t = Path(d) / "s.jsonl"
            t.write_text(json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 1, "cache_read_input_tokens": 210_000}}}) + "\n")
            out = run_hook("after_tool.py", {"session_id": "s", "transcript_path": str(t), "tool_name": "Bash", "tool_input": {}},
                           {"BUILDER_PROJECT": str(proj), "CLAUDE_CODE_AUTO_COMPACT_WINDOW": env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"]})
            self.assertIn("past the 200k mark", out)

    def test_no_hook_reads_files_before_the_agent_does(self):
        hooks = json.loads(self.SETTINGS.read_text())["hooks"]
        self.assertNotIn("PreToolUse", hooks)


if __name__ == "__main__":
    unittest.main()
