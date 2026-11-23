#!/usr/bin/env python3
"""Write a site of Manim animations from data/manim/site.json and the scene files.

    python3 tools/manim/sitepages.py          write the pages
    python3 tools/manim/sitepages.py --check  fail if a page is out of date

From Manim Lab's CSC 226 site (T4), which put thirty-seven animations on GitHub
Pages this way. The site's root is the folder that holds scenes/, media/, manim/
and fonts/ (site.json "root", deck/ by default). It gets one route per animation
and one per unit:

    index.html                  home: every unit and every animation, linked
    deck.html                   every animation as one slide deck
    <unit>/index.html           the unit as a slide deck
    <unit>/<scene>/index.html   one animation: its player, its summary, every step,
                                and a pager through every animation in deck order

Pages below the root find scenes/ and media/ through data-manim-base on <body>.
Every word a reader sees comes from site.json ("words", "player_labels") or from
the scene files; counts are computed here. Every scene in scenes/ must be in a unit
exactly once. A scene's "source" is never written into a page; tools/manim/publish.py
also leaves it out of the scene files it copies.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "data" / "manim" / "site.json"


def e(s):
    return html.escape(str(s), quote=True)


def words(s):
    """A step's words as HTML, `backticks` set as code, as player.js sets them."""
    return "".join(f"<code>{e(p)}</code>" if k % 2 else e(p) for k, p in enumerate(s.split("`")))


def say(site, key, **fields):
    """A string from site.json's words, its fields escaped (keys ending _html are HTML)."""
    text = site["words"][key]
    if key.endswith("_html"):
        return text.format(**fields)
    return e(text.format(**fields))


def load(config=CONFIG):
    site = json.loads(Path(config).read_text())
    base = ROOT / site["root"]
    scenes = {p.stem: json.loads(p.read_text()) for p in sorted((base / "scenes").glob("*.json"))}
    named = [s["scene"] for u in site["units"] for s in u["slides"]]
    dupes = sorted({n for n in named if named.count(n) > 1})
    missing = sorted(set(named) - set(scenes))
    unlisted = sorted(set(scenes) - set(named))
    if dupes or missing or unlisted:
        raise SystemExit(f"site.json: listed twice {dupes}; no scene file {missing}; in no unit {unlisted}")
    return site, scenes


def order(site, scenes):
    """Every animation in deck order, with its unit, place and route."""
    rows = []
    for u in site["units"]:
        for k, s in enumerate(u["slides"]):
            rows.append({"unit": u, "k": k, "n": len(u["slides"]), "slide": s, "scene": scenes[s["scene"]],
                         "route": f'{u["id"]}/{s["scene"]}/'})
    return rows


def head(site, title, pre, description, canonical, deck_css):
    out = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           f'<title>{e(title)}</title>\n<meta name="description" content="{e(description)}">\n')
    if site.get("site_url"):
        out += f'<link rel="canonical" href="{e(site["site_url"] + canonical)}">\n'
    out += (f'<link rel="stylesheet" href="{pre}manim/theme.css">\n<link rel="stylesheet" href="{pre}manim/deck.css">\n'
            f'<link rel="stylesheet" href="{pre}manim/player.css">\n')
    if not deck_css:
        out += f'<link rel="stylesheet" href="{pre}manim/page.css">\n'
    return out + '</head>\n'


def body(site, pre):
    base = f' data-manim-base="{pre}"' if pre else ''
    return f'<body data-theme-key="{e(site["theme_key"])}"{base}>\n'


def theme_pick(site, cls=""):
    c = f' class="{cls}"' if cls else ''
    return (f'  <select id="nav-theme"{c} aria-label="{say(site, "theme")}">\n'
            f'    <option value="auto">{say(site, "theme_auto")}</option>\n'
            f'    <option value="light">{say(site, "theme_light")}</option>\n'
            f'    <option value="dark">{say(site, "theme_dark")}</option>\n  </select>\n')


def scripts(site, pre, deck):
    labels = json.dumps(site["player_labels"], ensure_ascii=False)
    out = (f'<script type="application/json" id="manim-labels">\n{labels}\n</script>\n'
           f'<script src="{pre}manim/page.js"></script>\n<script src="{pre}manim/player.js"></script>\n')
    if deck:
        out += f'<script src="{pre}manim/deck.js"></script>\n'
    return out + '</body>\n</html>\n'


def deck_page(site, scenes, unit=None):
    """A slide deck: every unit (deck.html), or one unit (<unit>/index.html)."""
    units = [u for u in site["units"] if unit in (None, u["id"])]
    title = site["title"] + (f": {units[0]['name']}" if unit else "")
    pre = "../" if unit else ""
    out = [head(site, title, pre, units[0]["lead"] if unit else site["intro"], f"{unit}/" if unit else "deck.html", True),
           body(site, pre), '<main id="deck">\n\n',
           f'<section id="start" data-title="{e(title)}">\n  <div class="eyebrow">{e(site["eyebrow"])}</div>\n'
           f'  <h1>{e(title)}</h1>\n  <p class="lead">{e(site["intro"])}</p>\n  <ol class="units">\n']
    w = out.append
    for u in site["units"]:
        n = len(u["slides"])
        if unit in (None, u["id"]):
            w(f'    <li><a href="#{u["id"]}">{e(u["name"])}</a>: {say(site, "unit_count", n=n)}</li>\n')
        else:
            w(f'    <li><a href="../{u["id"]}/">{e(u["name"])}</a>: {say(site, "in_own_deck", n=n)}</li>\n')
    w(f'  </ol>\n  <p>{say(site, "deck_help")}</p>\n'
      f'  <p>{say(site, "also_home_html", href=pre or "./")}</p>\n</section>\n\n')
    for u in units:
        n = len(u["slides"])
        w(f'<section id="{u["id"]}" data-title="{e(u["name"])}">\n  <div class="eyebrow">{e(site["eyebrow"])} · {e(u["name"])}</div>\n'
          f'  <h2>{e(u["name"])}</h2>\n  <p class="lead">{e(u["lead"])}</p>\n  <ol class="units">\n')
        for s in u["slides"]:
            w(f'    <li><a href="#{s["scene"]}">{e(scenes[s["scene"]]["title"])}</a></li>\n')
        w('  </ol>\n</section>\n\n')
        for k, s in enumerate(u["slides"]):
            sc = scenes[s["scene"]]
            own = f'{s["scene"]}/' if unit else f'{u["id"]}/{s["scene"]}/'
            w(f'<section id="{s["scene"]}" data-title="{e(sc["title"])}">\n'
              f'  <div class="eyebrow">{e(u["name"])} · {say(site, "place", k=k + 1, n=n)}</div>\n'
              f'  <h2>{e(sc["title"])}</h2>\n  <p class="lead">{e(s["lead"])}</p>\n'
              f'  <div data-manim="{s["scene"]}"></div>\n'
              f'  <p class="from"><a href="{own}">{say(site, "own_page")}</a></p>\n</section>\n\n')
    w(f'</main>\n\n<nav class="pnav" aria-label="{say(site, "slides")}">\n'
      f'  <button class="mp-btn" id="nav-prev" type="button">{say(site, "back_slide")}</button>\n'
      '  <span class="count" id="nav-count"></span>\n'
      f'  <select id="nav-pick" aria-label="{say(site, "go_to_slide")}"></select>\n'
      f'  <button class="mp-btn mp-solid" id="nav-next" type="button">{say(site, "next_slide")}</button>\n'
      + theme_pick(site) + '</nav>\n\n')
    w(scripts(site, pre, True))
    return "".join(out)


def top(site, trail):
    crumbs = ' <span aria-hidden="true">›</span> '.join(trail)
    return (f'<header class="top">\n  <nav class="crumbs" aria-label="{say(site, "crumbs")}">{crumbs}</nav>\n'
            + theme_pick(site, "pick") + '</header>\n')


def foot(site, pre):
    return f'<footer class="foot">\n  <p>{say(site, "credit_html", pre=pre)}</p>\n</footer>\n' + scripts(site, pre, False)


def home(site, scenes):
    rows = order(site, scenes)
    out = [head(site, site["title"], "", site["site_intro"], "", False), body(site, ""),
           top(site, [f'<span>{e(site["home_name"])}</span>']),
           f'<main class="page">\n  <div class="eyebrow">{e(site["eyebrow"])}</div>\n'
           f'  <h1>{e(site["title"])}</h1>\n  <p class="lead">{e(site["site_intro"])}</p>\n']
    w = out.append
    for u in site["units"]:
        w(f'\n  <section class="unit" id="{u["id"]}">\n  <h2>{e(u["name"])}</h2>\n  <p>{e(u["lead"])}</p>\n'
          f'  <p><a class="mp-btn" href="{u["id"]}/">{say(site, "play_unit", unit=u["name"])}</a></p>\n  <ol class="anims">\n')
        for r in rows:
            if r["unit"] is u:
                w(f'    <li><a href="{r["route"]}">{e(r["scene"]["title"])}</a><span>{e(r["slide"]["lead"])}</span></li>\n')
        w('  </ol>\n  </section>\n')
    w(f'\n  <p class="also"><a href="deck.html">{say(site, "all_deck", n=len(rows))}</a></p>\n</main>\n')
    w(foot(site, ""))
    return "".join(out)


def route(site, scenes, i):
    rows = order(site, scenes)
    r = rows[i]
    u, s, sc = r["unit"], r["slide"], r["scene"]
    pre = "../../"
    place = say(site, "place", k=r["k"] + 1, n=r["n"])
    out = [head(site, f'{sc["title"]} · {site["title"]}', pre, s["lead"], r["route"], False), body(site, pre),
           top(site, [f'<a href="{pre}">{e(site["home_name"])}</a>', f'<a href="../">{e(u["name"])}</a>',
                      f'<span>{place}</span>']),
           f'<main class="page">\n  <div class="eyebrow">{e(u["name"])} · {place}</div>\n'
           f'  <h1>{e(sc["title"])}</h1>\n  <p class="lead">{e(s["lead"])}</p>\n'
           f'  <div data-manim="{s["scene"]}"></div>\n'
           f'  <p class="from"><a href="../#{s["scene"]}">{say(site, "in_unit_deck", unit=u["name"])}</a></p>\n\n'
           f'  <h2>{say(site, "what_it_shows")}</h2>\n  <p>{words(sc["summary"])}</p>\n\n'
           f'  <h2>{say(site, "every_step")}</h2>\n  <ol class="steps">\n']
    w = out.append
    for st in sc["steps"]:
        w(f'    <li>{words(st["t"])}</li>\n')
    w(f'  </ol>\n\n  <nav class="pager" aria-label="{say(site, "pager")}">\n')
    if i > 0:
        p = rows[i - 1]
        w(f'    <a class="prev" href="{pre}{p["route"]}"><span>{say(site, "previous")}</span>{e(p["scene"]["title"])}</a>\n')
    else:
        w('    <span></span>\n')
    if i < len(rows) - 1:
        n = rows[i + 1]
        w(f'    <a class="next" href="{pre}{n["route"]}"><span>{say(site, "next")}</span>{e(n["scene"]["title"])}</a>\n')
    w('  </nav>\n</main>\n')
    w(foot(site, pre))
    return "".join(out)


def pages(site, scenes):
    """Every page of the site, by its path under the site's root."""
    want = {"index.html": home(site, scenes), "deck.html": deck_page(site, scenes)}
    for u in site["units"]:
        want[f'{u["id"]}/index.html'] = deck_page(site, scenes, u["id"])
    for i, r in enumerate(order(site, scenes)):
        want[r["route"] + "index.html"] = route(site, scenes, i)
    return want


def main(argv):
    check = "--check" in argv
    site, scenes = load()
    base = ROOT / site["root"]
    want = {k: v.encode() for k, v in pages(site, scenes).items()}
    stale = [k for k, v in want.items() if not (base / k).is_file() or (base / k).read_bytes() != v]
    if check:
        if stale:
            raise SystemExit(f"site: out of date, run python3 tools/manim/sitepages.py: {stale}")
        print(f"site current: {len(scenes)} animations, {len(want)} pages")
        return
    for k in stale:
        (base / k).parent.mkdir(parents=True, exist_ok=True)
        (base / k).write_bytes(want[k])
    print(f"site written: {len(scenes)} animations, {len(stale)} pages changed")


if __name__ == "__main__":
    main(sys.argv[1:])
