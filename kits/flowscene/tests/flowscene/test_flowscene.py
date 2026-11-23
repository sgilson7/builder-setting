#!/usr/bin/env python3
"""Checks on the FlowScene kit: plain python3, stdlib only.

    python3 -m unittest discover -s tests/flowscene

Each test was seen to fail against a planted defect (Builder's
scripts/prove-checks.sh; the kit README lists them).
"""
import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "flowscene"))
import check  # noqa: E402

SAMPLE = json.loads((ROOT / "deck" / "flows" / "sample.json").read_text())
ENGINE = (ROOT / "deck" / "flowscene" / "engine.js").read_text()
PAGE = (ROOT / "deck" / "flowscene-sample.html").read_text()


def code_of(js):
    """JavaScript with its comments and string literals blanked."""
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`',
                  lambda m: " " if m[0].startswith("/") else '""', js, flags=re.S)


class Scenes(unittest.TestCase):
    def refused(self, edit):
        """The sample, edited, must be refused; returns why."""
        s = copy.deepcopy(SAMPLE)
        edit(s)
        with self.assertRaises(check.FlowError) as e:
            check.validate(s)
        return str(e.exception)

    def test_the_committed_scenes_are_valid(self):
        for p in sorted((ROOT / "deck" / "flows").glob("*.json")):
            check.load(p)

    def test_a_path_through_a_missing_node_is_refused(self):
        msg = self.refused(lambda s: s["flows"][0]["steps"][0]["go"][0]["path"].append("nowhere"))
        self.assertIn("path names node nowhere", msg)

    def test_a_mark_between_unjoined_nodes_is_refused(self):
        # page and db are both in the sample, with no edge between them
        msg = self.refused(lambda s: s["flows"][0]["steps"][0]["go"].__setitem__(0, {"path": ["page", "db"], "kind": "req"}))
        self.assertIn("a mark goes page to db, and no edge is drawn between them", msg)

    def test_a_highlight_outside_its_excerpt_is_refused(self):
        # "post" starts at line 10 and holds five lines, so 10-14; 15 is outside
        msg = self.refused(lambda s: s["flows"][0]["steps"][0].__setitem__("hl", [14, 15]))
        self.assertIn("highlights lines 14-15; post holds 10-14", msg)

    def test_an_excerpt_the_scene_lacks_is_refused(self):
        msg = self.refused(lambda s: s["flows"][0]["steps"][0].__setitem__("c", "nothing"))
        self.assertIn("shows excerpt 'nothing'", msg)

    def test_a_step_without_words_is_refused(self):
        msg = self.refused(lambda s: s["flows"][1]["steps"][0].__setitem__("t", "  "))
        self.assertIn("flow offline step 1: needs words", msg)

    def test_an_unknown_mark_kind_is_refused(self):
        msg = self.refused(lambda s: s["flows"][0]["steps"][0]["go"][0].__setitem__("kind", "ping"))
        self.assertIn("mark kind 'ping'", msg)

    def test_a_fraction_in_a_node_is_refused(self):
        msg = self.refused(lambda s: s["nodes"]["page"].__setitem__(0, 110.5))
        self.assertIn("node page x: 110.5 is not an integer", msg)


class Engine(unittest.TestCase):
    def test_every_label_the_engine_reads_is_on_the_sample_page(self):
        labels = json.loads(re.search(r'id="flow-labels">\n(.*?)\n</script>', PAGE, re.S)[1])
        used = set(re.findall(r"\bL\.(\w+)", ENGINE))
        self.assertEqual(sorted(used - set(labels)), [])
        self.assertEqual(sorted(labels["kinds"]), sorted(check.MARK_KINDS))

    def test_the_engine_holds_no_words_of_its_own(self):
        # words reach the reader only from the labels script and the scene file
        strings = re.findall(r'"((?:\\.|[^"\\\n])*)"', re.sub(r"/\*.*?\*/", " ", ENGINE, flags=re.S))
        # prose: two plain words in a row (class lists like "fx-node fx-" are hyphenated),
        # or one capitalised word such as "Play"
        prose = [s for s in strings if s != "use strict"
                 and (re.search(r"(?<![\w-])[A-Za-z]{2,} [A-Za-z]{2,}(?![\w-])", s) or re.fullmatch(r"[A-Z][a-z]+", s))]
        self.assertEqual(prose, [])

    def test_the_engine_parses_no_html(self):
        code = code_of(ENGINE)
        self.assertEqual(re.findall(r"\b(?:innerHTML|outerHTML|insertAdjacentHTML|eval)\b", code), [])


if __name__ == "__main__":
    unittest.main()
