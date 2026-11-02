# Saves kit

Progress that survives a reload and a deploy: the core owns a versioned save and a chain of migrations, the page keeps the core's text in the browser and offers it as a file, and a test loads a save written by every build that was ever deployed. Also a playtest file a friend can send back.

Use it when the brief has anything a player would be sorry to lose. Idle Game shipped without the old-save test, and an update reset a player's whole game ("wait why did my entire game get reset with this update? i lost everything"). The fix that held was this kit's shape: a save the build refuses is kept and offered back, and a save from every deployed build is loaded on every check.

## What it changes

| Default | Change | Where |
| --- | --- | --- |
| D17 (the page keeps nothing between visits) | `web/save/store.js` may use `localStorage`, for the text `save.rs` writes. No other page file may name browser storage. | `crates/core/tests/storage_fence.rs` replaces `no_storage.rs` |

Paste this row into the project's `BUILDER-SPEC.md` change table:

```markdown
| D17 | `web/save/store.js` keeps the core's save text in `localStorage` and offers it as a file; no other page file names browser storage | the brief keeps progress (kits/saves) | `crates/core/tests/storage_fence.rs`, `crates/core/tests/old_saves.rs`; SECOND-ORDER.md |
```

## Files

| Kit file | Copy to | What it is |
| --- | --- | --- |
| `crates/core/src/save.rs` | `crates/core/src/save.rs` | `Save`, `VERSION`, `DROPPED`, `load`, `store`, `migrate`; tests |
| `crates/core/src/playtest.rs` | `crates/core/src/playtest.rs` | counts of named events and first-reached ticks, as a file; a test that nothing else gets in |
| `crates/core/tests/old_saves.rs` | `crates/core/tests/old_saves.rs` | every save in `tests/saves/` loads; one from this version is there; no field is lost unsaid |
| `crates/core/tests/storage_fence.rs` | `crates/core/tests/storage_fence.rs` | replaces `no_storage.rs`: storage only in `web/save/store.js` |
| `web/save/store.js` | `web/save/store.js` | read, write, keep a refused save, save to a file, open a file |
| `tests/saves/` | `tests/saves/` | the example's two saves, one per version; replace with the project's own |
| `tools/playtest_readout.py` | `tools/playtest_readout.py` | playtest files to one Markdown table for the journal |

Add `pub mod save;` and `pub mod playtest;` to `crates/core/src/lib.rs`, and delete `crates/core/tests/no_storage.rs`. Add `tests/saves/**` to the core rule in `tests/tags.toml`.

## How the page uses it

The page asks the core what to do and does it; it never reads a save itself.

1. On load, the page passes `store.read()` to the core through `act`. The core calls `save::load` and answers with one of three things. It may start a new game (`Fresh`). It may continue the save (`Ready`). Or it may start a new game and tell the page to keep the refused text (`Refused`): the page calls `store.keepRefused(kept)`, and `ui()` shows the status key's string and a "Save the old file" button.
2. After each change worth keeping (the core says when, in `ui()`), the page calls `store.write(text)` with the text the core returns from `save::store`.
3. "Save to file" and "Open a file" call `store.saveFile` and `store.openFile`. An opened file goes through `save::load` like the browser's copy.
4. "Send a playtest file" saves the text of `Playtest::file()`. It holds counts and ticks only.

## Before each deploy

Write a save from the build being deployed into `tests/saves/` (`v<VERSION>.json`, or `v<VERSION>-<what it shows>.json`) and commit it. `old_saves.rs` fails until there is one for the current version, so a version bump cannot reach players untested. When a change to `Save` is needed:

1. Bump `VERSION`.
2. Add the step from the old version to `migrate`: it reads the old fields and writes the new ones.
3. If a field goes away or changes its value on purpose, list it in `DROPPED` with the version and the reason.
4. Run `cargo test`: every old save must still load, with no field lost unsaid.
5. Add a save from the new version to `tests/saves/`.

Never edit a file in `tests/saves/` by hand: each one stands for a player's real file.

## Playtest files

A friend presses "Send a playtest file" and sends what it saves. `python3 tools/playtest_readout.py files/*.json` prints one table, a row per file, for a *measured* or *your fixes* journal entry. The core ignores any event or milestone name not in `EVENTS` or `MILESTONES`, so the file can hold nothing the player typed. Balance from the agent's side comes from bot games, as a probe (`docs/checks.md`). Peter's Crabble keeps a table of headless games per change in `notes/playtests.md`, and the two together say what players did and what the rules allow.

## Required tests

Each one is in the kit, and `scripts/check-kits.sh` in the reference repository runs them inside a copy of the minimal example.

| Test | What it pins down |
| --- | --- |
| `a_save_reads_back_as_it_was_written` | store and load agree |
| `nothing_stored_is_a_new_game` | an empty store starts fresh |
| `a_version_one_save_moves_its_level_into_woodcutting` | the example migration |
| `a_save_this_build_cannot_use_is_refused_and_kept_word_for_word` | unreadable, newer, no step, unknown field: refused, text kept |
| `every_deployed_builds_save_still_loads` | the deploy gate |
| `a_save_from_this_version_is_kept_before_deploying` | a version bump needs a new saved file |
| `no_field_of_an_old_save_is_lost_or_changed_without_saying_so` | every field of an old save comes back with its value, or `DROPPED` says why not |
| `only_named_events_and_milestones_reach_the_file` | the playtest file holds counts and ticks only |
| `only_the_save_store_names_browser_storage` | the D17 fence |
