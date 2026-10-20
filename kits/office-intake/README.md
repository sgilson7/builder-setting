# Office intake kit

This kit turns a student team's game design, written in Word, PowerPoint, and Excel, into the start of a Builder project. You unzip the team's folder, start a coding agent in it, and the agent follows [`prompts/start-from-submission.md`](../../prompts/start-from-submission.md). The kit comes from a community college course where teams of three to five students design a game in a shared Microsoft 365 folder and the instructor builds it.

The kit has three parts:

- **Templates** that students start from: `templates/GameDesign.docx`, `templates/GamePitch.pptx`, and `templates/GameData.xlsx`. A filled sample, an invented game called Lava Lanes, is in `templates/sample/`. A team that designs a tool instead of a game uses `templates/tool/GameDesign.docx`, which keeps the file name and the ten-heading shape but asks about the tool's user, inputs and outputs. Its filled sample, an invented tool called Recipe Scaler, is `templates/sample-tool/GameDesign.docx`.
- **An intake script**, `tools/intake/intake.py`, that copies a submission into a fresh copy of `template/` and reports what is missing.
- **Tests**, `tests/test_intake.py`, that run the intake on the sample.

## What it changes

It changes no reference default. The intake script reads and writes files, so it runs outside the core, like the art pipeline. It copies the team's words and values and decides no game rule (R1): the agent still turns each rule into core code with a test.

## How the files map to Builder

The fixed shape of a submission is in `tools/intake/layout.json`. The templates are generated from it, and the intake checks submissions against it.

| From the team | Goes to | Notes |
| --- | --- | --- |
| `GameDesign.docx`, ten fixed headings | `BRIEF.md`, under "The description, word for word" | Every heading and paragraph, unchanged. The intake checks the document against the game headings or the tool headings, whichever it follows more closely, and says in `INTAKE.md` when it is the tool version. |
| `GameData.xlsx`, Words sheet | `GLOSSARY.md` | A meaning that states a number is flagged, because Builder's glossary writes numbers as `{placeholders}`. |
| `GameData.xlsx`, Rules, Levels, Things, Controls, and any extra sheet | `data/game.json` | Values stay as text, as the team wrote them. The Rules sheet's worked examples are the hand-worked cases for the core's tests. |
| `GameData.xlsx`, Assets sheet | `LICENSES.md` | For you to confirm before you publish. |
| `GameData.xlsx`, Changes sheet | `TRIAGE.md`, rows T1, T2, and so on | In the team's words. |
| `GamePitch.pptx` | `INTAKE.md` (slide text) and the journal's `img/reference/` (slide pictures) | The team's own picture of the game. |
| Other images and sounds in the folder | `data/assets/` | Listed in `INTAKE.md`. |
| `GameData.xlsx`, Team sheet; document author metadata; comments | nowhere | They hold students' names. |

## Privacy

Student names never reach the project. The intake doesn't copy the Team sheet, the files' author metadata, or comments. It reads Team-sheet names and author names only to search for them in what it's about to write. If a name appears, for example in the design document's text, the intake writes nothing and tells you which file the name would have reached.

The search finds names exactly as the Team sheet and the metadata spell them. It can't find a nickname or a first name that appears on its own, so read `BRIEF.md` before you publish.

## Using it

You run the kit from your Builder clone. Unlike the other kits, you don't copy its files into the project.

1. Download the team's shared folder from OneDrive as a `.zip` file.
2. Copy `template/` to a new directory, for example `cis110-team04-lava-lanes/`.
3. Run the intake:

   ```bash
   python3 kits/office-intake/tools/intake/intake.py ~/Downloads/team04.zip cis110-team04-lava-lanes
   ```

4. Read `INTAKE.md`, then follow the procedure in [`prompts/start-from-submission.md`](../../prompts/start-from-submission.md).

The intake needs only the Python standard library. To regenerate the templates after you change `layout.json`, install `python-docx`, `python-pptx`, and `openpyxl`, then run `python3 templates/make_templates.py`.

## Tests

Run the tests from the repository root:

```bash
python3 -m unittest discover -s kits/office-intake/tests
```

Each test listed here was seen to fail against a planted defect in `scripts/prove-checks.sh`:

| Test | Planted defect it catches |
| --- | --- |
| `test_no_private_text_reaches_any_output` | `layout.json` no longer marks the Team sheet private |
| `test_a_name_in_the_text_stops_the_intake_before_it_writes` | the name search is switched off |
| `test_a_missing_heading_is_reported` | the heading check reports nothing |
| `test_the_blank_templates_match_the_layout` | `layout.json` names a heading the game or tool template lacks |
| `test_a_tool_design_document_lands_in_the_brief_with_nothing_missing` | the intake checks a tool document against the game headings |
| `test_the_blank_templates_carry_no_author` | a template carries an author's name |
