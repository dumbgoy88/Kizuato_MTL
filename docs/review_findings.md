# Translation review — 2026-11-10/11

## All-English diagnostic draft audit

The completed route-aware v2 manifest has **3,307** translatable IDs; all have cached drafts. The ignored `build/all-english-diagnostic-20261111-v2.hdi` inserts English for every translatable ID, leaves 43 original punctuation-only messages and two command-only messages, and has zero Japanese-letter messages after archive readback. This is a content-coverage result, not approval of translation quality or emulator fit. [All-English test instructions](all_english_demo.md) give the exact artifact and risks.

`tools/audit_drafts.py` flagged one old “Joe” misreading (covered by the explicit opening-choice overlay), three extreme expansions (two earlier shout overrides and one new runaway replaced by a source-hash-checked first-pass draft), and eight missing choice numbers in raw model output (the builder restores each number from its Japanese source). Eight shared-key conflicts are resolved by explicit output hashes for the diagnostic. Fifty raw drafts contain Japanese-block characters; inspection found only middle dots and drawl marks (`・`, `ー`, `ッ`), which the formatter handles. The rebuilt archive independently scans with **zero Japanese letters or ideographs**. Two glossary checks lacked literal name spellings in model output; these remain editorial leads, not proof of mistranslation.

The inferred layout audit flags five later choice messages and the timing audit flags 2,922 messages with possible phrase movement across original commands. The full audit proves no nonspace character loss in 3,248 model-derived edits; 16 manual/overlay edits remain separate editorial text. Neither audit proves that pages fit or choices work in the native emulator.

This review used the SHA-256-pinned PC-98 extraction and the completed local PLaMo cache. It records mechanical and targeted editorial findings; it does **not** approve 3,306 translations. Detailed source-linked records remain ignored under `work/`, and beta reports remain ignored under `build/`.

## Earlier mixed-language insertion update

After targeted source review, the recommended beta inserts **3,154** messages and leaves **109 actual Japanese text messages**. Another **43 punctuation-only originals** remain unchanged because they convey no Japanese words. The separate choice-wrap diagnostic inserts 3,248 and leaves **15 actual Japanese text messages**, but its added option lines are unverified in the emulator. The 15 comprise eight conflicting cached outputs in later scenes, six choice texts that exceed the inferred page budget, and one sensitive passage with malformed model quotation. They are not auto-selected, shortened, or pushed into the beta. Four source-aligned typewriter edits and two identical non-explicit shout passages were fitted without deleting letters; four duplicate-scene drafts were resolved by source review. The game's own `■` redaction glyph is reused where the Japanese source contains it.

In the earlier expanded-opening beta, 3,120 messages were inserted and 186 were classified as Japanese fallbacks before the punctuation-only audit. Scenes `000`–`004` already had English in every queued slot. That snapshot's inferred layout audit flagged zero inserted text and its timing audit flagged 2,872 for possible pause/effect boundary review. These historical counts describe a static preview, not verified emulator behavior or approved prose.

The opt-in punctuation preview initially added 135 semicolon→period substitutions, 52 explanatory colon→spaced dash substitutions, 61 paired emphasis→corner quote substitutions, and 55 tilde→native wave-dash substitutions. Later preview rules also handle clock colons, Latin accents, and Japanese drawl marks left in English drafts. Each affected ID is marked in the ignored build report. These substitutions may alter voice or punctuation nuance and need editorial review. Within-word line breaks keep every letter of overlong cries/onomatopoeia. A compact font or measured choice layout and manual editorial work remain necessary.

## Draft content audit

`tools/audit_drafts.py` reviewed all 3,306 translatable IDs against `config/glossary.json` and the source-linked snapshot. It flagged 53 drafts containing Japanese characters, seven choice drafts lacking a visible option number, two extreme length expansions, and one clear reading error: `001.SCN/text/017` treats a display-split Japanese word for “joke” as the name “Joe.” The first-choice beta uses the explicit English example instead. No draft lacked one of the seven glossary spellings when its corresponding Japanese term appeared; this is a narrow string check, not proof that names and relationships are translated correctly. Twelve IDs have conflicting cached outputs across identical prompts; the preview leaves them Japanese. No model-token artifacts or replacement characters were found by this audit.

The opening spot check found natural but uneven English. `001.SCN/text/000` interprets a sudden movement as an audible gasp; `001.SCN/text/002` has an awkward literal phrase for the narrator's mind waking; and `001.SCN/text/017` has the confirmed “Joe” error noted above. These are editorial review examples, not a comprehensive quality score. The 1996 walkthrough is used for plot context only, never as translation source. Route-safe context currently stops at the same event block, so later scene openings may lack useful prior context.

## Earlier insertion and layout audit (superseded beta)

The beta inserts 2,795 full drafts, leaves 511 Japanese, and uses three explicit first-choice overlays. All 19 IDs in `001.SCN` are English; early `002.SCN` and `003.SCN` are also entirely English. The opening `000.SCN` still has four Japanese fallbacks, including a repeated word sequence whose 21 original text slots should not be collapsed. Of 148 unique choice prompt/option IDs in the checked event graph, 46 are English and 102 remain Japanese. Forty-nine scenes have every queued message inserted, and two have none.

`tools/audit_layout.py` found no beta edit beyond its inferred 24-column/13-row budget after the builder excluded ten lines with a `B9` choice indentation risk. This uses the related XLVNS renderer's `B9` interpretation and the observed 24-glyph line; native PC-98 layout remains to be measured. `tools/audit_timing.py` flags 2,553 of the 2,795 beta edits because original non-newline commands occur between text runs. In the related interpreter, `B2` waits for a key. The English formatter currently redistributes words across those boundaries, so a byte-identical event stream does not guarantee the original pacing. Segment-aware drafting and layout are required for a release candidate.

The 511 Japanese fallbacks are dominated by unsupported punctuation (especially semicolon, colon, asterisk, and tilde), choices too long for their original run slots, single words wider than 24 glyphs, and drafts with too few words to fill all original text slots. Final English needs a proper apostrophe and compact font or a reviewed punctuation/line strategy. Do not silently shorten or cut text to raise coverage.

## Reproduce the audits

```sh
bash tools/review_now.sh
python tools/audit_drafts.py work/review-<current-snapshot>.jsonl config/glossary.json work/draft-audit-new.json
python tools/audit_layout.py work/messages.jsonl build/beta-20261110-reviewed-edits.json build/beta-layout-new.json
python tools/audit_timing.py work/messages.jsonl build/beta-20261110-reviewed-edits.json build/beta-timing-new.json
```

Use the actual snapshot path printed by `review_now.sh`. Outputs are ignored and include IDs or source-linked material for local review. The next substantive translation pass should preserve each original pause/effect segment, add safe route context only after proving reachability, and review each character's voice and the later-revealed clues at the point they appear.
