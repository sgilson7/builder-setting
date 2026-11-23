"""The manifest, deck/media/<id>/manifest.json: what a render was made from and what
it made. The checks compare it with the files now on disk, so a stale or tampered
render fails in under a second with no Manim (Manim Lab PLAN.md P6). Stdlib only, except
make(), which runs under .venv-manim during a render.

    {"scene": id, "scene_sha256", "theme_sha256", "renderer_sha256",
     "fonts": {file: sha256}, "manim": version, "ffmpeg": first line of -version,
     "width", "height", "fps",
     "clips": {"light": [{"clip", "sha256", "bytes", "frames", "ms",
                          "png", "png_sha256", "png_bytes"}, ...], "dark": [...]}}
"""
import json
from pathlib import Path

import mp4
import scene as scenefile

ROOT = Path(__file__).resolve().parents[2]
RENDERER = ["tools/manim/render.py", "tools/manim/geometry.py", "tools/manim/scene.py", "tools/manim/build.py",
            "tools/manim/stepscene.py"]
MODES = ("light", "dark")
BUDGET = ROOT / "data" / "manim" / "budget.json"


def renderer_hash(root=ROOT):
    return scenefile.sha256(b"".join(f.encode() + b"\0" + (root / f).read_bytes() for f in RENDERER))


def font_hashes(theme, root=ROOT):
    return {f["file"]: scenefile.sha256((root / f["file"]).read_bytes()) for f in theme["fonts"].values()}


def describe(out, clip, png):
    data = clip.read_bytes()
    info = mp4.video_info(data)
    pdata = png.read_bytes()
    return {"clip": clip.relative_to(out).as_posix(), "sha256": scenefile.sha256(data), "bytes": len(data),
            "frames": info["frames"], "ms": info["ms"],
            "png": png.relative_to(out).as_posix(), "png_sha256": scenefile.sha256(pdata), "png_bytes": len(pdata)}


def make(scene, theme, clips):
    import subprocess
    from importlib.metadata import version
    ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    r = theme["render"]
    return {"scene": scene["id"], "scene_sha256": scenefile.scene_hash(scene),
            "theme_sha256": scenefile.scene_hash(theme), "renderer_sha256": renderer_hash(),
            "fonts": font_hashes(theme), "manim": version("manim"), "ffmpeg": ff,
            "width": scene["width"] * r["scale"], "height": scene["height"] * r["scale"], "fps": r["fps"],
            "clips": clips}


def check(scene, theme, media_dir, root=ROOT):
    """Every fault between a scene and its render, as sentences; [] when it is fresh."""
    faults = []
    path = Path(media_dir) / "manifest.json"
    if not path.exists():
        return [f"{scene['id']} has no render: {path} is missing"]
    m = json.loads(path.read_text())
    if m["scene_sha256"] != scenefile.scene_hash(scene):
        faults.append(f"{scene['id']}: the scene file or its code changed after its render; render it again")
    if m["theme_sha256"] != scenefile.scene_hash(theme):
        faults.append(f"{scene['id']}: theme.json changed after the render; render it again")
    if m["renderer_sha256"] != renderer_hash(root):
        faults.append(f"{scene['id']}: the renderer changed after the render; render it again")
    if m["fonts"] != font_hashes(theme, root):
        faults.append(f"{scene['id']}: a font changed after the render; render it again")
    r = theme["render"]
    width, height = scene["width"] * r["scale"], scene["height"] * r["scale"]
    fm = scenefile.frame_ms(theme)
    for mode in MODES:
        rows = m["clips"].get(mode, [])
        if len(rows) != len(scene["steps"]):
            faults.append(f"{scene['id']} {mode}: {len(rows)} clips for {len(scene['steps'])} steps")
            continue
        for i, (row, step) in enumerate(zip(rows, scene["steps"])):
            where = f"{scene['id']} {mode} step {i + 1}"
            clip, png = Path(media_dir) / row["clip"], Path(media_dir) / row["png"]
            if not clip.exists() or not png.exists():
                faults.append(f"{where}: {row['clip'] if not clip.exists() else row['png']} is missing")
                continue
            data = clip.read_bytes()
            if scenefile.sha256(data) != row["sha256"] or len(data) != row["bytes"]:
                faults.append(f"{where}: {row['clip']} is not the file the render made")
                continue
            info = mp4.video_info(data)
            if info["frames"] != step["move_ms"] // fm or info["ms"] != step["move_ms"]:
                faults.append(f"{where}: the clip has {info['frames']} frames, {info['ms']} ms; "
                              f"the scene says {step['move_ms']} ms, {step['move_ms'] // fm} frames")
            if (info["width"], info["height"]) != (width, height):
                faults.append(f"{where}: the clip is {info['width']}x{info['height']}, not {width}x{height}")
            pdata = png.read_bytes()
            if scenefile.sha256(pdata) != row["png_sha256"]:
                faults.append(f"{where}: {row['png']} is not the picture the render made")
            elif mp4.png_size(pdata) != (width, height):
                faults.append(f"{where}: the final frame is not {width}x{height}")
    return faults


def sizes(media_dir):
    """(largest clip, all bytes) of one render: clips, pictures and manifest."""
    files = [p for p in Path(media_dir).rglob("*") if p.is_file()]
    clips = [p.stat().st_size for p in files if p.suffix == ".mp4"]
    return max(clips, default=0), sum(p.stat().st_size for p in files)


def over_budget(media_root, budget=None):
    budget = budget or json.loads(BUDGET.read_text())
    faults, total = [], 0
    for d in sorted(p for p in Path(media_root).iterdir() if p.is_dir()):
        biggest, size = sizes(d)
        total += size
        if biggest > budget["clip_bytes"]:
            faults.append(f"{d.name}: a clip is {biggest} bytes, over the budget of {budget['clip_bytes']}")
        if size > budget["animation_bytes"]:
            faults.append(f"{d.name}: {size} bytes, over the budget of {budget['animation_bytes']} per animation")
    if total > budget["deck_bytes"]:
        faults.append(f"the deck's media is {total} bytes, over the budget of {budget['deck_bytes']}")
    return faults
