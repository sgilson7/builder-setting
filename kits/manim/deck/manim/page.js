/* A site's theme choice, kept from page to page in localStorage under the key on
   <body data-theme-key>. Runs before player.js and deck.js. On a deck page deck.js
   also sets the theme on change; this only remembers it. Without storage the choice
   lasts one page. From Manim Lab's CSC 226 site. Holds no number but 0 and 1. */
(function () {
  "use strict";
  const key = document.body.dataset.themeKey;
  const pick = document.getElementById("nav-theme");
  let kept = null;
  try { kept = key ? localStorage.getItem(key) : null; } catch (err) { kept = null; }
  if (kept === "light" || kept === "dark") {
    document.documentElement.dataset.theme = kept;
    if (pick) pick.value = kept;
  }
  if (!pick || !key) return;
  pick.addEventListener("change", () => {
    if (pick.value === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = pick.value;
    try {
      if (pick.value === "auto") localStorage.removeItem(key);
      else localStorage.setItem(key, pick.value);
    } catch (err) { /* the choice lasts this page */ }
  });
})();
