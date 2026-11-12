# Technical investigation

## Disk and files

All offsets and sizes below were inspected locally on 2026-11-09. The supplied Kizuato HDI is 11,145,216 bytes: a 4,096-byte header plus 11,141,120 bytes of disk sectors. Header little-endian values at offsets 0x08–0x1f are 4096 (header size), 11,141,120 (data size), 512 (sector size), 17 (sectors/track), 4 (heads), 320 (cylinders). The FAT12 volume begins at byte 38,912, where its boot sector contains `NEC  5.0`, `FAT12`, and a 0x55AA signature. The volume can be listed with `mdir -i 'Kizuato (J).hdi'@@38912 ::KIZUATO`.

The installed game uses `MAX2_SCN.PAK`, `MAX2_MUS.PAK`, `MAX2_CG0.PAK` through `MAX2_CG5.PAK`, `MAX2_SYS.PAK`, and `MAX2_ADV.EXE`. All `MAX2_*.PAK` start with a 16-byte label of the form `LEAFPACK:MAX2...`. The archive layout has now been verified on all nine supplied PAKs:

- At 0x10: a little-endian count plus 0x3f75. For `MAX2_SCN.PAK`, 0x4022 - 0x3f75 = 173.
- From 0x12: file data, each independently encoded by adding the repeating 13-byte key `6a d1 4b 13 58 7c f7 55 71 48 9f 3e b7`. The key bytes appear in `MAX2_ADV.EXE` immediately after `LEAFPACK`.
- At the end: count × 24-byte table, encoded with the same key reset at the table start. Each decoded row has an 8.3 name plus terminator, then little-endian offset, length, and next offset. Entries are contiguous.
- `tools/leafpack_pc98.py verify` decodes and rebuilds all nine archives byte-identically. For the scene archive it also decompresses both blocks in every one of the 173 entries.

The scene entry header uses 16-byte block offsets. The event and text blocks each start with a four-byte uncompressed length and use the LZS variant implemented in [XLVNS `leafpack.c`](https://github.com/catmirrors/xlvns/blob/master/leafpack.c). The [XLVNS scenario loader](https://github.com/catmirrors/xlvns/blob/master/LvnsFile.c) agrees with these offsets and the extracted text pointer table. Scene `000.SCN` yields 101 event bytes and 2,589 text bytes. Its first choice event is opcode 0x25 at event offset 0x54, with prompt message 24 and option messages 25 and 26. Its branch offsets are 0 and 4 bytes after the choice payload. Exact native PC-98 rendering remains to be tested.

The 173 scene filenames are `000.SCN`–`169.SCN` and `200.SCN`–`202.SCN`. `tools/scenes.py` exported 3,309 messages. Message pointers are little-endian 16-bit offsets from the start of the uncompressed text block; the first pointer equals `2 + 2 × message_count`. Every text block reproduced byte-identically from its messages. The literal-only LZS compressor reproduces the decompressed text and leaves the original compressed event block unchanged. One message, `201.SCN`/032, contains an unrecognized `0x26` command and is left opaque for later research.

`tools/event_graph.py` applies the analogous event pointer table (`count + 1` offsets) and checks every event command against the supplied archive revision. All 173 scenes and 519 blocks parse without unknown bytes; 47 choice commands and 243 scene-load commands occur. All conditional and choice skip targets land on command boundaries, and all scene-load targets exist. The nearby [XLVNS Kizuato interpreter](https://github.com/catmirrors/xlvns/blob/master/kizuato.c) helped identify `0x24` scene load, `0x25` choice, `0x41`/`0x42` conditions, `0x4b` flag set, `0x51` message, and `0x52` no-op. The supplied PC-98 bytes establish command boundaries; full flag and route semantics still need gameplay checks. The graph JSON is kept in ignored `work/`.

`tools/common_context.py` computes within-block dominators over both outcomes of each conditional and every choice branch. A prior `0x51` message is eligible as context only if it lies on every path to the later `0x51` message in that same block. Loads, endings, and opaque `0x23` stop traversal; choice text is excluded. The ignored map covers 3,112 displayed IDs, with nonempty context for 2,935. It is deliberately conservative and does not infer cross-scene route ancestry.

The external XLVNS `kizfont.tbl` is close to this game's character index but requires two apparent skipped positions after 0xD0 and 0xE3 to make the observed opening Japanese readable. This is an inferred alignment, not yet a verified full font mapping. Glyph codes below those positions include uppercase Latin and digits in the table; native PC-98 glyph appearance still needs emulator testing.

An edited HDI copy booted in local Neko Project II Kai with FM selected. The original Leaf title and background graphics appeared, and uppercase English glyphs from the original engine were readable in the opening narration and prompt. A 25-glyph English line wrapped its final period to the next line, so the current builder caps each translated text run at 24 glyphs. The current nine-message sample visually rendered its revised first passage as two clean lines. This is an observation for that text context only, not a proven choice-box limit. Both demo versions continued from `000.SCN` into `001.SCN`.

Fresh play takes `000.SCN`'s conditional load into `001.SCN` before its two-option choice. Scene `001.SCN` has a reachable three-option choice: prompt message 15, options 16–18. Its raw event payload is `25 0f 03 10 00 11 04 12 08`, followed by branch destinations `52 24 02 01`, `52 24 03 01`, and `52 24 04 01` (the `52` bytes are no-ops in XLVNS). All event blocks remain byte-identical in the edited archive. Native choice behavior has not yet been visually checked.

`tools/choice_probe.py` makes a disposable archive from the exact nine-message demo revision: it replaces only the preceding fifteen `51 xx` text-display commands in `001.SCN` with thirty `52` no-ops. Decompression confirms the choice and branch suffix, all text, and the other 172 scenes are unchanged. The resulting archive was verified after HDI reinsertion. It is a targeted layout/branch diagnostic, not a release patch or proof that the normal path reaches the choice. The probe booted to FM selection, but synthetic input was unreliable and no choice observation resulted.

The seven installer floppies start with `VFD1.00`; their contents have not been parsed.


## Required format proof

Before changing any script, record: text encoding, command table, choice target representation, pointer base and width, and length constraints. Archive and LZS extraction now pass an unchanged round trip. A successful insertion still requires a modified scene to boot and both choice paths to reach the expected targets.
