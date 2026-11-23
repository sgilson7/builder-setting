"""Tests for the journal's animations (template/tools/journal/animate.py).
scripts/prove-checks.sh breaks each behaviour in a copy of the tools
($BUILDER_TOOLS) and requires these tests to fail.

    python3 -m unittest tests/test_journal_animate.py
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS = Path(os.environ.get("BUILDER_TOOLS") or Path(__file__).resolve().parents[1] / "template" / "tools")
sys.path.insert(0, str(TOOLS / "journal" / "flowscene"))
spec = importlib.util.spec_from_file_location("animate_under_test", TOOLS / "journal" / "animate.py")
animate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(animate)

PAGE = """<!doctype html><html><body>
<article class="entry" id="2026-11-23-plan" data-kind="plan"><div class="entry-body">
<!--FLOW id=press-->
<!--/FLOW-->
</div></article>
</body></html>
"""


def scene(**over):
    s = {"id": "press", "title": "A press, from key to screen", "viewBox": "0 0 600 200",
         "status": "measured", "from": "crates/core/src/api.rs act()",
         "nodes": {"page": [100, 100, "Page", "client"], "core": [300, 100, "Core"], "ui": [500, 100, "ui()", "store"]},
         "edges": [["page", "core"], ["core", "ui"]],
         "flows": [{"id": "add", "title": "Add one", "sum": "The page asks; the core decides.",
                    "steps": [{"t": "The page sends act(\"add\").", "go": [{"path": ["page", "core"], "kind": "req"}]},
                              {"t": "The core returns the screen.", "go": [{"path": ["core", "ui"], "kind": "res"}]}]}]}
    s.update(over)
    return s


class Journal:
    def __init__(self, page=PAGE, scenes=(scene(),)):
        self.tmp = tempfile.TemporaryDirectory()
        self.where = Path(self.tmp.name)
        (self.where / "flows").mkdir()
        (self.where / "index.html").write_text(page)
        for s in scenes:
            (self.where / "flows" / f"{s['id']}.json").write_text(json.dumps(s))

    def build(self):
        with redirect_stdout(io.StringIO()):
            return animate.main([str(self.where)])

    def problems(self):
        return animate.problems(self.where)

    def page(self):
        return (self.where / "index.html").read_text()


class Case(unittest.TestCase):
    def journal(self, *a, **kw):
        j = Journal(*a, **kw)
        self.addCleanup(j.tmp.cleanup)
        return j


class Placing(Case):
    def test_a_placed_scene_becomes_a_figure_with_every_step_as_text(self):
        j = self.journal()
        self.assertEqual(j.build(), 0)
        page = j.page()
        self.assertIn('data-steps="2"', page)
        self.assertIn("<li>The page sends act(&quot;add&quot;).</li>", page)
        self.assertIn('data-flow-scene="press"', page)
        self.assertEqual(page.count("<!--FLOWSCENE-->"), 1)
        self.assertEqual(j.problems(), [])

    def test_a_page_without_a_closing_body_tag_still_gets_the_engine(self):
        j = self.journal(page=PAGE.replace("</body></html>", ""))
        j.build()
        self.assertEqual(j.page().count("<!--FLOWSCENE-->"), 1)
        self.assertEqual(j.problems(), [])

    def test_building_twice_changes_nothing(self):
        j = self.journal()
        j.build()
        once = j.page()
        j.build()
        self.assertEqual(j.page(), once)

    def test_closing_script_text_in_a_step_cannot_end_the_scene_early(self):
        s = scene()
        s["flows"][0]["steps"][0]["t"] = "It prints </script> and stops."
        j = self.journal(scenes=(s,))
        j.build()
        inline = j.page().split('data-flow-scene="press">', 1)[1].split("</script>", 1)[0]
        self.assertIn("<\\/script>", inline)


class Refusing(Case):
    def test_an_edited_scene_leaves_the_page_out_of_date(self):
        j = self.journal()
        j.build()
        s = scene()
        s["flows"][0]["steps"][1]["t"] = "The core returns the new screen."
        (j.where / "flows" / "press.json").write_text(json.dumps(s))
        self.assertTrue(any("out of date" in p for p in j.problems()))

    def test_a_placed_scene_with_no_file_is_refused(self):
        j = self.journal(scenes=())
        self.assertTrue(any("flows/press.json does not exist" in p for p in j.problems()))

    def test_a_scene_placed_in_no_entry_is_reported(self):
        j = self.journal(scenes=(scene(), scene(id="loose")))
        j.build()
        self.assertTrue(any("flows/loose.json is placed in no entry" in p for p in j.problems()))

    def test_a_measured_scene_says_where_its_steps_came_from(self):
        j = self.journal(scenes=(scene(**{"from": ""}),))
        self.assertTrue(any("where its steps came from" in p for p in j.problems()))

    def test_a_scene_without_a_status_is_refused(self):
        s = scene()
        del s["status"]
        j = self.journal(scenes=(s,))
        self.assertTrue(any("status None, not one of" in p for p in j.problems()))

    def test_a_mark_between_unjoined_boxes_is_refused(self):
        s = scene()
        s["flows"][0]["steps"][0]["go"][0]["path"] = ["page", "ui"]
        j = self.journal(scenes=(s,))
        self.assertTrue(any("no edge is drawn" in p for p in j.problems()))

    def test_an_illustrative_scene_needs_no_source(self):
        j = self.journal(scenes=(scene(status="illustrative", **{"from": ""}),))
        j.build()
        self.assertEqual(j.problems(), [])


if __name__ == "__main__":
    unittest.main()
