The platformer A/B trial (EM-Q4). Paste everything below the line into claude,
started in the trial folder. Paste the same text into both arms, and steer both
the same way (or not at all).

---

Builder is already in this folder as builder/ (do not clone it). Use Builder
to constrain and direct your work as the game's co-designer and developer.
The goal is a page that anyone can open in a browser, so put running well in
the browser first.

Earlier projects built with Builder, to read for what works:
- Chumontillado: its movement (holding shift to crouch and slide, space to
  hop, air strafing). Its digest is refs/chumontillado.md.
- Ape Race: its vines (grab, swing, let go). Its digest is
  refs/ape-race.md.
List them under References in BRIEF.md, naming the digests. Read each project
through its digest, and open its code only where the digest names a file.

First, read Builder through its cards (python3 <project>/tools/ask.py
--start, then ask.py "question"; open no file under builder/, its CLAUDE.md
included, except where a card points) and write the design journal's opening
entry: how you will use Builder for this game, the rules you will hold to and
what holds each, and your questions as answer chips.

The description, word for word: "build a platformer based around the holding
shift and space movement of chumontillado plus ape race vines and b-hopping and
surfing inspired by super Mario 64"

Permissions, for BRIEF.md's Autonomy, word for word: "Do not deploy. Do not
push to any remote or create any repository. Do not use subagents. The plan is
approved in advance: take the default for every question, record each in the
journal, and keep building until the game is playable in the browser and
./scripts/check.sh passes, then hand off."
