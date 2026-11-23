/* Request-lifecycle animation, after the ToyTalk journal's tab 9.
   FlowScene(root, scene, code) draws scene.nodes as boxes inside scene.zones,
   then plays one flow at a time: each step moves marks along paths of nodes
   (a request, a reply, a stream or an event, told apart by shape and colour),
   lights the pieces that work, shows the code that runs (or, for a proposed
   flow, the contract), and keeps a text list of every step.

   The author's engine from the SnapClass guide, carried into Builder as kits/flowscene
   with their approval (Manim Lab T8). Two changes from the original: every word the
   reader sees comes from <script type="application/json" id="flow-labels">, and
   <div data-flow="ID"> loads flows/ID.json by itself. It holds layout and timing
   numbers, so it belongs in a deck or journal, outside web/ (Builder D3). */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const labelsEl = document.getElementById("flow-labels");
  const L = labelsEl ? JSON.parse(labelsEl.textContent) : {};
  const KINDS = { req: "circle", res: "square", stream: "diamond", msg: "triangle" };
  function svgEl(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function htmlEl(tag, cls, parent, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function markShape(kind, parent, size) {
    const s = size || 7;
    if (kind === "res") return svgEl("rect", { x: -s, y: -s, width: 2 * s, height: 2 * s, class: "fx-m fx-res" }, parent);
    if (kind === "stream") return svgEl("polygon", { points: `0,${-s - 2} ${s + 2},0 0,${s + 2} ${-s - 2},0`, class: "fx-m fx-stream" }, parent);
    if (kind === "msg") return svgEl("polygon", { points: `0,${-s - 2} ${s + 2},${s} ${-s - 2},${s}`, class: "fx-m fx-msg" }, parent);
    return svgEl("circle", { r: s, class: "fx-m fx-req" }, parent);
  }

  function FlowScene(root, scene, code) {
    const W = scene.boxW || 150, H = scene.boxH || 44;
    const N = scene.nodes, VIA = scene.via || {};
    const flows = scene.flows;
    const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    let flow = flows[0], at = 0, playing = false, timer = null, anim = null;

    root.classList.add("fx");
    const pick = htmlEl("div", "fx-pick", root);
    pick.setAttribute("role", "tablist");
    pick.setAttribute("aria-label", scene.pickLabel || L.pick);
    const sum = htmlEl("p", "fx-sum", root);
    const stage = htmlEl("div", "fx-stage", root);
    const sceneBox = htmlEl("div", "fx-scene", stage);
    const svg = svgEl("svg", { viewBox: scene.viewBox || "0 0 1000 620", role: "img" }, sceneBox);
    svgEl("title", {}, svg).textContent = scene.title || L.picture;
    const panel = htmlEl("figure", "fx-code", stage);
    panel.setAttribute("aria-label", L.codePanel);
    const panelH = htmlEl("figcaption", "", panel);
    const panelP = htmlEl("pre", "", panel);
    const now = htmlEl("p", "fx-now", root);
    now.setAttribute("aria-live", "polite");
    const ctl = htmlEl("div", "fx-ctl", root);
    const bPrev = htmlEl("button", "", ctl, L.back); bPrev.type = "button"; bPrev.setAttribute("aria-label", L.backName);
    const bPlay = htmlEl("button", "fx-play", ctl, L.play); bPlay.type = "button";
    const bNext = htmlEl("button", "", ctl, L.next); bNext.type = "button"; bNext.setAttribute("aria-label", L.nextName);
    const bRestart = htmlEl("button", "", ctl, L.restart); bRestart.type = "button";
    const spLabel = htmlEl("label", "", ctl, L.speed + " ");
    const speed = htmlEl("select", "", spLabel);
    [["0.5", L.slow], ["1", L.normal], ["2", L.fast]].forEach(([v, t]) => {
      const o = htmlEl("option", "", speed, t); o.value = v; if (v === "1") o.selected = true;
    });
    const count = htmlEl("span", "fx-count", ctl);
    const key = htmlEl("ul", "fx-key", root);
    for (const k in KINDS) {
      const li = htmlEl("li", "", key);
      const s = svgEl("svg", { width: 22, height: 18, "aria-hidden": "true" }, li);
      const g = svgEl("g", { transform: "translate(11,9)" }, s);
      markShape(k, g, 5);
      li.appendChild(document.createTextNode(" " + L.kinds[k]));
    }
    const details = htmlEl("details", "fx-list", root);
    htmlEl("summary", "", details, L.everyStep);
    const steps = htmlEl("ol", "", details);

    // Zones, edges, nodes.
    const gZones = svgEl("g", {}, svg), gEdges = svgEl("g", {}, svg), gLive = svgEl("g", {}, svg);
    const gNodes = svgEl("g", {}, svg), gMarks = svgEl("g", {}, svg);
    (scene.zones || []).forEach(z => {
      svgEl("rect", { x: z.x, y: z.y, width: z.w, height: z.h, rx: 14, class: "fx-zone fx-zone-" + (z.tone || "a") }, gZones);
      const t = svgEl("text", { x: z.x + 12, y: z.y + 20, class: "fx-zlabel" }, gZones);
      t.textContent = z.label;
    });
    const box = {};
    for (const id in N) {
      const [x, y, label, kind] = N[id];
      const g = svgEl("g", { class: "fx-node fx-" + (kind || "svc"), "data-n": id }, gNodes);
      svgEl("rect", { x: x - W / 2, y: y - H / 2, width: W, height: H, rx: kind === "store" ? 16 : 7 }, g);
      const parts = String(label).split("\n");
      parts.forEach((p, i) => {
        const t = svgEl("text", { x, y: y + 5 + (i - (parts.length - 1) / 2) * 15, "text-anchor": "middle" }, g);
        t.textContent = p;
      });
      box[id] = g;
    }
    function border(a, toward) {
      const [x, y] = N[a], dx = toward[0] - x, dy = toward[1] - y;
      const s = Math.min(dx ? (W / 2) / Math.abs(dx) : Infinity, dy ? (H / 2) / Math.abs(dy) : Infinity);
      return [x + dx * s, y + dy * s];
    }
    function segment(a, b) {
      const fwd = VIA[a + ">" + b], back = VIA[b + ">" + a];
      const mid = fwd ? fwd.slice() : back ? back.slice().reverse() : [];
      if (!mid.length) return [border(a, N[b]), border(b, N[a])];
      return [border(a, mid[0]), ...mid, border(b, mid[mid.length - 1])];
    }
    function polyline(path) {
      let pts = [];
      for (let i = 0; i < path.length - 1; i++) {
        const s = segment(path[i], path[i + 1]);
        pts = pts.length ? pts.concat([N[path[i]].slice(0, 2)], s) : s;
      }
      return pts;
    }
    (scene.edges || []).forEach(([a, b, dashed]) => {
      svgEl("polyline", { points: segment(a, b).map(p => p.join(",")).join(" "), class: "fx-edge" + (dashed ? " fx-dash" : "") }, gEdges);
    });

    function showCode(step) {
      panelP.textContent = "";
      if (step.c && code && code[step.c]) {
        const c = code[step.c];
        const hl = step.hl ? (typeof step.hl[0] === "number" ? [step.hl] : step.hl) : [];
        const lit = n => hl.some(([a, b]) => n >= a && n <= b);
        panelH.textContent = c.lines.length ? c.file + ":" + c.first + "–" + (c.first + c.lines.length - 1) : c.file;
        let first = null;
        c.lines.forEach((line, i) => {
          const n = c.first + i, row = htmlEl("span", "fx-row" + (lit(n) ? " fx-lit" : ""), panelP);
          htmlEl("span", "fx-ln", row, String(n));
          row.appendChild(document.createTextNode(line + "\n"));
          if (lit(n) && first === null) first = row;
        });
        panelP.scrollTop = first ? Math.max(0, first.offsetTop - panelP.offsetTop - 24) : 0;
        panel.hidden = false;
      } else if (step.x) {
        panelH.textContent = step.x.h;
        step.x.body.split("\n").forEach(line => {
          const row = htmlEl("span", "fx-row", panelP);
          row.appendChild(document.createTextNode(line + "\n"));
        });
        panelP.scrollTop = 0;
        panel.hidden = false;
      } else {
        panelH.textContent = scene.noCode || L.noCode;
        panel.hidden = false;
      }
    }

    function clearMotion() {
      if (anim) cancelAnimationFrame(anim);
      anim = null;
      gMarks.textContent = "";
      gLive.textContent = "";
    }
    function light(step) {
      const on = new Set(step.work || []);
      (step.go || []).forEach(m => { on.add(m.path[0]); on.add(m.path[m.path.length - 1]); });
      for (const id in box) box[id].classList.toggle("fx-on", on.has(id));
    }
    function move(step, done) {
      clearMotion();
      const items = (step.go || []).map(m => {
        const pts = polyline(m.path);
        svgEl("polyline", { points: pts.map(p => p.join(",")).join(" "), class: "fx-live fx-live-" + m.kind }, gLive);
        const lens = [];
        let total = 0;
        for (let i = 1; i < pts.length; i++) {
          const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
          lens.push(d); total += d;
        }
        const g = svgEl("g", {}, gMarks);
        markShape(m.kind, g);
        return { pts, lens, total, g };
      });
      if (!items.length) { done(); return; }
      const place = (it, f) => {
        let d = f * it.total, i = 0;
        while (i < it.lens.length - 1 && d > it.lens[i]) { d -= it.lens[i]; i++; }
        const a = it.pts[i], b = it.pts[i + 1], r = it.lens[i] ? d / it.lens[i] : 1;
        it.g.setAttribute("transform", `translate(${a[0] + (b[0] - a[0]) * r},${a[1] + (b[1] - a[1]) * r})`);
      };
      if (reduce) { items.forEach(it => place(it, 1)); done(); return; }
      const longest = Math.max(...items.map(it => it.total));
      const dur = Math.max(700, longest * 2.2) / +speed.value;
      const t0 = performance.now();
      const tick = t => {
        const f = Math.min(1, (t - t0) / dur);
        items.forEach(it => place(it, f));
        if (f < 1) anim = requestAnimationFrame(tick); else { anim = null; done(); }
      };
      anim = requestAnimationFrame(tick);
    }

    function render() {
      const step = flow.steps[at];
      light(step);
      showCode(step);
      now.textContent = (at + 1) + ". " + step.t;
      count.textContent = L.count.replace("{n}", at + 1).replace("{of}", flow.steps.length);
      [...steps.children].forEach((li, i) => li.classList.toggle("fx-cur", i === at));
      [...steps.children].forEach((li, i) => li.toggleAttribute("aria-current", i === at));
      move(step, () => {
        if (!playing) return;
        clearTimeout(timer);
        const dwell = (900 + step.t.length * 28) / +speed.value;
        timer = setTimeout(() => {
          if (!playing) return;
          if (at < flow.steps.length - 1) { at++; render(); } else stop();
        }, dwell);
      });
    }
    function stop() { playing = false; clearTimeout(timer); bPlay.textContent = L.play; }
    function choose(f) {
      stop(); flow = f; at = 0;
      [...pick.children].forEach(b => b.setAttribute("aria-selected", String(b.dataset.f === f.id)));
      sum.textContent = f.sum;
      steps.textContent = "";
      f.steps.forEach((s, i) => {
        const li = htmlEl("li", "", steps);
        const b = htmlEl("button", "fx-jump", li, s.t);
        b.type = "button";
        b.addEventListener("click", () => { stop(); at = i; render(); });
      });
      render();
    }
    flows.forEach(f => {
      const b = htmlEl("button", "", pick, f.title);
      b.type = "button"; b.dataset.f = f.id; b.setAttribute("role", "tab");
      b.addEventListener("click", () => choose(f));
    });
    bPrev.addEventListener("click", () => { stop(); if (at > 0) { at--; render(); } });
    bNext.addEventListener("click", () => { stop(); if (at < flow.steps.length - 1) { at++; render(); } });
    bRestart.addEventListener("click", () => { stop(); at = 0; render(); });
    bPlay.addEventListener("click", () => {
      if (playing) { stop(); return; }
      if (at >= flow.steps.length - 1) at = 0;
      playing = true; bPlay.textContent = L.pause; render();
    });
    root.addEventListener("keydown", e => {
      if (e.target.closest("select,textarea,input")) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault(); e.stopPropagation();
        (e.key === "ArrowRight" ? bNext : bPrev).click();
      }
    });
    choose(flows.find(f => f.id === scene.start) || flows[0]);
    return { stop, choose: id => choose(flows.find(f => f.id === id) || flows[0]) };
  }
  window.FlowScene = FlowScene;

  // <div data-flow="ID"> loads flows/ID.json: the scene, with its code excerpts, if
  // any, under "code". The root's data-flow-base names the folder that holds flows/.
  document.querySelectorAll("[data-flow]").forEach(root => {
    const at = root.closest("[data-flow-base]");
    const pre = at ? at.dataset.flowBase : "";
    fetch(pre + "flows/" + root.dataset.flow + ".json")
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(scene => { root.flowScene = FlowScene(root, scene, scene.code || null); root.dataset.ready = "true"; })
      .catch(() => { root.textContent = L.failed; root.dataset.failed = "true"; });
  });
})();
