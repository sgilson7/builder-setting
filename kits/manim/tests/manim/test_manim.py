#!/usr/bin/env python3
"""Checks on the Manim kit that need no Manim: plain python3, stdlib only.

    python3 -m unittest discover -s tests/manim

Expected values are worked out by hand in the comments, never by calling the code
under test. Each test was seen to fail against a planted defect (Builder's
scripts/prove-checks.sh; the kit README lists them).
"""
import copy
import hashlib
import json
import re
import struct
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "manim"))
import geometry  # noqa: E402
import manifest  # noqa: E402
import mp4  # noqa: E402
import scene as scenefile  # noqa: E402
import theme as themecss  # noqa: E402

SCENES = ROOT / "deck" / "scenes"
MEDIA = ROOT / "deck" / "media"
THEME = scenefile.load_theme()


def scene(name):
    return json.loads((SCENES / f"{name}.json").read_text())


class SceneFile(unittest.TestCase):
    def refused(self, s, words):
        with self.assertRaises(scenefile.SceneError) as e:
            scenefile.validate(s, THEME)
        self.assertIn(words, str(e.exception))

    def test_the_committed_scenes_are_valid(self):
        for p in sorted(SCENES.glob("*.json")):
            scenefile.load(p, THEME)

    def test_a_scene_naming_a_missing_node_is_refused(self):
        s = scene("sample-flow")
        s["edges"][0]["b"] = "nowhere"
        self.refused(s, "'nowhere'")

    def test_a_lit_node_that_does_not_exist_is_refused(self):
        s = scene("sample-flow")
        s["steps"][1]["light"] = ["rend"]
        self.refused(s, "'rend'")

    def test_a_step_without_words_is_refused(self):
        s = scene("sample-flow")
        s["steps"][2]["t"] = "  "
        self.refused(s, "step 3 has no words")

    def test_a_scene_with_a_fraction_is_refused(self):
        s = scene("sample-flow")
        s["nodes"]["file"]["x"] = 120.5
        self.refused(s, "integers only")

    def test_a_move_that_is_not_whole_frames_is_refused(self):
        # theme fps 50: a frame is 20 ms, so 810 ms is 40.5 frames
        s = scene("sample-flow")
        s["steps"][0]["move_ms"] = 810
        self.refused(s, "not a whole number of 20 ms frames")

    def test_a_move_shorter_than_the_fade_is_refused(self):
        s = scene("sample-flow")
        s["steps"][0]["move_ms"] = 200
        self.refused(s, "less than fade_ms")

    def test_a_text_style_the_theme_lacks_is_refused(self):
        s = scene("sample-flow")
        s["nodes"]["player"]["lines"][0][0] = "heading"
        self.refused(s, "'heading'")

    def test_the_scene_hash_ignores_key_order(self):
        s = scene("sample-flow")
        reordered = copy.deepcopy(dict(reversed(list(s.items()))))
        self.assertEqual(scenefile.scene_hash(s), scenefile.scene_hash(reordered))
        s["steps"][0]["hold_ms"] += 20
        self.assertNotEqual(scenefile.scene_hash(s), scenefile.scene_hash(reordered))


class FlowSceneRules(unittest.TestCase):
    def test_the_border_point_by_hand(self):
        # file (120,80), box 200x90, toward (300,170): dx 180, dy 90.
        # s = min(100/180, 45/90) = 0.5; point = (120 + 90, 80 + 45) = (210, 125), a corner's
        # bottom edge. Toward render (360,80): dy 0, so s = 100/240 and the point is (220, 80).
        nodes = scene("sample-flow")["nodes"]
        self.assertEqual(geometry.border(nodes, "file", (300, 170)), (210.0, 125.0))
        self.assertEqual(geometry.border(nodes, "file", (360, 80)), (220.0, 80.0))

    def test_the_css_ease_by_hand(self):
        ease = geometry.cubic_bezier(0.4, 0.1, 0.3, 1)
        self.assertEqual(ease(0), 0)
        self.assertEqual(ease(1), 1)
        # cubic-bezier(.4,.1,.3,1) at x = 0.5: x(t) = 3(1-t)^2 t (0.4) + 3(1-t) t^2 (0.3) + t^3
        # is 0.4943 at t = 0.64 and 0.4988 at t = 0.645, so t is about 0.6465; then
        # y(t) = 3(1-t)^2 t (0.1) + 3(1-t) t^2 (1) + t^3 = 0.0242 + 0.4433 + 0.2702 = 0.7377
        self.assertAlmostEqual(ease(0.5), 0.738, places=2)


def box(kind, payload):
    return struct.pack(">I4s", 8 + len(payload), kind.encode()) + payload


def tiny_mp4(counts, timescale, duration, w, h):
    """An MP4 skeleton built by hand: ftyp, and moov > trak > tkhd, mdia > mdhd, hdlr, stts."""
    stts = box("stts", struct.pack(">I", 0) + struct.pack(">I", len(counts)) +
               b"".join(struct.pack(">II", c, 1) for c in counts))
    mdhd = box("mdhd", bytes(4) + bytes(8) + struct.pack(">II", timescale, duration) + bytes(4))
    hdlr = box("hdlr", bytes(8) + b"vide" + bytes(12))
    tkhd = box("tkhd", bytes(76) + struct.pack(">II", w << 16, h << 16))
    trak = box("trak", tkhd + box("mdia", mdhd + hdlr + box("minf", box("stbl", stts))))
    return box("ftyp", b"isom" + bytes(4)) + box("moov", trak)


class Mp4Reader(unittest.TestCase):
    def test_the_reader_counts_frames_in_a_hand_built_file(self):
        # 30 + 26 samples = 56 frames; 57344 ticks at 51200 a second = 1120 ms
        info = mp4.video_info(tiny_mp4([30, 26], 51200, 57344, 1800, 460))
        self.assertEqual((info["frames"], info["ms"], info["width"], info["height"]), (56, 1120, 1800, 460))

    def test_the_reader_refuses_a_file_that_is_not_mp4(self):
        with self.assertRaises(ValueError):
            mp4.video_info(b"\x00\x00\x00\x08free" + bytes(32))


class Media(unittest.TestCase):
    def test_every_step_has_a_clip_and_a_final_frame_in_each_theme(self):
        for p in sorted(SCENES.glob("*.json")):
            s = scenefile.load(p, THEME)
            self.assertEqual(manifest.check(s, THEME, MEDIA / s["id"]), [], s["id"])

    def copy_media(self, tmp, name):
        dest = Path(tmp) / name
        shutil.copytree(MEDIA / name, dest)
        return dest

    def test_a_scene_edited_after_its_render_is_stale(self):
        s = scene("sample-flow")
        s["steps"][1]["t"] = s["steps"][1]["t"].replace("light and dark", "dark and light")
        faults = manifest.check(s, THEME, MEDIA / "sample-flow")
        self.assertTrue(any("scene file or its code changed after its render" in f for f in faults), faults)

    def test_a_changed_theme_makes_the_render_stale(self):
        theme = copy.deepcopy(THEME)
        theme["light"]["lit"] = "#ffffff"
        faults = manifest.check(scene("sample-flow"), theme, MEDIA / "sample-flow")
        self.assertTrue(any("theme.json changed" in f for f in faults), faults)

    def test_a_swapped_clip_fails_its_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self.copy_media(tmp, "sample-flow")
            a, b = d / "dark" / "step-01.mp4", d / "dark" / "step-02.mp4"
            data = a.read_bytes()
            a.write_bytes(b.read_bytes())
            b.write_bytes(data)
            faults = manifest.check(scene("sample-flow"), THEME, d)
            self.assertTrue(any("dark step 1" in f and "not the file the render made" in f for f in faults), faults)

    def test_a_missing_final_frame_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self.copy_media(tmp, "sample-flow")
            (d / "light" / "step-03.png").unlink()
            faults = manifest.check(scene("sample-flow"), THEME, d)
            self.assertTrue(any("light step 3" in f and "missing" in f for f in faults), faults)

    def test_a_clip_whose_length_disagrees_with_the_scene_fails(self):
        # Someone edits move_ms and re-stamps the manifest's scene hash by hand
        # without rendering: the hash passes, the 40-frame clip does not.
        with tempfile.TemporaryDirectory() as tmp:
            d = self.copy_media(tmp, "sample-flow")
            s = scene("sample-flow")
            s["steps"][0]["move_ms"] = 1000
            m = json.loads((d / "manifest.json").read_text())
            m["scene_sha256"] = scenefile.scene_hash(s)
            (d / "manifest.json").write_text(json.dumps(m))
            faults = manifest.check(s, THEME, d)
            self.assertEqual(faults, ["sample-flow light step 1: the clip has 40 frames, 800 ms; "
                                      "the scene says 1000 ms, 50 frames",
                                      "sample-flow dark step 1: the clip has 40 frames, 800 ms; "
                                      "the scene says 1000 ms, 50 frames"])

    def test_the_media_fits_the_budget(self):
        self.assertEqual(manifest.over_budget(MEDIA), [])

    def test_a_tight_budget_fails(self):
        # every animation's largest clip is tens of kilobytes or more: a 1000-byte limit
        # must trip once per animation, and only the clip limit
        faults = manifest.over_budget(MEDIA, {"clip_bytes": 1000, "animation_bytes": 10 ** 9, "deck_bytes": 10 ** 9})
        animations = sorted(p.name for p in MEDIA.iterdir() if p.is_dir())
        self.assertEqual([f.split(":")[0] for f in faults], animations, faults)
        self.assertTrue(all("over the budget of 1000" in f for f in faults), faults)


class ThemeAndFiles(unittest.TestCase):
    def test_the_theme_css_matches_theme_json(self):
        css = (ROOT / "deck" / "manim" / "theme.css").read_text()
        self.assertEqual(css, themecss.css(THEME))
        # by hand: the light lit colour and the dark req colour are in it
        self.assertIn("--lit: #fff4c9;", css)
        self.assertIn("--req: #86b2e4;", css)

    def test_every_font_the_renderer_registers_is_in_licenses(self):
        # The kit's README gives the LICENSES.md rows a project pastes; a project's own
        # copy of this test reads its LICENSES.md instead.
        licences = (ROOT / "README.md").read_text()
        sums = (ROOT / "deck" / "fonts" / "SHA256SUMS").read_text()
        for f in THEME["fonts"].values():
            path = ROOT / f["file"]
            self.assertIn(f"`{f['file']}`", licences, f["family"])
            self.assertIn(f["family"], licences)
            self.assertIn("Open Font License", (ROOT / f["licence"]).read_text())
            self.assertIn(f"{scenefile.sha256(path.read_bytes())}  {path.name}", sums)

def code_of(js):
    """JavaScript with its comments and string literals blanked, for D3's checks."""
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`',
                  lambda m: " " if m[0].startswith("/") else '""', js, flags=re.S)


class CodeScenes(unittest.TestCase):
    """Scenes drawn by Manim code (tools/manim/stepscene.py, animations/)."""

    def test_a_code_scene_whose_code_is_missing_is_refused(self):
        s = scene("sample-dots")
        s["code"] = "animations/no-such-file.py"
        with self.assertRaises(scenefile.SceneError) as e:
            scenefile.validate(s, THEME)
        self.assertIn("does not exist", str(e.exception))

    def test_a_code_step_that_is_not_whole_frames_is_refused(self):
        s = scene("sample-dots")
        s["steps"][0]["move_ms"] = 1210
        with self.assertRaises(scenefile.SceneError) as e:
            scenefile.validate(s, THEME)
        self.assertIn("not a positive whole number of 20 ms frames", str(e.exception))

    def test_the_code_is_part_of_the_render_it_made(self):
        # The render's scene hash covers the code, so editing only the code makes it stale.
        raw = scene("sample-dots")
        loaded = scenefile.load(SCENES / "sample-dots.json", THEME)
        code = (ROOT / raw["code"]).read_bytes()
        self.assertEqual(loaded["code_sha256"], hashlib.sha256(code).hexdigest())
        made = json.loads((MEDIA / "sample-dots" / "manifest.json").read_text())["scene_sha256"]
        self.assertEqual(made, scenefile.scene_hash(loaded))
        self.assertNotEqual(made, scenefile.scene_hash(raw))
        edited = dict(loaded, code_sha256=hashlib.sha256(code + b"#").hexdigest())
        faults = manifest.check(edited, THEME, MEDIA / "sample-dots")
        self.assertEqual(faults, ["sample-dots: the scene file or its code changed after its render; render it again"])

class PageScripts(unittest.TestCase):
    SCRIPTS = ["deck/manim/player.js"]

    def test_code_of_blanks_comments_and_strings(self):
        self.assertEqual(code_of('a = "2" + 3; /* 4 */ b(\'5\') // 6\n'), 'a = "" + 3;   b("")  \n')

    def test_the_player_holds_no_number_but_0_and_1(self):
        for path in self.SCRIPTS:
            code = code_of((ROOT / path).read_text())
            numbers = re.findall(r"(?<![\w$.])\d[\w.]*", code)
            self.assertEqual([n for n in numbers if n not in ("0", "1")], [], path)
            self.assertEqual(re.findall(r"\b(?:Math|parseInt|parseFloat|toFixed)\b", code), [], path)

    def test_the_player_parses_no_html(self):
        # step words go in with textContent, `backticks` become <code>
        code = code_of((ROOT / "deck/manim/player.js").read_text())
        self.assertEqual(re.findall(r"\b(?:innerHTML|outerHTML|insertAdjacentHTML|eval)\b", code), [])


if __name__ == "__main__":
    unittest.main()
