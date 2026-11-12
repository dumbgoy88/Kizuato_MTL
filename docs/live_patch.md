# Make a playable preview from the current PLaMo cache

From the repository root, run this **while PLaMo is running or after it stops**:

```sh
python tools/build_live_patch.py
```

It snapshots the successful, exact-prompt PLaMo cache entries, checks the source archive and original HDI hashes, and creates new ignored files under `build/`: an edits JSON, a rebuilt `MAX2_SCN.PAK`, a report JSON, and a **new HDI copy**. It never modifies `Kizuato (J).hdi`, the live cache, or the model. Run the same command later to make another copy with more completed translations; each default name has a timestamp. Boot the HDI path printed by the command in your PC-98 emulator.

The default uses the observed 24-glyph text-run limit. Every inserted message keeps its complete English wording, its original number of text runs, and all original commands. If the draft cannot fit, uses a glyph the current encoder cannot render, contains an unresolved apostrophe, or has not finished yet, that message remains Japanese. The report lists the exact reason per stable ID. Choices with a visible number retain the same number. Event blocks and branch targets are checked unchanged by `tools/scenes.py`; `tools/hdi_copy.py` verifies the PAK readback on the new image.

For a **disposable layout experiment**, you may allow longer runs:

```sh
python tools/build_live_patch.py --max-run-glyphs 72
```

This still never cuts words, but it exceeds the only observed 24-glyph line behavior. Text may wrap off-screen, cover choices, or require extra keypresses. Treat the result as a probe, not a release build. A smaller English font or a verified engine text-box change would require separate research and emulator testing.

An experimental paginator keeps each English line at 24 glyphs and adds native line/page commands when needed: `python tools/build_live_patch.py --paginate`. It does **not** paginate choice prompts or options. `--apostrophe-dot` is an optional preview-only glyph substitution for unsupported apostrophes; it is not final English typography. See [pagination.md](pagination.md) for the evidence, limits, and emulator test plan.

For the current mixed-language beta, add `--opening-choice-overlay --skip-static-layout-flags`. The first flag uses the three provisional choice edits in `examples/opening_en.json`; the second keeps ten lines with inferred `B9` indentation overflow in Japanese. The exact command and artifact hash are in [beta_test.md](beta_test.md). These flags do not certify overall translation quality or timing.

The expanded beta additionally uses `--preview-punctuation --split-long-words --overrides examples/beta_opening_overrides.json`. Punctuation substitutions are explicit, provisional, and listed per ID in the ignored report. Long words can wrap across native line/page commands without deleting a character. Explicit overrides require matching source hashes and original text-run counts. See [beta_test.md](beta_test.md) for the current build and its remaining 186 Japanese fallbacks.

Before treating any bulk preview as pacing-correct, run `python tools/audit_timing.py work/messages.jsonl build/<name>-edits.json build/<name>-timing.json`. The current whole-message formatter can move English across original wait, effect, and presentation commands between text runs even when their bytes and order are preserved. The audit reports those IDs for segment-level translation or review.

The tool does not judge wording or translate failures automatically. It expands a small set of unambiguous contractions, changes paired ASCII quotation marks to the engine's available corner quotes, and uses the native minus glyph for dashes. Other unsupported punctuation is left for review. `bash tools/review_now.sh` gives a source-linked review snapshot. To include an overlong passage in a final patch, rewrite it without losing meaning, place it in explicit `text_runs`, and validate it with `tools/scenes.py apply` and the emulator. The PLaMo cache is a draft source, not an approved translation.
