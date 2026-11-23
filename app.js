// The page draws what the core returns and decides nothing.
//
// The core describes the screen: the display, the keypad (with the keyboard
// keys that press each key), the animation's controls and the current step's
// glyphs. This file builds the DOM from that description. Each glyph keeps one
// SVG element for as long as the sum is on the stage; a new step moves it to
// the position the core gives, and a CSS transition makes the move, the way
// Manim's Transform does (CM-2). Every key and control goes back through
// `act`, the core's one door; the core keeps the step number (CM-7).
import init, { start, act } from "./pkg/tool_shim.js?v=c6883075f633";

const SVG = "http://www.w3.org/2000/svg";
const el = (id) => document.getElementById(id);
const make = (tag, text) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
};

let state = null;
let glossary = "";
let ui = null;
let timer = null;
let sceneKey = "";
const glyphs = new Map();
const keyButtons = new Map();

function call(fn, ...args) {
  return JSON.parse(fn(...args));
}

function send(name, value) {
  draw(call(act, JSON.stringify(state), glossary, name, value));
}

function buildKeypad(keys) {
  const pad = el("keypad");
  keys.forEach((k) => {
    const button = make("button", k.label);
    button.type = "button";
    button.id = "key-" + k.id;
    button.setAttribute("aria-label", k.aria);
    button.addEventListener("click", () => send(k.name, k.value));
    keyButtons.set(k.id, button);
    pad.append(button);
  });
}

// A pressed keyboard key presses the keypad key whose list names it.
function onKey(event) {
  if (!ui || event.ctrlKey || event.metaKey || event.altKey) return;
  const onButton = event.target instanceof HTMLButtonElement;
  if (onButton && (event.key === "Enter" || event.key === " ")) return;
  const k = ui.keys.find((key) => key.keys.includes(event.key));
  if (!k) return;
  event.preventDefault();
  send(k.name, k.value);
}

function place(node, g) {
  node.setAttribute("class", "g " + g.kind + " " + g.tone);
  node.style.transform = "translate(" + g.x + "px, " + g.y + "px)";
  if (g.kind === "rule" || g.kind === "box") {
    node.setAttribute("width", g.w);
    node.setAttribute("height", g.h);
  } else {
    node.textContent = g.text;
  }
}

function create(g) {
  const isText = g.kind === "digit" || g.kind === "small";
  const node = document.createElementNS(SVG, isText ? "text" : "rect");
  const start = g.from ? { ...g, x: g.from[0], y: g.from[1] } : g;
  place(node, start);
  node.classList.add("gone");
  return node;
}

function drawStage(view) {
  const svg = el("stage");
  el("stage-empty").hidden = !!view;
  svg.hidden = !view;
  if (!view) {
    svg.replaceChildren();
    glyphs.clear();
    sceneKey = "";
    el("words").textContent = "";
    el("count").textContent = "";
    return;
  }
  if (view.key !== sceneKey) {
    svg.replaceChildren();
    glyphs.clear();
    sceneKey = view.key;
  }
  svg.setAttribute("viewBox", "0 0 " + view.width + " " + view.height);
  const seen = new Set();
  const fresh = [];
  view.glyphs.forEach((g) => {
    seen.add(g.id);
    let node = glyphs.get(g.id);
    if (!node) {
      node = create(g);
      svg.append(node);
      glyphs.set(g.id, node);
      fresh.push([node, g]);
    } else {
      place(node, g);
    }
  });
  glyphs.forEach((node, id) => {
    if (!seen.has(id)) node.classList.add("gone");
  });
  // Read layout once so a new glyph starts from its first place, then move it.
  svg.getBoundingClientRect();
  fresh.forEach(([node, g]) => place(node, g));
  el("words").textContent = view.words;
  el("count").textContent = view.count;
  svg.dataset.step = view.step;
  svg.dataset.steps = view.steps;
}

function drawControls(controls) {
  const box = el("controls");
  box.replaceChildren(
    ...controls.map((c) => {
      const button = make("button", c.label);
      button.type = "button";
      button.id = "ctl-" + c.id;
      button.disabled = !c.enabled;
      button.addEventListener("click", () => send(c.name, ""));
      return button;
    }),
  );
}

function drawTerms(hints) {
  el("terms-list").replaceChildren(
    ...hints.flatMap((h) => {
      const term = make("dt", h.term);
      term.dataset.term = h.term;
      term.title = h.definition;
      return [term, make("dd", h.definition)];
    }),
  );
}

async function buildExamples() {
  const box = el("examples");
  box.append(make("h2", ui.examples_heading), make("p", ui.examples_intro));
  const grid = make("div");
  grid.className = "example-grid";
  ui.examples.forEach((ex) => {
    const part = make("section");
    const player = make("div");
    player.dataset.manim = ex.id;
    part.append(make("h3", ex.heading), player);
    grid.append(part);
  });
  box.append(grid);
  const labels = make("script", JSON.stringify(ui.player));
  labels.type = "application/json";
  labels.id = "manim-labels";
  document.body.append(labels);
  await import("./manim/player.js?v=c6883075f633");
}

function draw(result) {
  if (result.error) {
    el("message").textContent = result.error;
    return;
  }
  ui = result.ok;
  state = ui.state;
  document.title = ui.title;
  el("title").textContent = ui.title;
  el("intro").textContent = ui.intro;
  el("expr").textContent = ui.expr;
  el("value").textContent = ui.value;
  el("message").textContent = ui.message;
  el("stage-heading").textContent = ui.stage_heading;
  el("stage-empty").textContent = ui.stage_empty;
  if (!keyButtons.size) buildKeypad(ui.keys);
  drawControls(ui.controls);
  drawStage(ui.stage);
  document.body.dataset.playing = ui.playing;
  clearTimeout(timer);
  if (ui.playing) timer = setTimeout(() => send("step.tick", ""), ui.hold_ms);
}

async function main() {
  await init();
  const strings = await (await fetch("data/strings.json?v=c6883075f633")).text();
  const stage = await (await fetch("data/stage.json?v=c6883075f633")).text();
  glossary = await (await fetch("data/glossary.md?v=c6883075f633")).text();
  const first = call(start, strings, glossary, stage);
  draw(first);
  if (first.error) return;
  document.documentElement.style.setProperty("--move", ui.move_ms + "ms");
  el("terms-heading").textContent = ui.terms_heading;
  drawTerms(ui.hints);
  document.addEventListener("keydown", onKey);
  await buildExamples();
  document.body.dataset.ready = "true";
}

main();
