# Public handoff

Read `AGENTS.md` and `STATUS.md` before changing code. The working project has verified extraction/rebuild, a hash-checked v6 English patch builder, and a separate beta installer package. Generated game images, model weights, draft caches, and screenshots are intentionally absent from this repository. Never push game data.

The next engineering milestone is unattended route playback with video capture and optional OCR, followed by tester-reported fixes. Verify native page continuation, choice branches, save/load, sound, and effects per route. The static audit covers 47 choice groups but does not prove emulator behavior. Keep all generated data in ignored `build/` or `work/` and commit useful tools and documentation locally.
