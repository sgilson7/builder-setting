#!/usr/bin/env python3
"""Render every scene file (or the ones named) in light and dark, remux each step's
clip so the same render gives the same bytes, and write the manifest the checks and
the player read.

    .venv-manim/bin/python tools/manim/build.py [deck/scenes/ID.json ...] [--out DIR]

For each scene, deck/media/<id>/ gets light/step-NN.mp4, light/step-NN.png, the same
under dark/, and manifest.json. --out writes the media somewhere else (the render
audit uses it to compare a fresh render with the committed one). Each theme renders
in its own process, because Manim's config and Pango's fonts are process-wide.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import manifest  # noqa: E402
import mp4  # noqa: E402
import scene as scenefile  # noqa: E402

MODES = ("light", "dark")
REMUX = ["-c", "copy", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
         "-movflags", "+faststart"]


def build(scene_path, media_root):
    theme = scenefile.load_theme()
    scene = scenefile.load(scene_path, theme)
    out = media_root / scene["id"]
    if out.exists():
        shutil.rmtree(out)
    clips = {}
    with tempfile.TemporaryDirectory(prefix="manim-") as tmp:
        for mode in MODES:
            work = Path(tmp) / mode
            subprocess.run([sys.executable, str(HERE / "render.py"), str(scene_path), mode, str(work)], check=True)
            sections = sorted(work.glob("manim/videos/*/sections/*.mp4"))
            if len(sections) != len(scene["steps"]):
                raise SystemExit(f"{scene['id']} {mode}: {len(sections)} clips for {len(scene['steps'])} steps")
            (out / mode).mkdir(parents=True)
            rows = []
            for i, src in enumerate(sections):
                name = f"step-{i + 1:02d}"
                clip = out / mode / f"{name}.mp4"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *REMUX, str(clip)], check=True)
                png = out / mode / f"{name}.png"
                shutil.copyfile(work / f"{name}.png", png)
                rows.append(manifest.describe(out, clip, png))
            clips[mode] = rows
    m = manifest.make(scene, theme, clips)
    (out / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
    info = [mp4.video_info(clip.read_bytes())["frames"] for clip in sorted((out / "light").glob("*.mp4"))]
    print(f"{scene['id']}: {len(scene['steps'])} steps x {len(MODES)} themes, frames {info}")


def main(argv):
    media = ROOT / "deck" / "media"
    if "--out" in argv:
        i = argv.index("--out")
        media = Path(argv[i + 1]).resolve()
        argv = argv[:i] + argv[i + 2:]
    paths = argv or sorted(str(p) for p in (ROOT / "deck" / "scenes").glob("*.json"))
    for p in paths:
        build(Path(p).resolve(), media)


if __name__ == "__main__":
    main(sys.argv[1:])
