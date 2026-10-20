"""Tests for the office-intake kit. Standard library only.

    python3 -m unittest discover -s kits/office-intake/tests

Each test runs the intake on the sample submission in templates/sample/
against a fresh copy of Builder's template/. Expected values are typed from
the sample's files by hand, never copied from the intake's own output.
"""
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
ROOT = KIT.parents[1]
sys.path.insert(0, str(KIT / "tools" / "intake"))
import intake  # noqa: E402

SAMPLE = KIT / "templates" / "sample"
TEMPLATES = KIT / "templates"
PRIVATE = ["Student A Placeholder", "Student B Placeholder", "Student C Placeholder",
           "Student D Placeholder", "Sundays at 7", "Team charter", "Made the folder"]


def rewrite_docx(src, dest, change):
    """Copy a .docx, passing word/document.xml through change(text) -> text."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = change(data.decode()).encode()
            zout.writestr(item, data)


class IntakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "game"
        self.project.mkdir()
        for name in ("BRIEF.md", "GLOSSARY.md", "TRIAGE.md", "LICENSES.md"):
            shutil.copy(ROOT / "template" / name, self.project / name)
        self.journal = self.tmp / "game-journal"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def submission(self, change=None):
        """A copy of the sample, with its design document passed through change."""
        sub = self.tmp / "submission"
        shutil.copytree(SAMPLE, sub)
        if change:
            rewrite_docx(SAMPLE / "GameDesign.docx", sub / "GameDesign.docx", change)
        return sub

    def read(self, name):
        return (self.project / name).read_text()

    def run_intake(self, sub):
        return intake.run(sub, self.project, self.journal)

    def test_the_design_document_lands_in_the_brief_word_for_word(self):
        self.run_intake(self.submission())
        brief = self.read("BRIEF.md")
        self.assertIn("> Lava Lanes is a three-lane runner. You hop between lanes to dodge falling rocks", brief)
        self.assertIn("> **5. Winning and losing**", brief)
        self.assertIn("> We asked Copilot for ten name ideas", brief)

    def test_words_become_glossary_entries_with_not_lines(self):
        self.run_intake(self.submission())
        glossary = self.read("GLOSSARY.md")
        self.assertIn("### Gem\n\nA pickup worth 10 points.\n\nNot: coin, crystal\n", glossary)
        terms = re.findall(r"^### (.+)$", re.sub(r"<!--.*?-->", "", glossary, flags=re.S), flags=re.M)
        self.assertEqual(terms, ["Cool pool", "Gem", "Heart", "Lane", "Lava"])

    def test_game_sheets_land_in_data_with_their_values(self):
        self.run_intake(self.submission())
        game = json.loads(self.read("data/game.json"))
        self.assertEqual(len(game["levels"]), 5)
        self.assertEqual(game["levels"][4]["time_limit_seconds"], "90")
        ember = next(t for t in game["things"] if t["name"] == "Ember")
        self.assertEqual((ember["speed"], ember["health"]), ("4", "3"))
        self.assertEqual(game["controls"][2], {"action": "Jump", "key_or_click": "Space"})
        self.assertEqual(game["rules"][0]["expected_result"], "Ember has 2 hearts")

    def test_changes_become_numbered_triage_rows(self):
        self.run_intake(self.submission())
        triage = self.read("TRIAGE.md")
        self.assertIn("| T1 | Ember moves too slowly between lanes. |", triage)
        self.assertIn("| T2 | Make the gem chime quieter. |", triage)
        self.assertNotIn("| T1 | | |", triage)

    def test_assets_land_in_licences(self):
        self.run_intake(self.submission())
        self.assertIn("| `rumble.wav` | Kenney | CC0 | https://kenney.nl/assets |", self.read("LICENSES.md"))

    def test_no_private_text_reaches_any_output(self):
        sub = self.submission()
        zipped = self.tmp / "submission.zip"
        with zipfile.ZipFile(zipped, "w") as z:
            for f in sub.iterdir():
                z.write(f, "CIS110 Team 04 - Lava Lanes/" + f.name)
        self.run_intake(zipped)
        written = [p for p in self.tmp.rglob("*") if p.is_file() and "submission" not in p.parts[len(self.tmp.parts):][0]]
        self.assertTrue(written)
        for path in written:
            text = path.read_bytes().decode("utf-8", "ignore")
            for word in PRIVATE:
                self.assertNotIn(word, text, f"{word!r} reached {path}")

    def test_a_name_in_the_text_stops_the_intake_before_it_writes(self):
        before = self.read("BRIEF.md")
        sub = self.submission(lambda x: x.replace("Lava Lanes is a three-lane runner.",
                                                  "Student B Placeholder made Lava Lanes, a three-lane runner."))
        with self.assertRaises(intake.IntakeError) as caught:
            self.run_intake(sub)
        self.assertIn("A student's name would be written", str(caught.exception))
        self.assertEqual(self.read("BRIEF.md"), before)

    def test_a_missing_heading_is_reported(self):
        sub = self.submission(lambda x: x.replace(">5. Winning and losing<", ">Winning<"))
        self.run_intake(sub)
        report = self.read("INTAKE.md")
        self.assertIn('the heading "5. Winning and losing"', report)
        self.assertIn('an extra heading "Winning"', report)

    def test_a_missing_file_is_reported(self):
        sub = self.submission()
        (sub / "GamePitch.pptx").unlink()
        self.run_intake(sub)
        self.assertIn("- GamePitch.pptx", self.read("INTAKE.md").split("## Missing")[1].split("##")[0])

    def test_the_slides_are_listed_in_order(self):
        self.run_intake(self.submission())
        report = self.read("INTAKE.md")
        self.assertIn("1. Lava Lanes / Team 04", report)
        self.assertIn("6. What we cut and why / We cut a second character", report)

    def test_a_project_that_already_has_a_description_is_refused(self):
        self.run_intake(self.submission())
        shutil.rmtree(self.tmp / "submission")
        with self.assertRaises(intake.IntakeError):
            self.run_intake(self.submission())

    def test_the_blank_templates_match_the_layout(self):
        sections, _ = intake.read_docx((TEMPLATES / "GameDesign.docx").read_bytes())
        self.assertEqual([h for h, _ in sections if h], intake.LAYOUT["headings"])
        slides, _ = intake.read_pptx((TEMPLATES / "GamePitch.pptx").read_bytes())
        self.assertEqual(len(slides), len(intake.LAYOUT["slides"]))
        sheets = intake.read_xlsx((TEMPLATES / "GameData.xlsx").read_bytes())
        self.assertEqual(list(sheets), [s["name"] for s in intake.LAYOUT["sheets"]])
        for spec in intake.LAYOUT["sheets"]:
            if spec["columns"]:
                self.assertEqual(sheets[spec["name"]][0], spec["columns"], spec["name"])

    def test_the_blank_templates_carry_no_author(self):
        for name in ("GameDesign.docx", "GamePitch.pptx", "GameData.xlsx"):
            with zipfile.ZipFile(TEMPLATES / name) as z:
                core = z.read("docProps/core.xml").decode()
            self.assertIsNone(re.search(r"<dc:creator>[^<]+</dc:creator>", core), name)


if __name__ == "__main__":
    unittest.main()
