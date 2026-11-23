/* Slides for a deck of Manim players, after the MerryQuery deck's slide script (the
   author's own deck, carried into Builder with their approval, Manim Lab T8): one
   section of #deck shown at a time, the hash names it, the arrow keys and the bottom
   bar move between them, and moving stops every player. Also the theme picker, which
   sets <html data-theme>. Holds no number but 0 and 1. */
(function () {
  "use strict";
  const slides = [...document.querySelectorAll("#deck > section")];
  const pick = document.getElementById("nav-pick");
  const count = document.getElementById("nav-count");
  slides.forEach((s, k) => {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = (k + 1) + ". " + s.dataset.title;
    pick.appendChild(o);
  });
  let cur = 0;
  function show(k, push) {
    if (k < 0 || k > slides.length - 1) return;
    cur = k;
    slides.forEach((s, j) => s.classList.toggle("cur", j === cur));
    count.textContent = (cur + 1) + " / " + slides.length;
    pick.value = slides[cur].id;
    if (window.ManimPlayers) window.ManimPlayers.stopAll();
    if (push !== false && location.hash !== "#" + slides[cur].id) history.replaceState(null, "", "#" + slides[cur].id);
    window.scrollTo(0, 0);
  }
  function fromHash() {
    const k = slides.findIndex(s => "#" + s.id === location.hash);
    show(k < 0 ? 0 : k, false);
  }
  document.getElementById("nav-prev").addEventListener("click", () => show(cur - 1));
  document.getElementById("nav-next").addEventListener("click", () => show(cur + 1));
  pick.addEventListener("change", () => show(slides.findIndex(s => s.id === pick.value)));
  document.addEventListener("keydown", e => {
    if (e.defaultPrevented || e.target.closest("select, input, textarea")) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); show(cur + 1); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); show(cur - 1); }
  });
  addEventListener("hashchange", fromHash);
  fromHash();

  const theme = document.getElementById("nav-theme");
  theme.addEventListener("change", () => {
    if (theme.value === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme.value;
  });
})();
