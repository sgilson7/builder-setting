#!/usr/bin/env python3
"""Checks on the site tools/manim/sitepages.py writes and tools/manim/publish.py copies.

    python3 -m unittest discover -s tests/manim

Plain python3, stdlib only; no Manim. They run on the kit's sample site
(data/manim/site.json: two units, one animation each). Each test was seen to fail
against a planted defect (Builder's scripts/prove-checks.sh; the kit README lists
them). From Manim Lab's checks on its CSC 226 site.
"""
import json
import posixpath
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "manim"))
import publish  # noqa: E402
import sitepages  # noqa: E402

SITE, SCENES = sitepages.load()
BASE = ROOT / SITE["root"]
PAGES = sitepages.pages(SITE, SCENES)


def links(text):
    return re.findall(r'(?:href|src)="([^"]+)"', text)


def ids(text):
    return set(re.findall(r'\bid="([^"]+)"', text))


class Site(unittest.TestCase):
    def test_the_pages_on_disk_are_current(self):
        for name, text in PAGES.items():
            self.assertEqual((BASE / name).read_text(), text, f"{name}: run python3 tools/manim/sitepages.py")

    def test_every_animation_has_its_own_route(self):
        # the sample has two units of one animation each: flow/sample-flow/ and code/sample-dots/
        for u in SITE["units"]:
            for s in u["slides"]:
                page = PAGES.get(f'{u["id"]}/{s["scene"]}/index.html')
                self.assertIsNotNone(page, s["scene"])
                self.assertIn(f'<div data-manim="{s["scene"]}"></div>', page)
                self.assertIn('data-manim-base="../../"', page)
                for st in SCENES[s["scene"]]["steps"]:
                    self.assertIn(sitepages.words(st["t"]), page, s["scene"])
        self.assertIn('data-manim-base="../"', PAGES["flow/index.html"])

    def test_every_link_on_the_site_resolves(self):
        files = set(PAGES) | {p.relative_to(BASE).as_posix() for p in BASE.rglob("*") if p.is_file()}
        for name, text in PAGES.items():
            for href in links(text):
                if href.startswith(("https://", "http://")):
                    continue
                path, _, frag = href.partition("#")
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), path)) if path else name
                if target == "." or path.endswith("/"):
                    target = posixpath.join("" if target == "." else target, "index.html")
                self.assertIn(target, files, f"{name} links to {href}")
                if frag:
                    self.assertIn(frag, ids(PAGES.get(target, "")), f"{name} links to {href}")

    def test_the_pager_walks_every_animation_in_deck_order(self):
        rows = sitepages.order(SITE, SCENES)
        at, seen = rows[0]["route"], []
        while at and at not in seen:
            seen.append(at)
            nxt = re.search(r'<a class="next" href="\.\./\.\./([^"]+)"', PAGES[at + "index.html"])
            at = nxt and nxt[1]
        self.assertEqual(seen, [r["route"] for r in rows])
        self.assertEqual(seen, ["flow/sample-flow/", "code/sample-dots/"])

    def test_a_scene_in_no_unit_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = json.loads(sitepages.CONFIG.read_text())
            cfg["units"] = cfg["units"][:1]
            path = Path(tmp) / "site.json"
            path.write_text(json.dumps(cfg))
            with self.assertRaises(SystemExit) as e:
                sitepages.load(path)
            self.assertIn("in no unit ['sample-dots']", str(e.exception))

    def test_counts_are_computed(self):
        # the home page says "All 2 animations as one deck"; site.json holds only "{n}"
        self.assertIn(">All 2 animations as one deck<", PAGES["index.html"])
        self.assertNotRegex(json.dumps(SITE["words"], ensure_ascii=False), r"\d")


class Publish(unittest.TestCase):
    def test_nothing_published_names_a_source(self):
        out = publish.content()
        for sid, scene in SCENES.items():
            kept = json.loads(out[f"scenes/{sid}.json"])
            self.assertEqual(sorted(kept), sorted(publish.SCENE_KEEP), sid)
            for name, data in out.items():
                if name.endswith((".html", ".json")):
                    self.assertNotIn(scene["source"], data.decode(), f"{name} names {sid}'s source")
                    self.assertNotIn(scene["code"] if "code" in scene else "\0", data.decode(), name)

    def test_every_file_a_page_needs_is_published(self):
        out = publish.content()
        for name in PAGES:
            for href in links(PAGES[name]):
                path = href.partition("#")[0]
                if not path or path.startswith(("https://", "http://")) or path.endswith("/"):
                    continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), path))
                self.assertIn(target, out, f"{name} needs {href}")
        for sid in SCENES:
            self.assertIn(f"media/{sid}/manifest.json", out)


if __name__ == "__main__":
    unittest.main()
