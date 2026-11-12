# Review the remaining Japanese text without a playthrough

The diagnostic choice-wrap build leaves 15 actual Japanese text IDs. Generate the ignored local review page from the exact build report, extracted source, cached PLaMo output, and source-linked draft snapshot:

```sh
python tools/review_remaining.py
```

Open `build/review-remaining.html` in a browser. The page lists all 15 stable IDs and why each stayed Japanese: six inferred choice-page layout failures, eight conflicting PLaMo cache outputs, and one malformed quotation in a sensitive passage. It shows Japanese source and draft candidates for the other 14; the sensitive passage body is hidden in the page. The generator checks the source archive revision, pending count, unique IDs, source hashes, and cached output source IDs. It sends no text to any model and never changes a game image.

This is a **script wording queue**, not a view of the native screen. Six choice entries need an emulator layout and cursor/selection check; editing their wording alone cannot prove they fit. The eight conflicting outputs need a human choice against the Japanese and story context. The sensitive entry needs separate appropriate review. All entries are from the **diagnostic** choice-wrap build. The recommended beta still has 109 actual Japanese text IDs, so this page does not describe its complete fallback set.

There is no verified arbitrary scene jump yet. The existing `tools/choice_probe.py` fast-forwards only the first choice by replacing known earlier display commands with no-ops in a disposable copy. Directly jumping to later scenes could omit required route flags, images, audio setup, or earlier event commands. An emulator save made at a known location is the safest later-screen shortcut once the route has been reached normally. Keep such saves under ignored `build/`; do not share or commit them.
