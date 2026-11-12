# Local beta test build

## Current recommended image

Use the disposable [focused-review beta HDI](../build/beta-20261110-focused-review.hdi), SHA-256 `ad64b4b4856afee8884017b50659aa837f1d76717a1785c459f33a799d290709`. It is ignored by Git and was made from the unchanged original. It inserts **3,154 of 3,306** queued messages, leaves **109 actual Japanese text messages**, and keeps **43 punctuation-only messages** in their original language-neutral form. Scenes `000`–`004`, including the first fresh-game choice and all three immediate branches, have English in every queued slot. This is a player-test image, not a release patch.

The image uses provisional typography: middle-dot apostrophes, periods for semicolons and clock colons, spaced dashes for explanatory colons, corner quotes for paired emphasis, ASCII letters for Latin accents, and the original game's wave-dash glyph for drawn-out sounds. Long cries can wrap within a word without deleting letters. `examples/beta_opening_overrides.json`, `examples/typewriter_overrides.json`, `examples/kaede_conflict_overrides.json`, and `examples/azusa_shout_overrides.json` are source-hash-checked explicit edits; the latter three preserve original timed text slots or resolve specific reviewed drafts. The first choice uses `examples/opening_en.json` because PLaMo misread one word as “Joe.”

Static checks passed: the scene PAK read back from the beta HDI with SHA-256 `37acdca18f5fe0a412242487eb1e90cf63faa6df09f8a28807296ab1a6f89ca6`; of 41 extracted installed files, only `MAX2_SCN.PAK` differs from the original; all 173 event blocks decode byte-identically; and the inferred 24-column/13-row audit flags no inserted text. These checks do **not** prove visible layout, choice highlight, added page waits, timing, or sound. The timing audit flags 2,904 inserted messages whose English may have moved across an original wait/effect command.

## Run it at the desktop

From the repository root, open `build/beta-20261110-focused-review.hdi` in Neko Project II Kai. The known local executable is `sdlnp21kai`; a direct launch is:

```sh
SDL_VIDEODRIVER=x11 XDG_CONFIG_HOME="$PWD/build/beta-emulator-config" sdlnp21kai "$PWD/build/beta-20261110-focused-review.hdi"
```

Start a new game. Read through the opening and check the first three-option choice: are all options visible and selectable, and does the next scene appear correctly? On separate fresh runs, test each option; the unchanged event bytes target scenes `002`, `003`, and `004` respectively. Check that an added page wait reveals the rest of its English passage. Note any cut-off text, odd punctuation, broken highlight, misplaced pause/effect, or new sound regression. Keep screenshots containing game art in ignored `build/`, and record the nearest line/choice and selected option. Stop if the image fails to boot or a choice cannot be selected. The original HDI is safe; build a new copy to reset beta save data.

The [choice-wrap experiment](choice_wrap_experiment.md) gets more English on screen but changes option line counts without emulator proof. Test the recommended image first.

## Rebuild exactly

With the ignored local extraction, manifest, PLaMo cache/model, and font research table present, use a fresh `--name`:

```sh
python tools/build_live_patch.py --paginate --apostrophe-dot --preview-punctuation --split-long-words --opening-choice-overlay --overrides examples/beta_opening_overrides.json --overrides examples/typewriter_overrides.json --overrides examples/kaede_conflict_overrides.json --overrides examples/azusa_shout_overrides.json --skip-static-layout-flags --name beta-new-copy
python tools/audit_layout.py work/messages.jsonl build/beta-new-copy-edits.json build/beta-new-copy-layout.json
python tools/audit_timing.py work/messages.jsonl build/beta-new-copy-edits.json build/beta-new-copy-timing.json
```

See [review findings](review_findings.md) and [STATUS.md](../STATUS.md) for remaining issues.
