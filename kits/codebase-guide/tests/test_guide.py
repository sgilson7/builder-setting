"""Tests for the codebase-guide kit, against a small fixture codebase.

Each test was seen failing with the behaviour it guards broken; the reference
repository's scripts/prove-checks.sh plants each break in a copy of this kit.
"""

import importlib.util
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixture"


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, KIT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


excerpts = load("tools/guide/excerpts.py", "kit_excerpts")
unchanged = load("scripts/target_unchanged.py", "kit_unchanged")
labels = load("tools/guide/labels.py", "kit_labels")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(FIXTURE, self.tmp / "f")
        self.project = self.tmp / "f" / "project"
        self.target = self.tmp / "f" / "target"

    def tearDown(self):
        shutil.rmtree(self.tmp)


class Excerpts(Fixture):
    def test_excerpts_in_place_pass(self):
        self.assertEqual(excerpts.problems(self.project), [])

    def test_moved_function_fails_and_says_where_it_went(self):
        app = self.target / "src" / "app.js"
        app.write_text("// a new first line\n" + app.read_text())
        found = excerpts.problems(self.project)
        self.assertEqual(len(found), 2)
        self.assertIn("now at line 3", found[0])

    def test_excerpt_reads_the_named_lines(self):
        e = excerpts.excerpt("save", self.project)
        self.assertEqual(e["first"], 6)
        self.assertEqual(len(e["lines"]), 4)
        self.assertIn("async function saveWork", e["lines"][0])


class Unchanged(Fixture):
    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = unchanged.main(list(argv), project=self.project)
        return code, out.getvalue()

    def test_untouched_codebase_passes(self):
        self.assertEqual(self.run_main("--write")[0], 0)
        self.assertEqual(self.run_main()[0], 0)

    def test_edit_addition_and_install_fail(self):
        self.run_main("--write")
        (self.target / "src" / "app.js").write_text("changed\n")
        (self.target / "node_modules").mkdir()
        (self.target / "node_modules" / "x.js").write_text("installed\n")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("edited src/app.js", out)
        self.assertIn("added node_modules/x.js", out)

    def test_manifest_is_written_once(self):
        self.run_main("--write")
        self.assertEqual(self.run_main("--write")[0], 1)


class Labels(unittest.TestCase):
    def setUp(self):
        self.html = (FIXTURE / "journal.html").read_text()

    def test_fixture_journal_passes(self):
        self.assertEqual(labels.problems(self.html, {"listen", "save"}), [])

    def test_proposed_part_with_code_fails(self):
        bad = self.html.replace("Contract: POST /work", '<pre data-excerpt="listen"></pre> POST /work')
        found = labels.problems(bad, {"listen", "save"})
        self.assertTrue(any("marked proposed but shows code" in p for p in found))

    def test_measured_part_without_code_fails(self):
        bad = self.html.replace('<pre data-excerpt="save"></pre>', "")
        self.assertTrue(any("shows no excerpt" in p for p in labels.problems(bad, {"listen", "save"})))

    def test_unknown_excerpt_fails(self):
        self.assertTrue(any("not in data/excerpts.json" in p for p in labels.problems(self.html, {"listen"})))


if __name__ == "__main__":
    unittest.main()
