#!/usr/bin/env python3
"""Write the three student templates and a filled sample submission.

    python3 make_templates.py

Needs python-docx, python-pptx and openpyxl. They are needed only to
regenerate these files; the intake script reads Office files with the
standard library. The headings, slide titles and sheet names come from
layout.json, which the intake script reads too, so the two cannot drift.
"""
import json
from pathlib import Path

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Font
from pptx import Presentation
from pptx.util import Inches, Pt as PPt

HERE = Path(__file__).resolve().parent
LAYOUT = json.loads((HERE.parent / "tools" / "intake" / "layout.json").read_text())

# Each Word heading's prompt, in the order of layout.json's "headings".
PROMPTS = [
    "Describe your game in two sentences. Say what the player does and why it is fun.",
    "Say who the player is and what they are trying to do. One short paragraph.",
    "List every key, click, or tap the player uses, and what each one does.",
    "Write each rule of the game as one sentence. Use exact numbers. Put the full list in the Rules sheet of GameData.xlsx.",
    "Say exactly how the player wins and how the player loses.",
    "Walk through one round from start to finish: what the player sees, decides, and does.",
    "Describe each screen: the start screen, the game screen, and the end screen. Say what is on each one.",
    "Describe the look, the sounds, and the mood. Name any images or sounds you plan to use, and list them in the Assets sheet.",
    "Make three lists: Must have, Nice to have, and Left out. Keep Must have short enough to build in a week.",
    "If you used AI for any part of this project, say which tool, what you asked it, and how you checked its answer. If you did not use AI, write \"We did not use AI.\"",
]

SLIDE_PROMPTS = [
    "Game name\nTeam number",
    "Say the idea of your game in one or two sentences.",
    "Draw the loop the player repeats, with a SmartArt cycle or arrows.",
    "List the three to five rules that matter most.",
    "Draw one screen of your game with shapes. Label each part.",
    "List the ideas you cut, and say why you cut each one.",
]

START_HERE = [
    "How to use this workbook",
    "Fill in one row for each thing in your game. Keep the header row as it is.",
    "Use exact numbers. Write 3, not \"a few\".",
    "Rules: write each rule with a worked example and the result you expect.",
    "Words: list the words your game uses, what each one means, and any word not to use for it.",
    "Assets: list every image or sound, who made it, and its licence.",
    "Changes: after you play the prototype, write each change you want in your own words.",
    "Team: this sheet stays private. It is never copied into the game.",
]

COLUMNS = {s["name"]: s["columns"] for s in LAYOUT["sheets"]}


def write_docx(path, title, bodies, author):
    doc = Document()
    doc.core_properties.author = author
    doc.core_properties.last_modified_by = author
    doc.add_heading(title, level=0)
    for heading, body in zip(LAYOUT["headings"], bodies):
        doc.add_heading(heading, level=1)
        for line in body:
            p = doc.add_paragraph()
            run = p.add_run(line)
            if body is not None and line in PROMPTS:
                run.italic = True
            run.font.size = Pt(11)
    doc.save(path)


def write_pptx(path, texts, author):
    prs = Presentation()
    prs.core_properties.author = author
    prs.core_properties.last_modified_by = author
    for i, (title, text) in enumerate(zip(LAYOUT["slides"], texts)):
        slide = prs.slides.add_slide(prs.slide_layouts[0 if i == 0 else 1])
        slide.shapes.title.text = title if i else text.split("\n")[0]
        body = slide.placeholders[1]
        body.text = text if i else "\n".join(text.split("\n")[1:])
        for para in body.text_frame.paragraphs:
            for run in para.runs:
                run.font.size = PPt(20)
    prs.save(path)


def write_xlsx(path, rows, author):
    wb = Workbook()
    wb.properties.creator = author
    wb.properties.lastModifiedBy = author
    first = True
    for name in [s["name"] for s in LAYOUT["sheets"]]:
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = name
        if name == "Start Here":
            for line in START_HERE:
                ws.append([line])
            ws["A1"].font = Font(bold=True, size=14)
            ws.column_dimensions["A"].width = 100
            continue
        ws.append(COLUMNS[name])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for col, header in zip("ABCDEFGH", COLUMNS[name]):
            ws.column_dimensions[col].width = max(14, len(header) + 6)
        for row in rows.get(name, []):
            ws.append(row)
    wb.save(path)


def templates():
    out = HERE
    write_docx(out / "GameDesign.docx", "Game name: Game design document", [[p] for p in PROMPTS], "")
    write_pptx(out / "GamePitch.pptx", SLIDE_PROMPTS, "")
    write_xlsx(out / "GameData.xlsx", {"Team": [["", "", ""], ["Team charter", "", ""],
                                                ["When we meet", "", ""], ["How to reach each other", "", ""],
                                                ["If someone goes quiet", "", ""]]}, "")


# The sample: an invented game from an invented team. The names are
# placeholders, and the author metadata is a planted name the intake must drop.
SAMPLE_AUTHOR = "Student A Placeholder"
SAMPLE_TEAM = [
    ["Student A Placeholder", "Coordinator", "Made the folder, kept the dates, wrote section 9."],
    ["Student B Placeholder", "Design writer", "Wrote sections 1 to 6 of the design document."],
    ["Student C Placeholder", "Data lead", "Filled in the Rules, Levels and Things sheets."],
    ["Student D Placeholder", "Presenter", "Made the slides and the screen mock-up."],
    ["Team charter", "", ""],
    ["When we meet", "Sundays at 7 p.m. on Teams", ""],
    ["How to reach each other", "Comments with @mentions in the files", ""],
    ["If someone goes quiet", "We message them, then tell the instructor after two days", ""],
]
SAMPLE_DOC = [
    ["Lava Lanes is a three-lane runner. You hop between lanes to dodge falling rocks and collect cooling gems before the lava reaches you."],
    ["You play a small salamander named Ember. Ember wants to reach the cool pool at the end of each level."],
    ["Left arrow or A moves one lane left. Right arrow or D moves one lane right. Space jumps over a crack. P pauses the game."],
    ["Ember starts with 3 hearts. A rock that lands on Ember's lane takes 1 heart. A gem adds 10 points. Every 5 gems give back 1 heart, up to 3."],
    ["You win when Ember reaches the cool pool at the end of level 5. You lose when Ember has 0 hearts or the lava catches up."],
    ["A round starts in the middle lane. Rocks show a shadow one second before they land. You watch the shadows, move, grab gems, and keep ahead of the lava."],
    ["The start screen shows the title and a Play button. The game screen shows three lanes, the hearts at the top left, and the score at the top right. The end screen shows the score and a Play again button."],
    ["The look is bright orange and dark red rock with a blue pool. The sound is a low rumble and a chime for each gem. We drew all the images ourselves."],
    ["Must have: three lanes, rocks, gems, hearts, five levels. Nice to have: a high score list. Left out: a second character and online play."],
    ["We asked Copilot for ten name ideas and chose Lava Lanes from them. We wrote everything else ourselves."],
]
SAMPLE_SLIDES = [
    "Lava Lanes\nTeam 04",
    "Hop between three lanes to dodge rocks and grab gems before the lava catches you.",
    "Watch the shadows → move → grab gems → reach the pool → next level.",
    "3 hearts. A rock takes 1 heart. A gem adds 10 points. 5 gems give back 1 heart.",
    "Three lanes, hearts at the top left, score at the top right, lava rising from the bottom.",
    "We cut a second character and online play so we could finish five levels.",
]
SAMPLE_ROWS = {
    "Rules": [
        ["A rock takes one heart", "Ember has 3 hearts and a rock lands on her lane", "Ember has 2 hearts"],
        ["A gem adds points", "Score is 40 and Ember grabs a gem", "Score is 50"],
        ["Five gems give back a heart", "Ember has 1 heart and grabs her 5th gem", "Ember has 2 hearts"],
        ["Hearts stop at three", "Ember has 3 hearts and grabs her 10th gem", "Ember still has 3 hearts"],
        ["Losing all hearts ends the game", "Ember has 1 heart and a rock lands on her", "The end screen shows"],
    ],
    "Levels": [
        ["1", "Reach the pool", "60", "Slow rocks"],
        ["2", "Reach the pool", "60", "Cracks appear"],
        ["3", "Reach the pool", "75", "Faster lava"],
        ["4", "Reach the pool", "75", "Rocks fall in pairs"],
        ["5", "Reach the pool", "90", "Everything at once"],
    ],
    "Things": [
        ["Ember", "Player", "4", "3", "0", "The salamander you play"],
        ["Rock", "Hazard", "3", "", "0", "Shadow shows 1 second early"],
        ["Big rock", "Hazard", "2", "", "0", "Covers two lanes"],
        ["Gem", "Pickup", "0", "", "10", "Cools the lava a little"],
        ["Cool pool", "Goal", "0", "", "100", "End of each level"],
    ],
    "Controls": [
        ["Move left", "Left arrow or A"],
        ["Move right", "Right arrow or D"],
        ["Jump", "Space"],
        ["Pause", "P"],
        ["Start", "Enter or click Play"],
    ],
    "Words": [
        ["Heart", "One unit of Ember's health. Ember starts with 3.", "life, HP"],
        ["Gem", "A pickup worth 10 points.", "coin, crystal"],
        ["Lane", "One of the three paths Ember runs along.", "track, row"],
        ["Lava", "The danger rising behind Ember.", "fire"],
        ["Cool pool", "The goal at the end of a level.", "finish line"],
    ],
    "Assets": [
        ["ember.png", "Our team", "Our own drawing", ""],
        ["rock.png", "Our team", "Our own drawing", ""],
        ["gem.png", "Our team", "Our own drawing", ""],
        ["rumble.wav", "Kenney", "CC0", "https://kenney.nl/assets"],
        ["chime.wav", "Kenney", "CC0", "https://kenney.nl/assets"],
    ],
    "Changes": [
        ["1", "Ember moves too slowly between lanes.", "Things sheet, Ember speed", "Rocks hit us before we can move."],
        ["2", "Make the gem chime quieter.", "Assets sheet, chime.wav", "It is louder than the music."],
    ],
    "Team": SAMPLE_TEAM,
}


def sample():
    out = HERE / "sample"
    out.mkdir(exist_ok=True)
    write_docx(out / "GameDesign.docx", "Lava Lanes: Game design document", SAMPLE_DOC, SAMPLE_AUTHOR)
    write_pptx(out / "GamePitch.pptx", SAMPLE_SLIDES, SAMPLE_AUTHOR)
    write_xlsx(out / "GameData.xlsx", SAMPLE_ROWS, SAMPLE_AUTHOR)


if __name__ == "__main__":
    templates()
    sample()
    print("wrote the templates and templates/sample/")
