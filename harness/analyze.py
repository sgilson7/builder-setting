#!/usr/bin/env python3
"""Analyse a Builder trial: how far token use was held down, and where Builder slipped.

Reads every Claude Code transcript for the trial folder (and its subagents),
then reports:

1. Token use, set beside the baseline of six projects built before the cards
   (harness/baseline.json): context at the first plan, peak, mean,
   compactions, total re-read, start-up share, share above 200k.
2. How Builder was read: ask.py calls (start pack, queries, cards), and every
   read of a file under builder/ — whether a card had pointed to it first, and
   whether it was a whole file or a range. Reads of transcripts.
3. Memory: STATE.md rewrites set against compactions, whether the hook put
   STATE.md back, and Builder files re-read after a compaction.
4. Output: long tool output not run through quiet.sh, images read.
5. Process: the order of BRIEF, the opening entry, PLAN.md and the first code;
   chips; checks run; subagents; deploys and whether the brief granted them.
6. End state: the project's own checks, run now (--full adds ./scripts/check.sh).

Each slip carries the call number, the evidence, and the tokens it carried
(its size times the calls it stayed in context before a compaction).

    python3 harness/analyze.py ~/Documents/BuilderTrials/NAME [--full] [--no-checks]
    python3 harness/analyze.py --session FILE.jsonl     a single old session, no checks
    python3 harness/analyze.py --baseline FILE.jsonl... write harness/baseline.json

Writes NAME/harness/report.md and NAME/harness/metrics.json, and adds a row
to the trials index (~/Documents/BuilderTrials/index.md).
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "template" / "tools"))
import tokens  # noqa: E402

BIG = 8000          # tokens: a tool result this large is a long output
REREAD_WINDOW = 40  # calls after a compaction in which a Builder re-read counts as a slip
STATE_WINDOW = 60   # calls before a compaction in which a STATE.md rewrite counts as in time
CHECK_CMD = re.compile(r"(scripts/check\.sh|scripts/quick-check\.sh|cargo test|cargo clippy|break_tests\.py|tests/browser/check\.py|scripts/build\.sh)")
DEPLOY_CMD = re.compile(r"(?:^|&&|;|\|\||\n)\s*(gh repo create|git push|\./scripts/publish\.sh|gh api [^\n]*pages)")
READ_CMD = re.compile(r"(?:^|[;&|(]\s*)(cat|head|tail|sed -n|less|bat)\b[^;&|]*")


def tok(chars):
    return max(0, chars // 4)


def transcripts_for(trial):
    base = Path.home() / ".claude" / "projects"
    stem = re.sub(r"[^A-Za-z0-9]", "-", str(Path(trial).resolve()))
    main, subs = [], []
    for d in sorted(base.glob(stem + "*")):
        main += sorted(d.glob("*.jsonl"))
        subs += sorted(d.glob("*/subagents/*.jsonl"))
    return main, subs


def events(path):
    """Per model call: usage, tool uses, and the tool results that answered them."""
    calls, index, results, notes = [], {}, {}, []
    for line in open(path, errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = d.get("type")
        if t == "assistant":
            m = d.get("message") or {}
            mid = m.get("id") or id(m)
            uses = [c for c in (m.get("content") or []) if isinstance(c, dict) and c.get("type") == "tool_use"]
            if mid in index:
                calls[index[mid]]["uses"] += uses
            else:
                index[mid] = len(calls)
                calls.append({"usage": m.get("usage") or {}, "uses": uses})
        elif t == "user":
            content = (d.get("message") or {}).get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        r = c.get("content")
                        text, imgs = "", 0
                        if isinstance(r, list):
                            for x in r:
                                if isinstance(x, dict) and x.get("type") == "image":
                                    imgs += 1
                                elif isinstance(x, dict):
                                    text += x.get("text", "")
                        else:
                            text = str(r or "")
                        results[c.get("tool_use_id")] = (text, imgs)
            elif isinstance(content, str) and "context was just compacted" in content:
                notes.append(("hook", len(calls)))
        elif t == "system" or d.get("isCompactSummary"):
            if "compact" in json.dumps(d)[:2000].lower():
                notes.append(("compact", len(calls)))
        if "The context was just compacted" in line:
            notes.append(("hook", len(calls)))
    return calls, results, notes


def find_project(trial):
    trial = Path(trial)
    skip = {"builder", "refs", "harness", ".claude"}
    cands = [p for p in trial.iterdir() if p.is_dir() and p.name not in skip and not p.name.endswith("-journal")
             and not p.name.startswith(".")]
    with_brief = [p for p in cands if (p / "BRIEF.md").exists()]
    return (with_brief or cands or [None])[0]


def rel_builder(path, builder_roots):
    for r in builder_roots:
        if path.startswith(r + "/"):
            return path[len(r) + 1:]
    if "/builder/" in path:          # Builder cloned into another project's folder
        return path.split("/builder/", 1)[1]
    return None


def analyse(paths, trial=None, project=None):
    builder_roots = []
    if trial:
        builder_roots.append(str(Path(trial).resolve() / "builder"))
    builder_roots += [str(Path.home() / "Documents" / "Builder" / "builder-setting")]
    calls, results, notes = [], {}, []
    for p in paths:
        c, r, n = events(p)
        offset = len(calls)
        calls += c
        results.update(r)
        notes += [(k, i + offset) for k, i in n]
    ctx = [tokens.context(c["usage"]) for c in calls]
    drops = [i for i in range(1, len(ctx)) if ctx[i] < 0.5 * ctx[i - 1] and ctx[i - 1] > 60_000]

    def carried(i, size):
        nxt = next((d for d in drops if d > i), len(ctx))
        return size * max(0, nxt - i)

    slips, f = [], {}
    asks, pointed_paths = [], set()
    builder_reads, transcript_reads, images, long_outputs = [], [], [], []
    state_writes, journal_writes, plan_writes, code_writes, brief_writes = [], [], [], [], []
    checks_raw, checks_quiet, subagents, deploys, chips, digests, tokens_runs = [], [], [], [], [], [], []
    for i, c in enumerate(calls):
        for u in c["uses"]:
            name, inp = u.get("name"), u.get("input") or {}
            text, imgs = results.get(u.get("id"), ("", 0))
            size = tok(len(text))
            cmd = inp.get("command", "") if name == "Bash" else ""
            fp = str(inp.get("file_path", ""))
            if imgs:
                images.append((i, fp or cmd[:60], imgs))
            if "tools/ask.py" in cmd:
                mode = "start" if "--start" in cmd else "card" if "--card" in cmd else "query"
                asks.append((i, mode, cmd[:120], size))
                for m in re.finditer(r"\(([\w./-]+\.(?:md|py|rs|sh|js|json|toml))(?::\d+)?,", text):
                    pointed_paths.add(m.group(1))
                for m in re.finditer(r"open ([\w./-]+) from line", text):
                    pointed_paths.add(m.group(1))
            if "tools/digest.py" in cmd:
                digests.append(i)
            if "tools/tokens.py" in cmd:
                tokens_runs.append(i)
            if "decisions.py" in cmd:
                chips.append(i)
            if name in ("Agent", "Task"):
                subagents.append((i, (inp.get("description") or "")[:60]))
            head = cmd.split("<<")[0]
            if head and DEPLOY_CMD.search(head):
                deploys.append((i, cmd[:100]))
            if cmd and CHECK_CMD.search(cmd):
                (checks_quiet if "quiet.sh" in cmd else checks_raw).append((i, cmd[:90], size))
            # reads
            targets = []
            if name == "Read" and fp:
                partial = bool(inp.get("offset") or inp.get("limit"))
                targets.append((fp, partial))
            elif cmd and READ_CMD.search(cmd):
                for m in re.finditer(r"([~\w./-]*/[\w./-]+\.(?:md|py|rs|sh|js|json|toml|html))", cmd):
                    targets.append((m.group(1), "sed -n" in cmd or "head" in cmd or "tail" in cmd))
            elif name == "Grep" and inp.get("path"):
                targets.append((str(inp.get("path")), True))
            for path, partial in targets:
                full = str(Path(path).expanduser())
                if ".claude/projects" in full and full.endswith(".jsonl"):
                    transcript_reads.append((i, full, size))
                rb = rel_builder(full, builder_roots)
                if rb is not None:
                    key = rb.removeprefix("template/")
                    was_pointed = any(rb.endswith(p) or p.endswith(key) for p in pointed_paths)
                    builder_reads.append({"call": i, "path": rb, "tokens": size // max(1, len(targets)),
                                          "partial": partial, "pointed": was_pointed, "carried": carried(i, size)})
            if size >= BIG and not imgs:
                long_outputs.append((i, name, (cmd or fp)[:90], size, carried(i, size)))
            # writes
            if name in ("Write", "Edit", "MultiEdit") and fp:
                if fp.endswith("/STATE.md"):
                    state_writes.append(i)
                elif "-journal/" in fp:
                    journal_writes.append(i)
                elif fp.endswith("/PLAN.md"):
                    plan_writes.append(i)
                elif fp.endswith("/BRIEF.md"):
                    brief_writes.append(i)
                elif re.search(r"/(crates|web)/", fp):
                    code_writes.append(i)

    first_plan = min([x for x in (journal_writes[:1] + plan_writes[:1]) if x is not None], default=None)
    reread = [c["usage"].get("cache_read_input_tokens") or 0 for c in calls]
    climb = (ctx[first_plan] - ctx[0]) if first_plan is not None else None
    first_drop = drops[0] if drops else len(ctx)
    startup = (sum(reread[:first_plan + 1]) + climb * max(0, first_drop - first_plan - 1)) if first_plan is not None else None
    f["tokens"] = {
        "calls": len(ctx), "base": ctx[0] if ctx else 0,
        "plan_at_call": first_plan + 1 if first_plan is not None else None,
        "at_plan": ctx[first_plan] if first_plan is not None else None, "climb": climb,
        "peak": max(ctx) if ctx else 0, "mean": sum(ctx) // len(ctx) if ctx else 0,
        "compactions": len(drops), "compaction_calls": [d + 1 for d in drops],
        "reread": sum(reread), "startup_reread": startup,
        "startup_share": (startup / sum(reread)) if startup and sum(reread) else None,
        "above_200k_share": (sum(max(0, c - 200_000) for c in ctx) / (sum(ctx) or 1)),
    }

    # ---- slips ----
    start_reads = [r for r in builder_reads if first_plan is None or r["call"] <= first_plan]
    if not asks:
        slips.append(("high", "ask.py was never used: Builder was read from its files (rule 19)", None, sum(r["carried"] for r in builder_reads)))
    elif not any(a[1] == "start" for a in asks):
        slips.append(("medium", "the start pack (ask.py --start) was never read", asks[0][0] + 1, 0))
    for r in builder_reads:
        if not r["pointed"] and not r["partial"] and r["tokens"] > 400:
            sev = "high" if r["tokens"] > 3000 else "medium"
            slips.append((sev, f"read builder/{r['path']} whole (~{r['tokens']} tokens) with no card pointing to it (rule 19)",
                          r["call"] + 1, r["carried"]))
        elif r["pointed"] and not r["partial"] and r["tokens"] > 3000:
            slips.append(("low", f"read builder/{r['path']} whole (~{r['tokens']} tokens) where a card named the lines", r["call"] + 1, r["carried"]))
    for i, p, size in transcript_reads:
        slips.append(("high", f"read a transcript ({Path(p).name}, ~{size} tokens) instead of a digest (rule 20)", i + 1, carried(i, size)))
    unready = [d for d in drops if not [w for w in state_writes if d - STATE_WINDOW <= w < d]]
    if unready:
        shown = ", ".join(str(d + 1) for d in unready[:8]) + (" …" if len(unready) > 8 else "")
        slips.append(("medium", f"{len(unready)} of {len(drops)} compactions had no STATE.md rewrite in the {STATE_WINDOW} calls before them (calls {shown}; rule 21)",
                      unready[0] + 1, 0))
    for d in drops:
        rereads = [r for r in builder_reads if d <= r["call"] < d + REREAD_WINDOW and not r["pointed"]]
        for r in rereads:
            slips.append(("medium", f"re-read builder/{r['path']} within {REREAD_WINDOW} calls after a compaction (rule 21)", r["call"] + 1, r["carried"]))
    if ctx and max(ctx) > 200_000 and not state_writes:
        slips.append(("high", "context passed 200k and STATE.md was never rewritten (rule 21)", None, 0))
    for i, nm, what, size, car in long_outputs:
        if nm == "Bash" and "quiet.sh" not in what:
            slips.append(("medium" if size < 20_000 else "high", f"long output (~{size} tokens) from `{what}` not run through quiet.sh (rule 22)", i + 1, car))
        elif nm != "Bash":
            slips.append(("low", f"long result (~{size} tokens) from {nm} {('`' + what + '`') if what else ''}", i + 1, car))
    for i, cmd, size in checks_raw:
        if size > 2000:
            slips.append(("low", f"check run without quiet.sh (~{size} tokens of output): `{cmd}`", i + 1, carried(i, size)))
    if subagents:
        slips.append(("info", f"{len(subagents)} subagent(s) spawned; allowed only if BRIEF.md's Autonomy names them (rule 17)", subagents[0][0] + 1, 0))
    if plan_writes and journal_writes and plan_writes[0] < journal_writes[0]:
        slips.append(("high", "PLAN.md was written before the journal's opening entry (rule 14)", plan_writes[0] + 1, 0))
    if code_writes and not plan_writes:
        slips.append(("high", "code was written in this session with no PLAN.md written first (stage order; fine if PLAN.md already existed)", code_writes[0] + 1, 0))
    elif code_writes and plan_writes and code_writes[0] < plan_writes[0]:
        slips.append(("high", "code was written before PLAN.md (stage order)", code_writes[0] + 1, 0))
    if not chips and journal_writes:
        slips.append(("medium", "decisions.py never ran: no questions were drawn as answer chips (rule 16)", None, 0))
    if not tokens_runs:
        slips.append(("low", "tools/tokens.py never ran (rule 23; the harness measured instead)", None, 0))
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    slips.sort(key=lambda s: (order[s[0]], -s[3]))
    f["slips"] = [{"severity": s, "what": w, "call": c, "carried_tokens": car} for s, w, c, car in slips]
    f["reading"] = {
        "ask_calls": len(asks), "ask_start": sum(1 for a in asks if a[1] == "start"),
        "ask_queries": sum(1 for a in asks if a[1] == "query"), "ask_cards": sum(1 for a in asks if a[1] == "card"),
        "ask_tokens": sum(a[3] for a in asks),
        "builder_reads": len(builder_reads), "builder_reads_cold_whole": sum(1 for r in builder_reads if not r["pointed"] and not r["partial"]),
        "builder_read_tokens": sum(r["tokens"] for r in builder_reads),
        "builder_read_tokens_at_startup": sum(r["tokens"] for r in start_reads),
        "builder_read_carried": sum(r["carried"] for r in builder_reads),
        "transcript_reads": len(transcript_reads), "digests_made": len(digests),
        "reads": builder_reads,
    }
    f["memory"] = {"state_writes": [w + 1 for w in state_writes], "hook_fired": [n for k, n in notes if k == "hook"]}
    f["output"] = {"long_outputs": len(long_outputs), "long_output_tokens": sum(x[3] for x in long_outputs),
                   "checks_raw": len(checks_raw), "checks_quiet": len(checks_quiet), "images": sum(x[2] for x in images)}
    f["process"] = {
        "brief_first_write": brief_writes[0] + 1 if brief_writes else None,
        "journal_first_write": journal_writes[0] + 1 if journal_writes else None,
        "plan_first_write": plan_writes[0] + 1 if plan_writes else None,
        "code_first_write": code_writes[0] + 1 if code_writes else None,
        "chip_runs": len(chips), "subagents": len(subagents), "deploys": [d[1] for d in deploys],
        "check_runs": len(checks_raw) + len(checks_quiet), "tokens_runs": len(tokens_runs),
    }
    f["ctx"] = ctx
    return f


def run_checks(project, full):
    out = {}
    if not project:
        return out
    cmds = {"journal": ["python3", "scripts/journal_check.py"], "context": ["python3", "scripts/context_check.py"],
            "notebook": ["python3", "scripts/notebook_check.py"], "tags": ["python3", "scripts/quick_check.py", "--guard"]}
    if full:
        cmds["check.sh"] = ["./scripts/check.sh"]
    for k, cmd in cmds.items():
        if not (project / cmd[-1 if k != "tags" else 1]).exists() and k != "check.sh":
            out[k] = {"ok": None, "text": "not present in this project"}
            continue
        try:
            r = subprocess.run(cmd, cwd=project, capture_output=True, text=True, timeout=1800)
            lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
            fails = [l for l in lines if "FAIL" in l][:8]
            out[k] = {"ok": r.returncode == 0, "text": "\n".join(fails or lines[-3:])}
        except Exception as e:  # noqa: BLE001
            out[k] = {"ok": False, "text": str(e)}
    # the deploy grant, read from the brief
    brief = (project / "BRIEF.md").read_text() if (project / "BRIEF.md").exists() else ""
    m = re.search(r"Deploys:\s*(.+)", brief)
    out["deploy_grant"] = m.group(1).strip() if m else None
    return out


def k(n):
    if n is None:
        return "–"
    if isinstance(n, float):
        return f"{n:.0%}"
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{round(n / 1000)}k"


def spark(ctx, width=64):
    if not ctx:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    step = max(1, len(ctx) // width)
    pts = [max(ctx[i:i + step]) for i in range(0, len(ctx), step)]
    return "".join(bars[min(7, int(p / 1_000_000 * 8))] for p in pts)


def report(name, meta, f, checks, baseline):
    t = f["tokens"]
    b = baseline.get("summary", {})
    L = [f"# Trial: {name}", "",
         f"Builder `{meta.get('builder_branch')}` @ `{meta.get('builder_commit')}` · Claude Code {meta.get('claude_version')} · "
         f"compact window {meta.get('compact_window') or 'default'} · analysed {datetime.now():%Y-%m-%d %H:%M}", "",
         "## Token use", "",
         "| | This trial | Baseline (6 projects before the cards, median) |", "| --- | --- | --- |"]
    rows = [("Model calls", t["calls"], b.get("calls")), ("Context at first plan or journal write", t["at_plan"], b.get("at_plan")),
            ("Start-up climb", t["climb"], b.get("climb")), ("Peak context", t["peak"], b.get("peak")),
            ("Mean context", t["mean"], b.get("mean")), ("Compactions", t["compactions"], b.get("compactions")),
            ("Total re-read", t["reread"], b.get("reread")), ("Start-up share of re-read", t["startup_share"], b.get("startup_share")),
            ("Share of context above 200k", t["above_200k_share"], b.get("above_200k_share"))]
    for label, v, bv in rows:
        fmt = (lambda x: str(x) if isinstance(x, int) and x < 1000 else k(x))
        L.append(f"| {label} | {fmt(v)} | {fmt(bv)} |")
    L += ["", f"Context per call (each bar up to 1M): `{spark(f['ctx'])}`",
          f"First plan or journal write at call {t['plan_at_call']}; compactions at calls {t['compaction_calls'] or 'none'}.", ""]
    r = f["reading"]
    L += ["## How Builder was read", "",
          f"- ask.py: {r['ask_calls']} calls ({r['ask_start']} start pack, {r['ask_queries']} questions, {r['ask_cards']} cards), ~{r['ask_tokens']} tokens returned.",
          f"- Files under builder/: {r['builder_reads']} reads, ~{r['builder_read_tokens']} tokens ({r['builder_read_tokens_at_startup']} before the first plan); "
          f"{r['builder_reads_cold_whole']} were whole files with no card pointing to them. Carried in context: ~{k(r['builder_read_carried'])} re-read tokens.",
          f"- Transcripts read: {r['transcript_reads']}; digests made: {r['digests_made']}.", ""]
    if r["reads"]:
        L += ["| Call | File | Tokens | Card first? | Range? |", "| --- | --- | --- | --- | --- |"]
        for x in sorted(r["reads"], key=lambda x: -x["tokens"])[:20]:
            L.append(f"| {x['call'] + 1} | `{x['path']}` | {x['tokens']} | {'yes' if x['pointed'] else 'no'} | {'yes' if x['partial'] else 'no'} |")
        L.append("")
    mm, o, p = f["memory"], f["output"], f["process"]
    L += ["## Memory and output", "",
          f"- STATE.md rewritten at calls: {mm['state_writes'] or 'never'}. After-compaction hook seen at calls: {mm['hook_fired'] or 'never'}.",
          f"- Long tool outputs (≥{BIG} tokens): {o['long_outputs']}, ~{o['long_output_tokens']} tokens. Check runs: {o['checks_quiet']} through quiet.sh, {o['checks_raw']} not. Images read: {o['images']}.", "",
          "## Process", "",
          f"- First writes, by call: BRIEF.md {p['brief_first_write']}, journal {p['journal_first_write']}, PLAN.md {p['plan_first_write']}, code {p['code_first_write']}.",
          f"- decisions.py runs: {p['chip_runs']}; checks run: {p['check_runs']}; subagents: {p['subagents']}; tokens.py runs: {p['tokens_runs']}.",
          f"- Deploy commands: {len(p['deploys'])}" + (f" (first: `{p['deploys'][0][:70]}`)" if p['deploys'] else "") +
          f"; the brief's grant: {checks.get('deploy_grant') or 'none written'}.", ""]
    if checks:
        L += ["## The project's checks, run now", ""]
        for name_, v in checks.items():
            if name_ == "deploy_grant":
                continue
            mark = "pass" if v["ok"] else ("–" if v["ok"] is None else "FAIL")
            L.append(f"- **{name_}**: {mark}" + (f"\n\n  ```\n  " + v["text"].replace("\n", "\n  ") + "\n  ```" if v["ok"] is False else ""))
        L.append("")
    L += ["## Where Builder slipped", "", "Ranked by severity, then by the re-read tokens each one carried.", "",
          "| Severity | Call | What | Carried |", "| --- | --- | --- | --- |"]
    for s in f["slips"]:
        L.append(f"| {s['severity']} | {s['call'] or '–'} | {s['what']} | {k(s['carried_tokens']) if s['carried_tokens'] else '–'} |")
    if not f["slips"]:
        L.append("| – | – | no slips found | – |")
    return "\n".join(L) + "\n"


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def main(argv):
    if "--baseline" in argv:
        files = [a for a in argv if not a.startswith("--")]
        per = {Path(p).parent.name.split('-Documents-')[-1]: {k_: v for k_, v in analyse([Path(p)])["tokens"].items() if k_ != "compaction_calls"} for p in files}
        keys = next(iter(per.values())).keys()
        summary = {k_: median([v[k_] for v in per.values()]) for k_ in keys}
        (HERE / "baseline.json").write_text(json.dumps({"sessions": per, "summary": summary}, indent=1))
        print(f"wrote {HERE / 'baseline.json'} from {len(per)} sessions")
        return 0
    baseline = json.loads((HERE / "baseline.json").read_text()) if (HERE / "baseline.json").exists() else {}
    if "--session" in argv:
        p = Path(argv[argv.index("--session") + 1])
        f = analyse([p])
        print(report(p.stem, {}, f, {}, baseline))
        return 0
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    trial = Path(args[0]).expanduser().resolve()
    meta = json.loads((trial / "harness" / "trial.json").read_text()) if (trial / "harness" / "trial.json").exists() else {}
    main_t, subs = transcripts_for(trial)
    if not main_t:
        print(f"no transcripts for {trial} under ~/.claude/projects; was claude started in that folder?")
        return 1
    project = find_project(trial)
    f = analyse(main_t, trial, project)
    f["subagent_transcripts"] = len(subs)
    checks = {} if "--no-checks" in argv else run_checks(project, "--full" in argv)
    text = report(trial.name, meta, f, checks, baseline)
    out = trial / "harness"
    out.mkdir(exist_ok=True)
    (out / "report.md").write_text(text)
    (out / "metrics.json").write_text(json.dumps({"meta": meta, "project": str(project) if project else None,
                                                  "checks": checks, **{k_: v for k_, v in f.items()}}, indent=1))
    index = trial.parent / "index.md"
    if not index.exists():
        index.write_text("# Builder trials\n\n| Trial | Builder | Calls | At first plan | Peak | Mean | Re-read | Above 200k | High slips | Checks |\n"
                         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    t = f["tokens"]
    highs = sum(1 for s in f["slips"] if s["severity"] == "high")
    ok = all(v.get("ok") is not False for kk, v in checks.items() if kk != "deploy_grant") if checks else None
    with index.open("a") as fh:
        fh.write(f"| [{trial.name}]({trial.name}/harness/report.md) | {meta.get('builder_commit', '?')} | {t['calls']} | {k(t['at_plan'])} | "
                 f"{k(t['peak'])} | {k(t['mean'])} | {k(t['reread'])} | {k(t['above_200k_share'])} | {highs} | "
                 f"{'pass' if ok else '–' if ok is None else 'FAIL'} |\n")
    print(text)
    print(f"wrote {out / 'report.md'} and metrics.json; index: {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
