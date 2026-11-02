# Start in a folder

For a person who keeps their projects in folders of their own and starts a coding agent in a new, empty one. The agent clones Builder into that folder for reference, copies the template beside it, and builds there. This is the opening the author pasted, nearly word for word, to start Spins, Idle Game, Ravnica Digest, Formula Builder, CHUMWORLD and Chumworld Arena, and, with the role changed, the CIS 110 game lab. Stages 0–9, the same as [`start-from-description.md`](start-from-description.md); only the folder layout and the opening differ.

## What the person does

```bash
mkdir ~/Documents/MyGame && cd ~/Documents/MyGame
claude
```

Then paste the opening below with the four slots filled, and after it the description in your own words (or "the game is in BRIEF.md" if you wrote one already).

```text
Clone https://github.com/sgilson7/builder-setting into this folder as
builder/, then remove its .git. Use Builder to
constrain and direct your work as [ROLE: the game's co-designer and
developer | the tool's developer | an assignment's author]. The goal is a
page on GitHub Pages that anyone can open in a browser, so put running
well in the browser first.

Earlier projects built with Builder, to read for what works:
[REFERENCES: e.g. https://sgilson7.github.io/projects/ and the folders under
~/Documents; name the ones this project should borrow from, and what each
lends: "the lobby from Ape Race", "Lowballer's 2D style"]. List them under
References in BRIEF.md.

First, read Builder and write the design journal's opening entry: how you
will use Builder for this [game | tool], the rules you will hold to and what
holds each, and your questions as answer chips. Use [MODEL JOURNAL: e.g.
../ApeRaceMapMaking/ape-race-journal] as the model of a good journal.

[PERMISSIONS: e.g. "You may create a public repository named ____ and
deploy it to GitHub Pages when the checks pass." / "Do not deploy." /
"Do not use subagents."]
```

Each slot changes what the agent does:

| Slot | Goes to | Why it matters |
| --- | --- | --- |
| ROLE | the opening entry | "co-designer" asks the agent to propose and ask; "developer" asks it to build what is described |
| REFERENCES | `BRIEF.md`, References | the agent opens each one before planning, and `journal_check.py` fails until the opening entry says what it took from each. "In the style of X" works only when X's files are on disk |
| MODEL JOURNAL | the opening entry | the agent copies a journal's shape better than it follows a description of one |
| PERMISSIONS | `BRIEF.md`, Autonomy | written word for word as the Deploys and Subagents lines. Without a grant the agent does not deploy; without a named subagent allowance it works alone (D21) |

## What the agent does

```text
1. Clone Builder into this folder as builder/ and remove its .git; it stays
   as the reference (docs/, kits/, prompts/). Copy builder/template/ to a
   new folder beside it named after the project (lowercase, hyphens), run
   git init there, and work only there. Read that project's CLAUDE.md in
   full; its rules govern everything below. Start the journal from inside
   the project: python3 tools/journal/new_journal.py, which makes
   <name>-journal/ beside it. The folder then holds builder/, <name>/ and
   <name>-journal/, the layout Idle Game and ToyTalk ended up with.

2. Write BRIEF.md as start-from-description.md step 2 says, with the
   person's words verbatim. Put each reference under References, with
   where its files are and what it lends, and the permissions under
   Autonomy, word for word.

3. Open every reference. Read its journal if it has one, and the files the
   person pointed at. Write the opening entry: what Builder asks of you,
   what this project changes, what each reference lends and how you will
   use it, numbered rules with what holds each, the question prefix, where
   you stop. Put each question in the journal's decisions.json with a
   default and draw the chips (python3 tools/journal/decisions.py).
   Publish the journal if you can, with the db capability on claude.ai,
   and give the person the link.

4. Stop for the person's answers unless the brief approves the plan in
   advance. When the person says the answers are in the journal, read
   them, record them (decisions.py --answers), and write an agreed entry.

5. From here, follow start-from-description.md steps 5 to 8. Add a
   research entry before a design that leans on another game or a paper,
   mockups before code, an against entry once it is built, and rewrite
   Live now on every deploy.
```

## Why this opening works

Each part answers something an agent cannot know from the description alone. The role sets whether it proposes or builds as told. The references turn "make it look like Mage Tower Battle" into files it can open, and Peter's Crabble brief does the same ("the same graphical style from ape-race and Honey Hole … This is proven to be good"). The model journal gives it a shape to copy. The permissions decide in advance what would otherwise stop the work mid-session ("override the rule just this once and deploy live"). Asking for the Builder reading first puts the agent's understanding of the rules where the person can correct it before any code depends on it.
