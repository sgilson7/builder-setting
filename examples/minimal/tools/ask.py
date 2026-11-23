#!/usr/bin/env python3
"""Ask Builder a question and get the few cards that answer it, instead of reading its docs.

Builder's Markdown (the spec, docs/, prompts/, kit READMEs, CLAUDE.md, the
journal's ENTRIES.md, and any game digests) is cut into cards: one per
section, one per spec row (spec.D20), one per CLAUDE.md rule (claude.r14),
long sections split into parts. Its code is cut too: a card per Python or
JavaScript function and class, per Rust item and test (code.core.tests.boundary.
core_source_has_no_io_and_no_nondeterminism), and per script header, each
naming path:line so only those lines need opening. A card is cut from the files each time this
runs, so it is never stale. Its id is stable while the heading it comes from
is, and journal entries and STATE.md cite cards as card:<id>.

    python3 tools/ask.py "how do saves load an old version"    the top 3 cards
    python3 tools/ask.py -k 5 "..."                             the top 5
    python3 tools/ask.py --ids "..."                            ids and titles only
    python3 tools/ask.py --card spec.D20 claude.r14             those cards in full
    python3 tools/ask.py --code "..."  /  --docs "..."           only code cards / only document cards
    python3 tools/ask.py --start                                the start pack, for the opening entry
    python3 tools/ask.py --list                                 every card id and its size
    python3 tools/ask.py --check                                cards, start pack and spec rows in order
    python3 tools/ask.py --qa tests/builderqa.json              a question set: each answer in the top 5

Where Builder is: $BUILDER_HOME, else the repository this file sits in
(template/ or examples/minimal/), else ../builder/ beside this project. Without
it, the cards come from this project's own copies (CLAUDE.md, BUILDER-SPEC.md,
ENTRIES.md, STATE.md). Game digests come from $BUILDER_REFS or ../refs/.
Standard library only; keyword ranking (BM25), no model.
"""

import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 1800          # characters per card part, about 450 tokens
START_BUDGET = 3500   # tokens the start pack may take
CITE = re.compile(r"card:([a-z0-9][a-z0-9._~-]*[a-z0-9_])")

# The start pack: what an opening entry needs that CLAUDE.md does not already say.
# The agent reads CLAUDE.md in full anyway, so its rules are not repeated here.
START = [
    "docs.context.how-to-read-builder",
    "docs.procedure", "docs.procedure.p2", "docs.procedure.p3",
    "docs.journal.the-opening-entry",
    "entries.kinds", "entries.kinds.p2", "entries.kinds.p3",
    "kits.readme.the-kits",
]

STOP = set("""a an the and or of to in on for with by is are be it this that as at from how what when where which
who why do does i you we my your our can should into not no its their there them then than so if else
about use using used get put make makes made one each all any exist exists""".split())


def stem(w):
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + rep
    return w


# Builder's own vocabulary: a question in one word finds a card written in the other.
SAME = {"crate": "dependency", "dependencie": "dependency", "depend": "dependency", "verifi": "check", "verify": "check",
        "test": "check", "multiplayer": "online", "netcode": "online", "network": "online", "save": "saves",
        "persist": "saves", "deploy": "publish", "subagent": "agent", "parallel": "agent", "rule": "rule",
        "picture": "art", "image": "art", "phone": "mobile", "touch": "mobile"}


def words(text):
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP or len(w) < 2:
            continue
        w = stem(w)
        out.append(w)
        if w in SAME and SAME[w] != w:
            out.append(SAME[w])
    return out


CODE_WORDS = {"test", "function", "fn", "script", "code", "py", "rs", "js", "struct", "const", "scanner", "def", "implement"}


def slug(text):
    s = re.sub(r"`([^`]*)`", r"\1", text.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48].strip("-") or "section"


def builder_home():
    env = os.environ.get("BUILDER_HOME")
    if env and (Path(env) / "BUILDER-SPEC.md").exists():
        return Path(env).resolve()
    for cand in (ROOT.parent, ROOT.parent.parent, ROOT.parent / "builder"):
        if (cand / "BUILDER-SPEC.md").exists() and (cand / "template").is_dir() and (cand / "docs").is_dir():
            return cand.resolve()
    return None


def refs_home():
    env = os.environ.get("BUILDER_REFS")
    if env and Path(env).is_dir():
        return Path(env).resolve()
    cand = ROOT.parent / "refs"
    return cand.resolve() if cand.is_dir() else None


def sources():
    """(key, path) for every file the cards come from."""
    out = []
    home = builder_home()
    if home:
        out += [("readme", home / "README.md"), ("spec", home / "BUILDER-SPEC.md")]
        out += [(f"docs.{p.stem}", p) for p in sorted((home / "docs").glob("*.md"))]
        out += [(f"prompts.{p.stem}", p) for p in sorted((home / "prompts").glob("*.md"))]
        out += [("kits.readme", home / "kits" / "README.md")]
        out += [(f"kits.{p.parent.name}", p) for p in sorted((home / "kits").glob("*/README.md"))]
        t = home / "template"
    else:
        t = ROOT
        out += [("spec", t / "BUILDER-SPEC.md")]
    out += [("claude", t / "CLAUDE.md"), ("brief", t / "BRIEF.md"), ("entries", t / "tools" / "journal" / "ENTRIES.md"),
            ("state", t / "STATE.md"), ("glossary", t / "GLOSSARY.md"), ("tone", t / "TONE.md")]
    out += [(f"skill.{p.parent.name}", p) for p in sorted((t / ".claude" / "skills").glob("*/SKILL.md"))]
    refs = refs_home()
    if refs:
        out += [(f"ref.{slug(p.stem)}", p) for p in sorted(refs.glob("*.md"))]
    return [(k, p) for k, p in out if p.exists()]


def split_long(text):
    """Paragraph groups of at most LIMIT characters; a longer paragraph is cut by lines."""
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        pieces = [para] if len(para) <= LIMIT else _lines(para)
        for piece in pieces:
            if cur and len(cur) + len(piece) + 2 > LIMIT:
                parts.append(cur)
                cur = piece
            else:
                cur = f"{cur}\n\n{piece}" if cur else piece
    if cur.strip():
        parts.append(cur)
    return parts or [""]


def _lines(para):
    out, cur = [], ""
    for line in para.splitlines():
        if cur and len(cur) + len(line) + 1 > LIMIT:
            out.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    return out + ([cur] if cur else [])


ROW = re.compile(r"^\|\s*([RD][1-9]\d*)\s*\|")
RULE = re.compile(r"^([1-9]\d*)\.\s+")


def cut(key, path):
    """The cards of one file."""
    rel = path.as_posix()
    lines = path.read_text().splitlines()
    sections, trail, cur = [], [], {"level": 0, "title": "", "body": []}
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            sections.append(cur)
            level, title = len(m.group(1)), m.group(2).strip()
            trail = [t for t in trail if t[0] < level] + [(level, title)]
            cur = {"level": level, "title": title, "trail": [t for _, t in trail], "body": []}
        else:
            cur["body"].append(line)
    sections.append(cur)

    cards, used = [], set()

    def add(cid, title, text, where):
        base, n = cid, 2
        while cid in used:
            cid = f"{base}-{n}"
            n += 1
        used.add(cid)
        cards.append({"id": cid, "title": title, "text": text.strip(), "file": where})

    for sec in sections:
        body = sec["body"]
        if not sec["title"] and not "".join(body).strip():
            continue
        trail = sec.get("trail", [])
        title = " › ".join(trail) or path.name
        cid = key if sec["level"] <= 1 else f"{key}.{slug(sec['title'])}"
        if sec["level"] > 1 and f"{key}.{slug(sec['title'])}" in used and len(trail) > 1:
            cid = f"{key}.{slug(trail[-2])}-{slug(sec['title'])}"
        rest = []
        for line in body:
            row = ROW.match(line) if key == "spec" else None
            rule = RULE.match(line) if key == "claude" else None
            if row:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                add(f"spec.{row.group(1)}", f"{row.group(1)}: {cells[1][:70]}", " | ".join(cells), rel)
            elif rule:
                add(f"claude.r{rule.group(1)}", f"Rule {rule.group(1)}: {line[rule.end():][:70]}", line, rel)
            else:
                rest.append(line)
        text = "\n".join(rest).strip()
        if not text and sec["level"] > 1:
            text = "(this section's rows and rules are cards of their own)"
        parts = split_long(text)
        for i, part in enumerate(parts):
            add(cid if i == 0 else f"{cid}.p{i + 1}", title + ("" if i == 0 else f" (part {i + 1})"), part, rel)
    return cards


CODE_SKIP = {"target", "dist", ".venv", "node_modules", "vendor", "__pycache__", "mutants.out", ".git", "notes"}
CODE_EXT = {".py", ".rs", ".sh", ".js"}


def code_sources():
    """(key, path, shown path) for every code file the cards come from."""
    home = builder_home()
    roots = [(home / "template", "", home)] if home else [(ROOT, "", ROOT)]
    if home:
        roots += [(home / "kits", "kits.", home), (home / "scripts", "repo.scripts.", home)]
    out = []
    for base, prefix, rel_to in roots:
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*"), key=lambda p: (str(p.parent), p.suffix != ".py", p.name)):
            if p.suffix not in CODE_EXT or not p.is_file() or CODE_SKIP & set(p.relative_to(base).parts):
                continue
            rel = p.relative_to(base)
            parts = [x for x in rel.with_suffix("").parts if x not in ("crates", "src")]
            key = "code." + prefix + ".".join(slug(x).replace("-", "_") for x in parts)
            if any(key == k for k, _, _ in out):
                key += "_" + p.suffix.lstrip(".")
            out.append((key, p, p.relative_to(rel_to).as_posix()))
    return out


ITEM = {
    ".py": re.compile(r"^(\s*)(?:async\s+)?(def|class)\s+([A-Za-z_]\w*)"),
    ".rs": re.compile(r"^(\s*)(?:pub(?:\([^)]*\))?\s+)?(fn|struct|enum|trait|const|static|mod|type)\s+([A-Za-z_]\w*)"),
    ".js": re.compile(r"^(\s*)(?:export\s+)?(?:async\s+)?(function|class)\s+([A-Za-z_$][\w$]*)|^(\s*)(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
    ".sh": re.compile(r"^(\s*)()([A-Za-z_][\w-]*)\s*\(\)\s*\{"),
}
COMMENT = {".py": "#", ".rs": "//", ".js": "//", ".sh": "#"}


def cut_code(key, path, shown):
    lines = path.read_text(errors="replace").splitlines()
    ext = {".ts": ".js", ".tsx": ".js", ".jsx": ".js", ".mjs": ".js"}.get(path.suffix, path.suffix)
    cards, used = [], set()

    def add(cid, title, text, line):
        base, n = cid, 2
        while cid in used:
            cid = f"{base}-{n}"
            n += 1
        used.add(cid)
        if len(text) > LIMIT:
            cut_at = text.rfind("\n", 0, LIMIT)
            more = text[cut_at:].count("\n")
            text = text[:cut_at] + f"\n… ({more} more lines: open {shown} from line {line})"
        cards.append({"id": cid, "title": title, "text": text.strip(), "file": f"{shown}:{line}"})

    # the file's own header: a docstring, //! or # comments, and a script's step names
    head = []
    if ext == ".py":
        m = re.match(r'(?:#![^\n]*\n)?\s*("""|\'\'\')(.*?)\1', "\n".join(lines), re.S)
        if m:
            head = m.group(2).strip().splitlines()
    else:
        mark = "//!" if ext == ".rs" else COMMENT[ext]
        for line in lines[1 if lines and lines[0].startswith("#!") else 0:]:
            if line.strip().startswith(mark) or (ext == ".rs" and line.strip().startswith("//")):
                head.append(line.strip().lstrip("/!#").strip())
            elif line.strip():
                break
    if ext == ".sh":
        head += [m.group(1) for m in (re.search(r'step\s+"([^"]+)"', l) for l in lines) if m]
    if head or ext in (".sh",):
        add(key, f"{shown} (the file)", "\n".join(head) or "(no header comment)", 1)

    starts = []
    rx = ITEM[ext]
    for i, line in enumerate(lines):
        m = rx.match(line)
        if not m:
            continue
        if ext == ".js" and m.group(5):
            indent, kind, name = m.group(4), "function", m.group(5)
        else:
            indent, kind, name = m.group(1), m.group(2) or "function", m.group(3)
        if ext == ".rs" and kind == "mod" and line.rstrip().endswith(";"):
            continue
        starts.append((i, len(indent or ""), kind, name))
    for n, (i, indent, kind, name) in enumerate(starts):
        end = len(lines)
        for j, ind, _, _ in starts[n + 1:]:
            if ind <= indent:
                end = j
                break
        # doc comments and attributes just above the item
        top = i
        while top > 0 and re.match(r"\s*(///|#\[|#\s|@)", lines[top - 1]) and not lines[top - 1].strip().startswith("#!"):
            top -= 1
        test = any("#[test]" in l for l in lines[top:i])
        body = "\n".join(lines[top:end]).rstrip()
        label = "test" if test else kind
        add(f"{key}.{name}", f"{shown}: {label} {name}", body, top + 1)
    return cards


def load():
    cards, keys = [], set()
    for key, path in sources():
        keys.add(key)
        for c in cut(key, path):
            c["path"] = path
            cards.append(c)
    for key, path, shown in code_sources():
        keys.add(key)
        for c in cut_code(key, path, shown):
            c["path"] = path
            cards.append(c)
    return cards, keys


class Index:
    def __init__(self, cards):
        self.cards = cards
        self.docs = []
        for c in cards:
            head = words(c["title"] + " " + c["id"].replace(".", " ").replace("-", " "))
            self.docs.append(Counter(head * 3 + words(c["text"])))
        self.avg = sum(sum(d.values()) for d in self.docs) / max(1, len(self.docs))
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def search(self, query, k=3):
        q = words(query)
        code_q = bool(CODE_WORDS & set(re.findall(r"[a-z]+", query.lower())))
        scored = []
        for c, d in zip(self.cards, self.docs):
            size = sum(d.values())
            s = 0.0
            for w in q:
                f = d.get(w, 0)
                if f:
                    s += self.idf[w] * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * size / self.avg))
            if s > 0:
                if c["id"].startswith("code.") and not code_q:
                    s *= 0.8
                scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:k]]


def tokens(text):
    return max(1, len(text) // 4)


def show(c):
    return f"── card:{c['id']}  {c['title']}  ({c['file']}, ~{tokens(c['text'])} tokens)\n{c['text']}\n"


def known_ids():
    """(ids, keys) for checks that verify card citations; a citation whose key was not loaded is not judged."""
    cards, keys = load()
    return {c["id"] for c in cards}, keys


def unknown_citations(text):
    ids, keys = known_ids()
    bad = []
    for cid in sorted(set(CITE.findall(text))):
        key_known = any(cid == k or cid.startswith(k + ".") for k in keys)
        if key_known and cid not in ids:
            bad.append(cid)
    return bad


def check(cards):
    problems = []
    by = {c["id"]: c for c in cards}
    seen = set()
    for c in cards:
        if c["id"] in seen:
            problems.append(f"two cards share the id {c['id']}")
        seen.add(c["id"])
    for c in cards:
        if not c["id"].startswith("code.") and len(c["text"]) > LIMIT * 1.6:
            problems.append(f"card {c['id']} is {len(c['text'])} characters; the limit is {LIMIT}")
    missing = [i for i in START if i not in by]
    problems += [f"the start pack names card {i}, which does not exist" for i in missing]
    size = sum(tokens(by[i]["text"]) for i in START if i in by)
    if size > START_BUDGET:
        problems.append(f"the start pack is ~{size} tokens; the budget is {START_BUDGET}")
    spec = next((c["path"] for c in cards if c["id"].startswith("spec.")), None)
    if spec:
        rows = {m.group(1) for line in spec.read_text().splitlines() for m in [ROW.match(line)] if m}
        problems += [f"spec row {r} has no card" for r in sorted(rows) if f"spec.{r}" not in by]
    claude = next((c["path"] for c in cards if c["id"].startswith("claude.")), None)
    if claude:
        rules = {m.group(1) for line in claude.read_text().splitlines() for m in [RULE.match(line)] if m}
        problems += [f"CLAUDE.md rule {r} has no card" for r in sorted(rules, key=int) if f"claude.r{r}" not in by]
    return problems, size


def qa(index, path, k=5):
    items = json.loads(Path(path).read_text())
    ids = {c["id"] for c in index.cards}
    misses, unknown, at = [], [], Counter()
    for it in items:
        want = set(it["cards"])
        unknown += [w for w in want if w not in ids]
        got = [c["id"] for c in index.search(it["q"], k)]
        hit = next((i for i, g in enumerate(got) if g in want), None)
        if hit is None:
            misses.append((it["q"], sorted(want), got[:3]))
        else:
            for n in (1, 3, 5):
                if hit < n:
                    at[n] += 1
    return items, misses, sorted(set(unknown)), at


def main(argv):
    cards, _ = load()
    if not cards:
        print("no Builder files found: set BUILDER_HOME to the Builder folder")
        return 1
    index = Index(cards)
    by = {c["id"]: c for c in cards}
    k = 3
    if "-k" in argv:
        i = argv.index("-k")
        k = int(argv[i + 1])
        del argv[i:i + 2]
    if "--list" in argv:
        for c in cards:
            print(f"{c['id']:<52} ~{tokens(c['text']):>4}  {c['title'][:70]}")
        print(f"{len(cards)} cards, ~{sum(tokens(c['text']) for c in cards)} tokens in all")
        return 0
    if "--check" in argv:
        problems, size = check(cards)
        for p in problems:
            print(f"FAIL {p}")
        if not problems:
            print(f"cards: {len(cards)} cards from {len({c['file'] for c in cards})} files, "
                  f"every spec row and CLAUDE.md rule on a card, start pack ~{size} tokens (budget {START_BUDGET})")
        return 1 if problems else 0
    if "--qa" in argv:
        items, misses, unknown, at = qa(index, argv[argv.index("--qa") + 1])
        for u in unknown:
            print(f"FAIL the question set names card {u}, which does not exist")
        for q, want, got in misses:
            print(f"FAIL {q!r}: none of {', '.join(want)} in the top 5 (got {', '.join(got)})")
        n = len(items)
        print(f"BuilderQA: {n - len(misses)}/{n} answered in the top 5; "
              f"top 1 {at[1]}/{n}, top 3 {at[3]}/{n}")
        return 1 if misses or unknown else 0
    if "--start" in argv:
        print("Start pack: the Builder cards an opening entry needs. Cite them as card:<id>.\n"
              "CLAUDE.md's rules are not repeated here; read CLAUDE.md in full.\n"
              "Ask for anything else with: python3 tools/ask.py \"your question\"\n")
        for i in START:
            if i in by:
                print(show(by[i]))
        return 0
    if "--card" in argv:
        bad = 0
        for cid in argv[argv.index("--card") + 1:]:
            cid = cid.removeprefix("card:")
            if cid in by:
                print(show(by[cid]))
            else:
                print(f"no card {cid}; try: python3 tools/ask.py --ids \"{cid.replace('.', ' ')}\"")
                bad = 1
        return bad
    if "--code" in argv or "--docs" in argv:
        want_code = "--code" in argv
        index = Index([c for c in cards if c["id"].startswith("code.") == want_code])
    ids_only = "--ids" in argv
    query = " ".join(a for a in argv if not a.startswith("--"))
    if not query.strip():
        print(__doc__)
        return 2
    found = index.search(query, k)
    if not found:
        print("no card matches; try other words, or --list")
        return 1
    for c in found:
        print(f"card:{c['id']:<48} ~{tokens(c['text'])} tokens  {c['title']}" if ids_only else show(c))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
