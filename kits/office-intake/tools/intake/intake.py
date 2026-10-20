#!/usr/bin/env python3
"""Copy a team's Office submission into a Builder project.

    python3 intake.py SUBMISSION PROJECT [--journal DIR]

SUBMISSION is the team's folder, or the .zip OneDrive downloads for it.
PROJECT is a fresh copy of Builder's template/. The journal defaults to
../<PROJECT>-journal/, as Builder's own journal does.

The intake copies and checks. It decides no game rule (R1): every rule stays
in the team's words, for the agent to turn into core code and tests.

What goes where:

- GameDesign.docx, every heading and paragraph, word for word -> BRIEF.md,
  under "The description, word for word"
- GameData.xlsx: Words -> GLOSSARY.md; Rules, Levels, Things, Controls and
  any extra sheet the team added -> data/game.json; Assets -> LICENSES.md;
  Changes -> TRIAGE.md rows T1, T2, ...
- GamePitch.pptx slide text -> INTAKE.md; slide pictures -> the journal's
  img/reference/
- other images and sounds in the folder -> data/assets/
- INTAKE.md: what was found, what is missing, what the agent must look at

Privacy (GL-5): the intake never copies the Team sheet, the files' author
metadata (docProps) or comments. It reads Team-sheet names and author names
only to look for them in what it is about to write; if one appears, it writes
nothing and says where the name is. Only the Python standard library is used,
so the instructor installs nothing.
"""
import argparse
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

LAYOUT = json.loads((Path(__file__).resolve().parent / "layout.json").read_text())
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
}
MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".wav", ".mp3", ".ogg"}
DATA_SHEETS = ["Rules", "Levels", "Things", "Controls"]
SKIP_SHEETS = {"Start Here", "Words", "Assets", "Changes"}


class IntakeError(Exception):
    pass


# ---------- reading the submission ----------

def load_submission(path):
    """{relative posix path: bytes} for every file in a folder or zip."""
    path = Path(path)
    files = {}
    if path.is_dir():
        for f in sorted(path.rglob("*")):
            if f.is_file() and not f.name.startswith((".", "~$")):
                files[f.relative_to(path).as_posix()] = f.read_bytes()
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                base = PurePosixPath(name).name
                if not name.endswith("/") and not base.startswith((".", "~$")) and "__MACOSX" not in name:
                    files[name] = z.read(name)
    else:
        raise IntakeError(f"{path} is neither a folder nor a .zip file.")
    return files


def find(files, name):
    """The file whose base name matches, ignoring case and folders."""
    hits = [k for k in files if PurePosixPath(k).name.lower() == name.lower()]
    return files[hits[0]] if hits else None


def text_of(node, tag):
    return "".join(t.text or "" for t in node.iter(tag))


def read_docx(data):
    """[(heading, [paragraph, ...])] in order; text before the first Heading 1 goes under ''."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        media = {n: z.read(n) for n in z.namelist() if n.startswith("word/media/")}
    sections = [("", [])]
    w = "{%s}" % NS["w"]
    for p in root.iter(w + "p"):
        style = p.find(f"{w}pPr/{w}pStyle")
        kind = style.get(w + "val") if style is not None else ""
        text = text_of(p, w + "t").strip()
        if kind in ("Heading1", "heading1", "Heading 1"):
            sections.append((text, []))
        elif kind == "Title":
            sections[0][1].append(text)
        elif text:
            sections[-1][1].append(text)
    return sections, media


def read_pptx(data):
    """[[text, ...] per slide], {media name: bytes}."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        names.sort(key=lambda n: int(re.search(r"(\d+)", PurePosixPath(n).name).group(1)))
        slides = []
        a = "{%s}" % NS["a"]
        for n in names:
            root = ET.fromstring(z.read(n))
            slides.append([text_of(p, a + "t").strip() for p in root.iter(a + "p") if text_of(p, a + "t").strip()])
        media = {n: z.read(n) for n in z.namelist() if n.startswith("ppt/media/")}
    return slides, media


def col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(data, skip=()):
    """{sheet name: [[cell text, ...], ...]}. Sheets named in skip are listed with no rows: never read."""
    s = "{%s}" % NS["s"]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(s + "si"):
                shared.append(text_of(si, s + "t"))
        book = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels.iter("{%s}Relationship" % NS["rel"])}
        sheets = {}
        for sh in book.iter(s + "sheet"):
            name = sh.get("name")
            if name in skip:
                sheets[name] = None
                continue
            part = target[sh.get("{%s}id" % NS["r"])].lstrip("/")
            part = part if part.startswith("xl/") else "xl/" + part
            rows = []
            for row in ET.fromstring(z.read(part)).iter(s + "row"):
                cells = {}
                for c in row.iter(s + "c"):
                    kind = c.get("t")
                    if kind == "s":
                        value = shared[int(c.find(s + "v").text)]
                    elif kind == "inlineStr":
                        value = text_of(c, s + "t")
                    else:
                        v = c.find(s + "v")
                        value = v.text if v is not None else ""
                    cells[col_index(c.get("r"))] = (value or "").strip()
                if any(cells.values()):
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            sheets[name] = rows
    return sheets


def private_words(files):
    """Names the intake must not write: Team-sheet names and author metadata. Read only to search for them."""
    words = set()
    for name in LAYOUT["files"].values():
        data = find(files, name)
        if data is None:
            continue
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "docProps/core.xml" in z.namelist():
                core = ET.fromstring(z.read("docProps/core.xml"))
                for tag in ("{%s}creator" % NS["dc"], "{%s}lastModifiedBy" % NS["cp"]):
                    for el in core.iter(tag):
                        if el.text and el.text.strip():
                            words.add(el.text.strip())
    data = find(files, LAYOUT["files"]["data"])
    if data is not None:
        team = read_xlsx(data).get("Team") or []
        for row in team[1:]:
            if row and row[0] and row[0].lower() == "team charter":
                break
            if row and row[0]:
                words.add(row[0])
    return {w for w in words if len(w) >= 3}


# ---------- writing into the project ----------

def md_cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def records(rows):
    if not rows:
        return []
    keys = [re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_") or f"col{i}" for i, h in enumerate(rows[0])]
    return [{k: (r[i] if i < len(r) else "") for i, k in enumerate(keys)} for r in rows[1:]]


def brief_with(brief, sections):
    lines = []
    for heading, paras in sections:
        if heading:
            lines += [f"> **{heading}**", ">"]
        for p in paras:
            lines += [f"> {p}", ">"]
    quote = "\n".join(lines[:-1] if lines and lines[-1] == ">" else lines)
    refuse = IntakeError("BRIEF.md has no empty quote under \"The description, word for word\"; "
                         "the project already holds a description, or it is not a copy of template/.")
    head = "## The description, word for word\n"
    start = brief.find(head)
    if start < 0:
        raise refuse
    body_start = start + len(head)
    nxt = brief.find("\n## ", body_start)
    body_end = len(brief) if nxt < 0 else nxt + 1
    body = brief[body_start:body_end].split("\n")
    quoted = [i for i, line in enumerate(body) if line.startswith(">")]
    if not quoted or any(body[i].lstrip("> ").strip() for i in quoted):
        raise refuse
    body[quoted[0]] = quote
    return brief[:body_start] + "\n".join(body) + brief[body_end:]


def glossary_with(glossary, words, notes):
    entries = []
    for row in records(words):
        term, meaning, nots = row.get("term", ""), row.get("meaning", ""), row.get("not_this_word", "")
        if not term:
            continue
        if not meaning:
            notes.append(f"Words: \"{term}\" has no meaning; it was left out of GLOSSARY.md.")
            continue
        if re.search(r"\d", meaning):
            notes.append(f"Words: \"{term}\" states a number; turn it into a {{placeholder}} the core fills.")
        entry = f"### {term}\n\n{meaning}\n"
        if nots:
            entry += f"\nNot: {', '.join(w.strip() for w in re.split(r'[,;]', nots) if w.strip())}\n"
        entries.append((term.lower(), entry))
    entries.sort()
    return glossary.rstrip("\n") + "\n\n" + "\n".join(e for _, e in entries)


def triage_with(triage, changes):
    rows = []
    for n, row in enumerate(records(changes), start=1):
        request = row.get("request_in_your_words", "")
        if not request:
            continue
        where, why = row.get("where_in_the_files", ""), row.get("why", "")
        rows.append(f"| T{n} | {md_cell(request)} | {md_cell(why)} | {md_cell('Where: ' + where) if where else ''} | | | open |")
    if not rows:
        return triage
    empty = "| T1 | | | | | | |"
    if empty in triage:
        return triage.replace(empty, "\n".join(rows))
    return triage.rstrip("\n") + "\n" + "\n".join(rows) + "\n"


def licences_with(licences, assets):
    rows = [r for r in records(assets) if r.get("file_name")]
    if not rows:
        return licences
    table = ["", "## Assets from the team's workbook", "",
             "Copied from the Assets sheet as the team wrote it. Each row is the person's to confirm before publishing.", "",
             "| File | Made by | Licence | Link |", "| --- | --- | --- | --- |"]
    table += [f"| `{md_cell(r['file_name'])}` | {md_cell(r.get('made_by', ''))} | {md_cell(r.get('licence', ''))} | "
              f"{md_cell(r.get('link', ''))} |" for r in rows]
    return licences.rstrip("\n") + "\n" + "\n".join(table) + "\n"


def plan(files):
    """Everything the intake would write, as {relative path: bytes or str}, plus the report."""
    found, missing, notes = [], [], []
    names = LAYOUT["files"]
    out_text, out_bin = {}, {}

    design = find(files, names["design"])
    if design is None:
        raise IntakeError(f"The submission has no {names['design']}; the brief comes from it.")
    sections, doc_media = read_docx(design)
    found.append(names["design"])
    got = [h for h, _ in sections if h]
    for h in LAYOUT["headings"]:
        if h not in got:
            missing.append(f"{names['design']}: the heading \"{h}\"")
    for h, paras in sections:
        if h in LAYOUT["headings"] and not paras:
            missing.append(f"{names['design']}: text under \"{h}\"")
    for h in got:
        if h not in LAYOUT["headings"]:
            notes.append(f"{names['design']}: an extra heading \"{h}\" was kept in the brief.")

    pitch = find(files, names["pitch"])
    slides, slide_media = ([], {})
    if pitch is None:
        missing.append(names["pitch"])
    else:
        found.append(names["pitch"])
        slides, slide_media = read_pptx(pitch)
        if not 5 <= len(slides) <= 8:
            notes.append(f"{names['pitch']} has {len(slides)} slides; the assignment asks for 5 to 8.")

    sheets = {}
    data = find(files, names["data"])
    if data is None:
        missing.append(names["data"])
    else:
        found.append(names["data"])
        sheets = read_xlsx(data, skip=set(LAYOUT["private_sheets"]))
        for spec in LAYOUT["sheets"]:
            if spec["name"] not in sheets:
                missing.append(f"{names['data']}: the sheet \"{spec['name']}\"")
            elif spec["columns"] and sheets[spec["name"]] is not None:
                rows = sheets[spec["name"]]
                if not rows or rows[0][:len(spec["columns"])] != spec["columns"]:
                    notes.append(f"{names['data']}: the \"{spec['name']}\" headers differ from the template's.")
        filled = sum(len(sheets.get(n) or []) - 1 for n in DATA_SHEETS if sheets.get(n))
        if filled < 5:
            notes.append(f"{names['data']} has {max(filled, 0)} rows of game data; the assignment asks for at least 5.")

    game = {"_source": f"{names['data']}, copied by the intake; values are the team's, word for word"}
    for name, rows in sheets.items():
        if rows is None or name in SKIP_SHEETS:
            continue
        key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        game[key] = records(rows)
    out_text["data/game.json"] = json.dumps(game, indent=2, ensure_ascii=False) + "\n"

    for path, blob in files.items():
        if PurePosixPath(path).suffix.lower() in MEDIA:
            out_bin["data/assets/" + PurePosixPath(path).name] = blob
    for path, blob in doc_media.items():
        out_bin["data/assets/doc-" + PurePosixPath(path).name] = blob
    for path, blob in slide_media.items():
        out_bin["journal:img/reference/" + PurePosixPath(path).name] = blob

    return sections, slides, sheets, out_text, out_bin, found, missing, notes


def report(found, missing, notes, slides):
    lines = ["# Intake", "", "Written by `kits/office-intake/tools/intake/intake.py`. The agent reads this before the opening entry.", "",
             "## Found", ""] + [f"- {f}" for f in found] + ["", "## Missing", ""]
    lines += [f"- {m}" for m in missing] or ["- nothing"]
    lines += ["", "## To look at", ""] + ([f"- {n}" for n in notes] or ["- nothing"])
    lines += ["", "## The slides, word for word", ""]
    for i, texts in enumerate(slides, start=1):
        lines.append(f"{i}. " + " / ".join(texts))
    lines += ["", "## Not copied", "",
              "- The Team sheet, author metadata and comments. They hold students' names, which stay out of the project (GL-5).", ""]
    return "\n".join(lines)


def leaks(texts, words):
    """[(path, word)] for each private word found in text about to be written."""
    found = []
    for path, text in texts.items():
        low = text.lower()
        for w in words:
            if w.lower() in low:
                found.append((path, w))
    return found


def run(submission, project, journal=None):
    project = Path(project)
    journal = Path(journal) if journal else project.parent / f"{project.name}-journal"
    for need in ("BRIEF.md", "GLOSSARY.md", "TRIAGE.md", "LICENSES.md"):
        if not (project / need).exists():
            raise IntakeError(f"{project} has no {need}; copy Builder's template/ there first.")
    files = load_submission(submission)
    sections, slides, sheets, out_text, out_bin, found, missing, notes = plan(files)

    out_text["BRIEF.md"] = brief_with((project / "BRIEF.md").read_text(), sections)
    out_text["GLOSSARY.md"] = glossary_with((project / "GLOSSARY.md").read_text(), sheets.get("Words") or [], notes)
    out_text["TRIAGE.md"] = triage_with((project / "TRIAGE.md").read_text(), sheets.get("Changes") or [])
    out_text["LICENSES.md"] = licences_with((project / "LICENSES.md").read_text(), sheets.get("Assets") or [])
    out_text["INTAKE.md"] = report(found, missing, notes, slides)

    bad = leaks(out_text, private_words(files))
    if bad:
        where = "; ".join(f"{p} contains \"{w}\"" for p, w in bad)
        raise IntakeError(f"A student's name would be written, so nothing was written: {where}. "
                          "Remove the name from the team's files and run the intake again.")

    for rel, text in out_text.items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(text)
    for rel, blob in out_bin.items():
        dest = journal / rel.split(":", 1)[1] if rel.startswith("journal:") else project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    return found, missing, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("submission")
    ap.add_argument("project")
    ap.add_argument("--journal")
    args = ap.parse_args(argv)
    try:
        found, missing, notes = run(args.submission, args.project, args.journal)
    except IntakeError as e:
        print(f"intake stopped: {e}", file=sys.stderr)
        return 1
    print(f"intake: {len(found)} files read, {len(missing)} missing, {len(notes)} to look at; see INTAKE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
