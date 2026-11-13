# Faster patch testing

The full OCR-driven route recorder is a final integration check. It takes many
minutes per route and can stop on artwork, a blinking cursor, or emulator
timing. Use smaller tests first.

1. Parse the original and rebuilt PAKs and compare every scene's packed,
   event, and decoded-text lengths:

   ```sh
   python tools/audit_scene_capacity.py \
     work/original-extract/KIZUATO/MAX2_SCN.PAK \
     build/all-english-diagnostic-20261111-v6.PAK \
     --output build/scene-capacity-v6.json
   ```

   The 32 KiB threshold is a diagnostic comparison, **not an established
   engine limit**. A direct-load test of v6 `034.SCN` failed with decoded
   text below 32 KiB. The report also compares each rebuilt size with the
   largest original size. v6 has 18 scenes crossing 32 KiB and 81 exceeding
   at least one original maximum. Both counts are risk indicators, not a
   verified engine acceptance rule.

2. For a suspected scene-load fault, make a disposable archive that redirects
   the new-game event to that scene. The source archive is hash pinned, only
   `000.SCN`'s event is changed, and all text stays intact. Example for v6:

   ```sh
   python tools/scene_jump_probe.py \
     build/all-english-diagnostic-20261111-v6.PAK \
     build/jump-016-v6.PAK \
     --expected-sha256 b5a64890f9ffca8e7c02625696c866629d5e1f2b78c0540e7a86c3a1b4389249 \
     --scene 16
   python tools/hdi_copy.py \
     build/all-english-diagnostic-20261111-v6.hdi \
     build/jump-016-v6.hdi build/jump-016-v6.PAK KIZUATO/MAX2_SCN.PAK \
     --expected-sha256 ba0e0aca114925dde277ef3ad3b9695623fcf2d1557e3a9cc77e15cbea6ecc6a
   ```

   Make the same probe from the pinned original PAK and HDI for an A/B boot.
   A direct jump is a diagnostic shortcut: prior route flags, graphics setup,
   and gameplay context may differ. A failure in the shortcut alone does not
   prove the release fails; a pass does not prove the whole route works.

3. Once static checks and targeted scene boots pass, run the guarded route
   recorder on a clean HDI copy. Review branch destinations, text, audio,
   effects, and the ending. Keep recordings and diagnostic HDIs in ignored
   `build/`; never publish them.

## Confirmed direct-load observations

The same isolated `sdlnp21kai` setup loaded the original `016.SCN` probe and
displayed Japanese story text. The v6 `016.SCN` probe displayed the game's
Japanese memory-allocation error naming `*MES DATA` and `pk:016 SCN`. v6
`100.SCN` and `034.SCN` probes showed the same error naming their respective
scene files. The requested allocation values, interpreted as 16-byte
paragraphs, equal each scene's decoded text size rounded upward. This confirms
the rebuilt data exhausts an engine allocation path in these direct boots;
the exact allocation rule and safe scene budget remain to be determined.

The v7 builder now uses the verified LZS2 compressor in its normal text and
pagination stages. Independent decoding found no event or text changes from
v6 across all 173 scenes. The separate `tools/recompress_scene_archive.py`
remains useful for diagnostics. Compression alone does not fix every memory
failure: direct boots of compressed `016.SCN` and `034.SCN` failed, while
`055.SCN` loaded English text. Long scenes need splitting without dropping
text or changing branches. Verify the finished patch with a normal route
replay; a direct jump cannot validate route state.

`tools/shard_linear_scene.py` is a **diagnostic one-scene prototype** for
v6 `016.SCN`. It preserves all 100 message payloads and the original choice
destinations, splitting the linear pre-choice calls into `016.SCN` and a new
`203.SCN`. Direct-load probes of both corrected shards boot and display their
expected English openings. `tools/transition_probe.py` shortens a disposable
copy of `016.SCN` to its final text call and the original load command. In a
native emulator test, one Return then displayed the first `203.SCN` message.
This checks the load handoff quickly. The full unshortened scene, choices, and
later gameplay still need integration testing. Do not use either probe as a
general sharder or publish its HDI output.

`tools/shard_main_scenes.py` generalizes the verified linear-prefix pattern
and audits reconstruction of every original message and event command. Its
first 16,000-byte pass split 55 main-story scenes into 66 added scenes; the
largest resulting main-story text block is 15,998 bytes. It leaves `201.SCN`
as a reported exception because bonus messages use dynamic references. The
239-scene output still needs emulator checks before it can replace the beta.

The [NP2 Kai project](https://github.com/AZO234/NP2kai) documents standalone
state save/load support. A state may speed repeated checks within **one exact
HDI build**, but this project has not verified state creation, restoration, or
safe reuse across rebuilt images. Do not treat an old state as proof for a new
patch.
