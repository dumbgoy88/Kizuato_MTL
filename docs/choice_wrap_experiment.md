# Choice text wrapping experiment

The original PC-98 script has multi-line choice options. `tools/build_live_patch.py --choice-line-wrap` tests adding `B0` newlines *inside* a choice prompt or option's existing text run, keeping every English character, original commands, event bytes, and choice targets. It never adds a `B3` page wait to a choice. The option rendering, selection highlight, and cursor geometry have **not** been observed for these added lines in the native emulator, so this is a diagnostic copy, not the recommended player-test image.

The latest ignored experimental HDI is `build/choice-wrap-experiment-20261110-v6.hdi`; its scene PAK readback SHA-256 is `31e63a611b465b4888c9144beba8d1e09e306314a1631ebf3066ccbc8589f6ce`. It inserts **3,248/3,306** queued messages, leaves **15 actual Japanese text messages**, and keeps **43 punctuation-only original messages** unchanged. The recommended beta inserts 3,154 and leaves 109 actual Japanese text messages. All experimental edits passed the inferred 24-column/13-row *per-message* layout audit. The choice-wrap mode adds 139 choice newlines across 44 of 47 static choice groups. A group-level row estimate exceeded 13 rows for 12 choices; two already exceeded 13 in the original script under this estimate. Thus the estimate is a warning, not a measured choice-menu limit. Do not claim the additional English choices are visually usable without checking selection and all options in an emulator.

Rebuild with a new name:

```sh
python tools/build_live_patch.py --paginate --apostrophe-dot --preview-punctuation --split-long-words --choice-line-wrap --opening-choice-overlay --overrides examples/beta_opening_overrides.json --overrides examples/typewriter_overrides.json --overrides examples/kaede_conflict_overrides.json --overrides examples/azusa_shout_overrides.json --skip-static-layout-flags --name choice-wrap-new
```

When the user can test desktop input, compare one choice with an added newline to the original option on separate disposable HDIs. Check all visible options, highlight movement, selected branch, and return from the choice. Keep screenshots in ignored `build/`. Until then, use [beta_test.md](beta_test.md) for the recommended image.
