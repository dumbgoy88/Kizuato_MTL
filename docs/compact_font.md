# Compact English renderer feasibility

The user requires complete, readable English. A font bitmap alone is insufficient: the original PC-98 game visibly advances a full-width cell per English glyph, and the 25th glyph wrapped in the opening test. The related [XLVNS text renderer](https://github.com/catmirrors/xlvns/blob/master/LvnsText.c) also advances its cursor one cell per glyph. This port is useful research evidence, **not** proof of the original `MAX2_ADV.EXE` implementation. The original Kizuato font `KNJ_ALL.KCD` is inside `MAX2_SYS.PAK`; its compressed glyph records have a 2,083-entry offset table. A font replacement needs Kizuato-specific glyph and renderer verification.

## Capacity estimate

`python tools/font_feasibility.py work/messages.jsonl work/full_draft_cache.jsonl work/event_graph.json` prints only counts; it is safe to run while PLaMo appends to the cache. On a snapshot of **331 drafts**, the raw character-count upper bounds were:

| Columns per line | Fits within original text-run count | Fits within one 13-row page | Choice prompts/options fitting original runs |
| ---: | ---: | ---: | ---: |
| 24 (current observation) | 27/331 | 120/331 | 12/37 |
| 36 (proposed compact) | 154/331 | 265/331 | 24/37 |
| 48 (proposed half width) | 291/331 | 326/331 | 34/37 |

These are **optimistic counts**: they ignore word boundaries, punctuation glyphs, `B9` choice indentation, original page commands, and translation quality. They show why a 48-column English renderer is worth investigating, while also showing that a smaller font alone will not fit every message or choice. Native pagination and reviewed wording remain necessary.

## Native patch route

1. Decode and re-encode Kizuato's own `KNJ_ALL.KCD`, proving a byte-identical round trip before editing glyphs. Design a legible approximately half-width Latin alphabet and an apostrophe while retaining Japanese glyphs needed by menus and any untranslated script.
2. Disassemble the **hash-pinned** `MAX2_ADV.EXE`. Locate text glyph drawing, horizontal cursor advance, line-wrap comparison, text history redraw, and choice highlight/indent logic. Patch Latin-code advances to the new pixel width and keep the original path for Japanese and graphics. Document every changed instruction and its expected original bytes.
3. Build a disposable HDI with modified EXE, SYS font archive, and a short diagnostic script containing a 48-character line, apostrophe, and multi-option choice. Verify source hashes, archive readback, visible glyphs, wrapping, selection/highlight, save/load, and original music/effects in the emulator.
4. Parameterize the script formatter for the **measured** compact width, retain native page breaks for remaining long passages, and rerun a full overflow/choice audit. Never truncate English. Distribute only a patch/reproducible transformation, not game assets.

No compact font or EXE patch exists yet. Changing only the KCD glyph shapes would make letters smaller **inside the same spacing** and would not achieve the estimated 36/48-column capacity. The already implemented script pagination is a separate route to full-length passages; the opening probe displayed a 13-row English page without clipping, but its inserted page-advance command has not yet been visually reached.
