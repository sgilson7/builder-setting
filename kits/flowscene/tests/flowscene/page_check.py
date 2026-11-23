#!/usr/bin/env python3
"""The kit's sample page, deck/flowscene-sample.html, in Chromium, Firefox and WebKit.

Serves deck/ on 127.0.0.1 and, in each engine, with and without reduced motion, checks:

- the scene file loads and draws a box per node and a tab per flow;
- Next moves to step 2, shows that step's excerpt with its lines lit, and sends a mark;
- under reduced motion the mark is placed at the end of its path at once;
- Play advances by itself and Pause holds the step;
- another flow's tab starts that flow at step 1, and a contract step shows its heading;
- the page makes no off-origin request and logs no error.

Needs Playwright (Builder's .venv has it):

    .venv/bin/python kits/flowscene/tests/flowscene/page_check.py
    BUILDER_ENGINES=chromium .venv/bin/python kits/flowscene/tests/flowscene/page_check.py
"""
import functools
import http.server
import json
import os
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "deck"
ENGINES = os.environ.get("BUILDER_ENGINES", "chromium firefox webkit").split()
SCENE = json.loads((DECK / "flows" / "sample.json").read_text())
failures = []


def check(ok, what):
    print(("  PASS " if ok else "  FAIL ") + what)
    if not ok:
        failures.append(what)


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".json": "application/json"}

    def log_message(self, *args):
        pass


STATE = """() => {
  const r = document.querySelector('[data-flow="sample"]');
  const m = r.querySelector('.fx-scene svg g:last-of-type g');
  return {count: r.querySelector('.fx-count').textContent, now: r.querySelector('.fx-now').textContent,
          cap: r.querySelector('.fx-code figcaption').textContent, lit: r.querySelectorAll('.fx-lit').length,
          mark: m ? m.getAttribute('transform') : null, play: r.querySelector('.fx-play').textContent,
          boxes: r.querySelectorAll('.fx-node').length, tabs: r.querySelectorAll('.fx-pick button').length};
}"""


def run_engine(p, engine, base, **ctx):
    label = engine + (" " + " ".join(f"{k}={v}" for k, v in ctx.items()) if ctx else "")
    print(f"\n[{label}]")
    seen = {"foreign": [], "console": [], "errors": []}
    browser = getattr(p, engine).launch()
    context = browser.new_context(**ctx)
    context.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base + "/")
                  else (seen["foreign"].append(r.request.url), r.abort()))
    page = context.new_page()
    page.on("console", lambda m: seen["console"].append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: seen["errors"].append(str(e)))
    page.goto(base + "/flowscene-sample.html")
    page.wait_for_selector('[data-flow="sample"][data-ready="true"]', timeout=10000)
    s = page.evaluate(STATE)
    n0 = len(SCENE["flows"][0]["steps"])
    check(s["boxes"] == len(SCENE["nodes"]) and s["tabs"] == len(SCENE["flows"]),
          f"a box per node and a tab per flow {s['boxes']}, {s['tabs']}")
    check(s["count"] == f"Step 1 of {n0}", f"the first flow starts at step 1 {s['count']}")

    page.get_by_role("button", name="Next step").click()
    s = page.evaluate(STATE)
    step = SCENE["flows"][0]["steps"][1]
    c = SCENE["code"][step["c"]]
    check(s["count"] == f"Step 2 of {n0}" and s["now"] == "2. " + step["t"], f"Next moves to step 2 {s['now']}")
    check(s["cap"].startswith(c["file"] + ":") and s["lit"] == step["hl"][1] - step["hl"][0] + 1,
          f"step 2 shows {c['file']} with its lines lit {s['cap']}, {s['lit']}")
    if ctx.get("reduced_motion") == "reduce":
        check(s["mark"] is not None and s["mark"] != "", f"reduced motion: the mark is placed at once {s['mark']}")
        page.wait_for_timeout(300)
        check(page.evaluate(STATE)["mark"] == s["mark"], "reduced motion: the mark does not move afterwards")
    else:
        page.wait_for_timeout(1500)
        m = page.evaluate(STATE)["mark"]
        check(m is not None and m != s["mark"], f"the mark travels along its path {s['mark']} -> {m}")

    page.get_by_role("button", name="Restart").click()
    page.get_by_role("button", name="Play").click()
    page.wait_for_function("() => document.querySelector('.fx-count').textContent.startsWith('Step 2')", timeout=15000)
    check(True, "Play advances by itself")
    page.get_by_role("button", name="Pause").click()
    held = page.evaluate(STATE)["count"]
    page.wait_for_timeout(2500)
    check(page.evaluate(STATE)["count"] == held, f"Pause holds the step {held}")

    page.get_by_role("tab", name=SCENE["flows"][1]["title"]).click()
    s = page.evaluate(STATE)
    n1 = len(SCENE["flows"][1]["steps"])
    check(s["count"] == f"Step 1 of {n1}", f"the second flow's tab starts it at step 1 {s['count']}")
    for _ in range(n1 - 1):
        page.get_by_role("button", name="Next step").click()
    s = page.evaluate(STATE)
    check(s["cap"] == SCENE["flows"][1]["steps"][-1]["x"]["h"], f"a contract step shows its heading {s['cap']}")

    check(not seen["foreign"], f"no off-origin request {seen['foreign']}")
    check(not seen["errors"], f"no uncaught page error {seen['errors']}")
    check(not seen["console"], f"no console error {seen['console']}")
    browser.close()


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(DECK)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://%s:%d" % server.server_address[:2]
    with sync_playwright() as p:
        for engine in ENGINES:
            run_engine(p, engine, base)
            run_engine(p, engine, base, reduced_motion="reduce")
    server.shutdown()
    if failures:
        sys.exit(f"\nPAGE CHECK FAILED: {len(failures)} checks")
    print(f"\nPAGE CHECK PASSED in {', '.join(ENGINES)}")


if __name__ == "__main__":
    main()
