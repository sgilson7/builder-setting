#!/usr/bin/env python3
"""The kit's sample page, deck/sample.html, in Chromium, Firefox and WebKit.

Serves deck/ on 127.0.0.1 (with byte ranges, which WebKit needs for video) and,
in each engine, in light, dark and reduced motion, checks:

- every scene file has a player on the page, loaded with its steps;
- a player shows step 1's final frame in the page's colour scheme;
- Next plays step 2's H.264 clip (it reaches loadeddata), and when the clip ends
  the final frame of step 2 is behind it; under reduced motion no clip plays;
- Play starts, Pause stops the clip and the timer, Restart returns to step 1;
- the page makes no off-origin request and logs no error.

Needs Playwright (Builder's .venv has it):

    .venv/bin/python kits/manim/tests/manim/page_check.py
    BUILDER_ENGINES=chromium .venv/bin/python kits/manim/tests/manim/page_check.py
"""
import functools
import http.server
import json
import os
import re
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "deck"
ENGINES = os.environ.get("BUILDER_ENGINES", "chromium firefox webkit").split()
failures = []


def check(ok, what):
    print(("  PASS " if ok else "  FAIL ") + what)
    if not ok:
        failures.append(what)


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static files with single byte ranges, so WebKit will play video."""
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".json": "application/json", ".mp4": "video/mp4"}

    def send_head(self):
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        path = Path(self.translate_path(self.path))
        if not m or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        start = int(m[1]) if m[1] else size - int(m[2])
        end = min(int(m[2]), size - 1) if m[1] and m[2] else size - 1
        f = path.open("rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.range_left = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "range_left", None)
        if left is None:
            return super().copyfile(source, outputfile)
        outputfile.write(source.read(left))

    def log_message(self, *args):
        pass


def player(page, scene):
    return page.locator(f"[data-manim='{scene}']")


def state(page, scene):
    return page.evaluate("""s => {
        const r = document.querySelector(`[data-manim='${s}']`);
        const v = r.querySelector('video'), i = r.querySelector('img');
        return {step: r.dataset.step, playing: r.dataset.playing || 'false', pic: i && i.getAttribute('src'),
                vid: v && v.getAttribute('src'), vidHidden: v ? v.hidden : true, paused: v ? v.paused : true,
                ready: v ? v.readyState : 0, now: r.querySelector('.mp-now') && r.querySelector('.mp-now').textContent};
    }""", scene)


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
    page.goto(base + "/sample.html")
    want = sorted(f"{p.stem}:{len(json.loads(p.read_text())['steps'])}" for p in (DECK / "scenes").glob("*.json"))
    for w in want:
        page.wait_for_selector(f"[data-manim='{w.split(':')[0]}'][data-steps]", timeout=15000)
    ids = page.evaluate("() => [...document.querySelectorAll('[data-manim]')].map(r => r.dataset.manim + ':' + (r.dataset.steps || r.dataset.failed))")
    check(sorted(ids) == want, f"every scene file has a player on the page, loaded with its steps {ids}")

    mode = "dark" if ctx.get("color_scheme") == "dark" else "light"
    for name in ("sample-flow", "sample-dots"):
        s = state(page, name)
        check(s["step"] == "1" and s["pic"] == f"media/{name}/{mode}/step-01.png",
              f"{name} shows step 1's {mode} final frame {s['pic']}")
        root = player(page, name)
        root.get_by_role("button", name="Next step").click()
        if ctx.get("reduced_motion") == "reduce":
            page.wait_for_timeout(500)
            s = state(page, name)
            check(s["step"] == "2" and s["vid"] is None and s["vidHidden"] and s["paused"],
                  f"reduced motion: {name}'s Next plays no clip {s}")
            check(s["pic"] == f"media/{name}/{mode}/step-02.png", f"reduced motion: step 2's final frame {s['pic']}")
        else:
            page.wait_for_function(f"() => document.querySelector(\"[data-manim='{name}'] video\").readyState >= 2",
                                   timeout=10000)
            check(state(page, name)["vid"] == f"media/{name}/{mode}/step-02.mp4", f"{name}'s Next plays step 2's {mode} clip")
            page.wait_for_function(f"() => document.querySelector(\"[data-manim='{name}'] video\").ended", timeout=10000)
            s = state(page, name)
            check(s["pic"] == f"media/{name}/{mode}/step-02.png", f"when {name}'s clip ends, step 2's final frame is behind it {s['pic']}")

    root = player(page, "sample-flow")
    root.get_by_role("button", name="Play").click()
    page.wait_for_timeout(300)
    check(state(page, "sample-flow")["playing"] == "true", "Play starts")
    root.get_by_role("button", name="Pause").click()
    s = state(page, "sample-flow")
    check(s["playing"] == "false" and s["paused"], f"Pause stops the clip and the timer {s}")
    step = s["step"]
    page.wait_for_timeout(1500)
    check(state(page, "sample-flow")["step"] == step, "after Pause the step stays put")
    root.get_by_role("button", name="Restart").click()
    check(state(page, "sample-flow")["step"] == "1", "Restart returns to step 1")

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
            run_engine(p, engine, base, color_scheme="dark")
            run_engine(p, engine, base, reduced_motion="reduce")
    server.shutdown()
    if failures:
        sys.exit(f"\nPAGE CHECK FAILED: {len(failures)} checks")
    print(f"\nPAGE CHECK PASSED in {', '.join(ENGINES)}")


if __name__ == "__main__":
    main()
