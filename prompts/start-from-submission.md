# Start from a student submission

Use this procedure when a team of students designed a game in the [office-intake kit](../kits/office-intake/)'s templates and you want to build it. You unzip the team's folder, start a coding agent there, and give it a short prompt. The agent copies the submission into a new Builder project, starts the design journal, builds the game, and publishes it if your prompt allows. Stages 0–9.

## What you do

1. Download the team's shared folder from OneDrive as a `.zip` file, and unzip it.
2. Start a coding agent inside the unzipped folder.
3. Give it a prompt like this one:

   ```text
   This folder is a CIS 110 team's game design submission. Follow Builder's
   prompts/start-from-submission.md from https://github.com/sgilson7/builder-setting.
   You may create a public repository named cis110-team04-lava-lanes and
   publish it on my GitHub Pages once the checks pass.
   ```

Leave out the last sentence if you want to read the build before anything is public.

## What the agent does

```text
1. Get Builder. Clone https://github.com/sgilson7/builder-setting next to the
   submission folder, unless a clone is already there.

2. Make the project. Copy builder-setting/template/ to a sibling directory
   named after the game (lowercase, hyphens, for example
   cis110-team04-lava-lanes), run git init there, and read its CLAUDE.md in
   full. Its rules govern everything below.

3. Run the intake:
     python3 ../builder-setting/kits/office-intake/tools/intake/intake.py <submission folder> <project>
   If it stops because a student's name would be written, stop too. Tell the
   person which file holds the name, and do not edit the team's files.
   Otherwise, read INTAKE.md.

4. Start the journal with python3 tools/journal/new_journal.py, and write
   its opening entry (kind reading) as tools/journal/ENTRIES.md says. Add a
   "brief" entry: the team's design document is the description; show where
   each heading and sheet lands, and list everything INTAKE.md reports as
   missing or to look at.

5. Fill the rest of BRIEF.md from the team's words. The Scope heading's
   "Must have" list is "Done means". Everything the team did not decide is
   yours to decide: record each choice in SECOND-ORDER.md and continue.
   The plan is approved in advance for a submission. Write the autonomy
   paragraph from the person's prompt, word for word for any grant to
   publish, and record the grant in DECISIONS.md.

6. Build with tests, as CLAUDE.md says. The Rules sheet's rows are the
   hand-worked cases: each becomes a core test whose expected value comes
   from the team's "Expected result" column. Values in data/game.json stay
   the team's; a value the game needs that the team did not give is a
   notebook row. A glossary meaning that states a number becomes a
   {placeholder} the core fills.

7. Use the pictures. The team's slide pictures in the journal's
   img/reference/ are what they expect the game to look like. Take
   screenshots of the running build and put them beside the team's pictures
   in a "screenshots" journal entry.

8. Run ./scripts/check.sh. If the person's prompt grants publishing to a
   named repository, create it, push, run ./scripts/publish.sh, and run the
   browser check against the live address. Credit the game to the team
   number and the game's name. Do not add students' names anywhere: not in
   the repository, the page, the commit messages or the journal.

9. Answer the TRIAGE.md rows the intake wrote from the team's Changes sheet
   only if the person asks; they are the team's requests from the prototype
   round. Write HANDOFF.md and a "ready for you" journal entry, and tell the
   person what to try first.
```

## What the person still owns

You own whether the game matches what the team meant, the licences in `LICENSES.md`, and the decision to publish. The intake keeps names it knows about out of the project. It can't recognize a nickname or a first name on its own, so read `BRIEF.md` and the page before you publish.
