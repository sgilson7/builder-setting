/* The Manim player (Manim Lab PLAN.md P10): plays a scene's rendered clips one step at a time
   with the deck's own controls. Markup: <div data-manim="ID"></div>; it reads
   scenes/ID.json for the words and timings and media/ID/manifest.json for the files.

   Play plays the current step's clip, holds its last frame for the step's hold_ms,
   then goes on; Pause stops; back and forward play that step's clip, as FlowScene
   replays a step's move; Restart goes to step one. Under prefers-reduced-motion it
   shows each step's final frame and never plays a clip. Light or dark follows
   prefers-color-scheme, or <html data-theme>. The labels come from the page's
   <script type="application/json" id="manim-labels">.

   It holds no number but 0 and 1 (BUILDER-SPEC D3): every time and size comes from
   the scene file or the manifest. */
(function () {
  "use strict";
  const labels = JSON.parse(document.getElementById("manim-labels").textContent);
  const reduceQ = matchMedia("(prefers-reduced-motion: reduce)");
  const darkQ = matchMedia("(prefers-color-scheme: dark)");

  function mode() {
    const forced = document.documentElement.dataset.theme;
    if (forced === "light" || forced === "dark") return forced;
    return darkQ.matches ? "dark" : "light";
  }
  function el(tag, cls, parent, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    parent.appendChild(e);
    return e;
  }
  function button(parent, text, cls) {
    const b = el("button", "mp-btn" + (cls ? " " + cls : ""), parent, text);
    b.type = "button";
    return b;
  }
  /* A step's words, with `backticks` set as code; never parsed as HTML. */
  function words(parent, text) {
    let code = false;
    text.split("`").forEach(part => {
      if (part) {
        if (code) el("code", "", parent, part);
        else parent.appendChild(document.createTextNode(part));
      }
      code = !code;
    });
  }
  function fill(template, values) {
    return template.replace(/\{(\w+)\}/g, (all, key) => String(values[key]));
  }

  function Player(root, scene, manifest, base) {
    const steps = scene.steps, last = steps.length - 1;
    let at = 0, playing = false, timer = null, turn = 0;

    root.classList.add("mp");
    const stage = el("div", "mp-stage", root);
    stage.style.aspectRatio = scene.width + " / " + scene.height;
    const pic = el("img", "mp-pic", stage);
    pic.alt = scene.title;
    const vid = el("video", "mp-vid", stage);
    vid.muted = true;
    vid.playsInline = true;
    vid.preload = "auto";
    vid.disablePictureInPicture = true;
    vid.setAttribute("aria-hidden", "true");
    vid.hidden = true;
    const now = el("p", "mp-now", root);
    now.setAttribute("aria-live", "polite");
    const ctl = el("div", "mp-ctl", root);
    const bPrev = button(ctl, labels.back);
    bPrev.setAttribute("aria-label", labels.backName);
    const bPlay = button(ctl, labels.play, "mp-solid");
    const bNext = button(ctl, labels.next);
    bNext.setAttribute("aria-label", labels.nextName);
    const bRestart = button(ctl, labels.restart);
    const count = el("span", "mp-count", ctl);
    const details = el("details", "mp-list", root);
    el("summary", "", details, labels.everyStep);
    const list = el("ol", "", details);
    steps.forEach((s, i) => {
      const b = button(el("li", "", list), "", "mp-jump");
      words(b, s.t);
      b.addEventListener("click", () => { stop(); show(i, true); });
    });

    const row = i => manifest.clips[mode()][i];
    const png = i => base + row(i).png;
    const clip = i => base + row(i).clip;

    function say(i) {
      now.textContent = "";
      el("b", "", now, (i + 1) + ". ");
      words(now, steps[i].t);
      count.textContent = fill(labels.count, { n: i + 1, of: steps.length });
      [...list.children].forEach((li, k) => {
        li.classList.toggle("mp-cur", k === i);
        li.toggleAttribute("aria-current", k === i);
      });
    }
    /* Show step i: play its clip (animate) or its final frame, then hold if playing. */
    function show(i, animate) {
      const mine = ++turn;
      clearTimeout(timer);
      at = i;
      root.dataset.step = String(i + 1);
      say(i);
      if (!animate || reduceQ.matches) {
        vid.pause();
        vid.removeAttribute("src");
        vid.hidden = true;
        pic.src = png(i);
        hold(mine);
        return;
      }
      vid.hidden = true;
      if (i > 0) pic.src = png(i - 1);
      vid.onloadeddata = () => { if (mine === turn) vid.hidden = false; };
      vid.onended = () => {
        if (mine !== turn) return;
        pic.src = png(i);
        hold(mine);
      };
      vid.src = clip(i);
      const started = vid.play();
      if (started) started.catch(() => {
        if (mine !== turn) return;
        vid.hidden = true;
        pic.src = png(i);
        hold(mine);
      });
    }
    function hold(mine) {
      if (!playing || mine !== turn) return;
      timer = setTimeout(() => {
        if (!playing || mine !== turn) return;
        if (at < last) show(at + 1, true);
        else stop();
      }, steps[at].hold_ms);
    }
    function stop() {
      playing = false;
      clearTimeout(timer);
      vid.pause();
      bPlay.textContent = labels.play;
      root.dataset.playing = "false";
    }

    bPrev.addEventListener("click", () => { stop(); if (at > 0) show(at - 1, true); });
    bNext.addEventListener("click", () => { stop(); if (at < last) show(at + 1, true); });
    bRestart.addEventListener("click", () => { stop(); show(0, true); });
    bPlay.addEventListener("click", () => {
      if (playing) { stop(); return; }
      playing = true;
      bPlay.textContent = labels.pause;
      root.dataset.playing = "true";
      show(at >= last ? 0 : at, true);
    });
    root.addEventListener("keydown", e => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      e.preventDefault();
      e.stopPropagation();
      (e.key === "ArrowRight" ? bNext : bPrev).click();
    });
    const again = () => { stop(); show(at, false); };
    darkQ.addEventListener("change", again);
    reduceQ.addEventListener("change", again);
    new MutationObserver(again).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    root.dataset.steps = String(steps.length);
    show(0, false);
    return { stop };
  }

  const players = [];
  document.querySelectorAll("[data-manim]").forEach(root => {
    const id = root.dataset.manim, base = "media/" + id + "/";
    Promise.all([fetch("scenes/" + id + ".json"), fetch(base + "manifest.json")])
      .then(rs => Promise.all(rs.map(r => {
        if (!r.ok) throw new Error(r.url);
        return r.json();
      })))
      .then(([scene, manifest]) => { players.push(Player(root, scene, manifest, base)); })
      .catch(() => { root.textContent = labels.failed; root.dataset.failed = "true"; });
  });
  window.ManimPlayers = { stopAll: () => players.forEach(p => p.stop()) };
})();
