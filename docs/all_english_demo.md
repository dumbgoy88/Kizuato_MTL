# All-English continuation probe

The user’s native emulator screenshots proved that v2/v3 are **unsafe for play**: the 13th text row clips, and a `B3` inserted inside a message skips later words. Static no-loss checks on those builds did not establish visible completeness. Do not continue v2/v3 saves.

## Current test copy

`build/all-english-diagnostic-20261111-v6.hdi` is an ignored disposable HDI, SHA-256 `ba0e0aca114925dde277ef3ad3b9695623fcf2d1557e3a9cc77e15cbea6ecc6a`. Its installed scene PAK SHA-256 is `b5a64890f9ffca8e7c02625696c866629d5e1f2b78c0540e7a86c3a1b4389249`. The original `Kizuato (J).hdi` remains SHA-256 `783adfa48bf5b8efcb9ae681e726f3c6180e8cac2d2bc568a5953aa32b992d04`.

Start a fresh test copy from the project folder:

```sh
bash tools/launch_all_english_demo.sh
```

The launcher checks the v6 hash, copies it to an ignored playtest HDI, and starts Neko Project II Kai. Select FM audio and begin a new game. At opening `000.SCN/text/003`, confirm that the page turns before “MY LIPS FORMED THE SHAPE,” then displays “OF WORDS…” and the rest before the next message. Try Space if Enter does not advance. This page continuation has **not** yet been observed on v6.

## What v6 changes and what was checked

The initial English insertion still contains 3,264 edited messages, 43 original punctuation-only messages, and no Japanese-letter fallbacks. `tools/split_pages.py` turns inserted mid-message page markers into 3,493 real continuation/prelude messages for 2,566 referenced source messages. It adds `0x51` continuation calls after ordinary messages and prelude calls before ten long choice prompts, then relocates conditional/choice branch skips. The independent `tools/audit_split_pages.py` checked all 173 scenes and 519 event blocks, reconstructed every split message byte-for-byte, and found no mid-message `B3` in directly referenced scenes. Text and event pointer tables round-trip; the replacement PAK read back from the v6 HDI.

Native page continuation, choice selection/highlighting, effects timing, and full-route behavior still need gameplay checks. Twelve unreferenced bonus messages in `201.SCN` retain 17 mid-message page markers because the native meaning of nearby opcode `0x23` is unknown. The independent 24-column/12-row audit finds all 47 combined choice groups within the static limit; native selection and highlighting remain unverified. The timing audit flags 2,922 messages where translated wording may move across original waits or effects. V6 is an **emulator probe**, not a verified complete patch.

## Rebuild

Use a new name each time; these tools refuse to overwrite existing outputs:

```sh
bash tools/rebuild_split_demo.sh my-new-probe
```

The wrapper builds the source-hash-checked English archive, runs its source/text audits, converts pages into real messages, independently audits event branches and reconstructed pages, and installs the PAK into a new copy of the hash-pinned original HDI. All generated images, archives, extracted text, reports, screenshots, and saves stay ignored by Git. Never distribute a complete game image.

