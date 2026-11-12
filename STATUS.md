# Status — public snapshot, 2026-11-11

## Verified

- The supplied PC-98 Kizuato scene archive extracts and rebuilds byte-identically when unchanged. The source HDI and scene PAK are SHA-256 pinned in the tools.
- The v6 English edit set has 3,264 edited messages and no Japanese-letter fallbacks in its audited scene archive. Pagination uses real continuation messages and relocated event branches. The independent static audit reconstructed 2,566 split messages byte-for-byte and found all 47 choice groups within an estimated 24-column/12-row layout.
- A separate beta installer ZIP contains English edit instructions and project-authored tools, not a game image or rebuilt archive. Its self-contained Python installer was tested on the exact clean source HDI; readback found only `KIZUATO/MAX2_SCN.PAK` changed among 45 installed files.
- Neko Project II Kai displayed English opening narration on a v6 image with FM selected. A player reported the pagination looked fixed.

## Current milestone and limitations

The shareable v6 beta is ready for route-by-route player testing. A complete native playthrough, all choice paths, timing, effects, and save/load remain unverified. Twelve bonus-scene messages have no direct event reference and still need engine research. Static layout checks are evidence of capacity, not proof of native rendering.

## Next steps

1. Run each route with a reproducible input script and video; capture choice checkpoints and stop on mismatches.
2. Review reported missing/clipped text, branch errors, timing, and translation quality by stable message ID.
3. Rebuild and retest a new version from the hash-pinned source. Keep game images and beta payloads out of Git.
