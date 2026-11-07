"""Tests for the work index and the context hooks (template/tools/ask.py,
template/tools/context/). scripts/prove-checks.sh breaks each behaviour in a
copy of the tools ($BUILDER_TOOLS) and requires these tests to fail.

    python3 -m unittest tests/test_context_tools.py
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


class Vectors(unittest.TestCase):
    def test_changed_text_is_embedded_again_and_unchanged_text_never(self):
        v = ask.Vectors.__new__(ask.Vectors)
        v.py, v.cache, v.dirty = "python", {}, False
        calls = []
        v._run = lambda texts, mode="doc": calls.append(list(texts)) or [[1.0, 0.0] for _ in texts]
        card = {"id": "a", "title": "A", "text": "one"}
        v.for_cards([card])
        v.for_cards([card])
        self.assertEqual(len(calls), 1)
        v.for_cards([{**card, "text": "two"}])
        self.assertEqual(len(calls), 2)


class Fusion(unittest.TestCase):
    def test_a_card_first_by_keywords_stays_in_the_top_three(self):
        cards = [{"id": f"c{i}", "title": f"card {i}", "text": f"word{i} filler"} for i in range(8)]
        cards[0]["text"] = "rollback netcode for online play"
        idx = ask.Index(cards)
        idx.vecs = [[0.0, 1.0]] + [[1.0, 0.0]] * 7      # the model ranks c0 last
        idx.vectors = type("V", (), {"query": lambda self, q: [1.0, 0.0]})()
        got = [c["id"] for c in idx.search("rollback netcode", 3)]
        self.assertIn("c0", got)


class Memory(unittest.TestCase):
    def test_memory_off_answers_with_a_note(self):
        out = subprocess.run([sys.executable, str(TOOLS / "ask.py"), "--mine", "anything"], capture_output=True, text=True,
                             env={**os.environ, "BUILDER_MEMORY": "off"}).stdout
        self.assertIn("work index is off", out)

    def test_a_file_still_as_the_template_has_it_is_not_this_projects_work(self):
        home = ask.builder_home()
        if not home:
            self.skipTest("Builder not on disk")
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "p"
            (proj / "scripts").mkdir(parents=True)
            (proj / "scripts" / "quiet.sh").write_bytes((home / "template" / "scripts" / "quiet.sh").read_bytes())
            (proj / "scripts" / "mine.sh").write_text("#!/bin/sh\n# my own script\nhello() { echo hi; }\n")
            old = ask.PROJECT
            ask.PROJECT = proj
            try:
                ids = [c["id"] for c in ask.mine_cards()]
            finally:
                ask.PROJECT = old
            self.assertTrue(any(i.startswith("mine.code.scripts.mine") for i in ids))
            self.assertFalse(any(i.startswith("mine.code.scripts.quiet") for i in ids))


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
            env = {"BUILDER_PROJECT": str(proj), "BUILDER_EMBED": "off", "CLAUDE_CODE_AUTO_COMPACT_WINDOW": ""}
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
            env = {"BUILDER_PROJECT": str(proj), "BUILDER_EMBED": "off", "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "200000"}
            at = {"session_id": "s", "transcript_path": str(self.transcript(d, 140_000)), "tool_name": "Bash", "tool_input": {}}
            self.assertIn("past the 133k mark", run_hook("after_tool.py", at, env))


class PushRecall(unittest.TestCase):
    def test_after_a_compaction_the_next_steps_cards_come_with_state(self):
        # the platformer pair: the index arm asked --mine once in 208 calls, so the hook asks for it
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / "tools").mkdir()
            (proj / "STATE.md").write_text("# State\n\n## What is next\n\nTune the vine release boost.\n")
            (proj / "tools" / "ask.py").write_text("import sys\nprint('── card:mine.code.vine.release  ' + ' '.join(sys.argv[1:]))\n")
            r = subprocess.run([sys.executable, str(TOOLS / "context" / "after_compact.py")], input="{}", capture_output=True,
                               text=True, cwd=proj, env={**os.environ, "BUILDER_MEMORY": "on"}, timeout=60)
            self.assertIn("card:mine.code.vine.release  --mine Tune the vine release boost.", r.stdout)
            off = subprocess.run([sys.executable, str(TOOLS / "context" / "after_compact.py")], input="{}", capture_output=True,
                                 text=True, cwd=proj, env={**os.environ, "BUILDER_MEMORY": "off"}, timeout=60)
            self.assertIn("Tune the vine release boost.", off.stdout)
            self.assertNotIn("card:mine", off.stdout)


class ReadAdvice(unittest.TestCase):
    def test_long_whole_read_gets_its_parts_and_a_range_read_gets_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "big.py"
            f.write_text("\n".join(f"def f{i}():\n    return {i}\n" for i in range(200)))
            out = run_hook("before_read.py", {"tool_name": "Read", "tool_input": {"file_path": str(f)}})
            advice = json.loads(out)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("def f0 (line 1)", advice)
            self.assertIn("def f11 (line 34)", advice)
            self.assertEqual(run_hook("before_read.py", {"tool_name": "Read", "tool_input": {"file_path": str(f), "offset": 10}}), "")
            self.assertEqual(run_hook("before_read.py", {"tool_name": "Read", "tool_input": {"file_path": str(f)}},
                                      {"BUILDER_MEMORY": "off"}), "")

    def test_an_image_gets_no_advice(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "shot.png"
            f.write_bytes(b"\x89PNG\r\n\x1a\n\0\0" + b"\n" * 2000)
            self.assertEqual(run_hook("before_read.py", {"tool_name": "Read", "tool_input": {"file_path": str(f)}}), "")


if __name__ == "__main__":
    unittest.main()
