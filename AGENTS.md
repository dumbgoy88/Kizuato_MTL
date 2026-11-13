# Kizuato PC-98 English patch project rules

Read `STATUS.md` before changing code or making claims. Keep verified observations separate from hypotheses. Update `STATUS.md` at each meaningful milestone and commit useful changes locally. Never push.

## Preservation

- Treat supplied Kizuato images and private reference material as read-only references. Work only in ignored `work/`, `build/`, or other copies.
- Do not commit game images, raw extracted game data, patched executables, screenshots containing game art, translation model weights, credentials, or save files. The user-requested text-only Japanese message export at `translations/japanese_source.jsonl` is the sole exception; it must contain no raw bytes or commands. Check `git status` and `git check-ignore` before each commit.
- Preserve original PC-98 graphics, FM music, effects, choices, timing, and branch behavior. Every engine or script change needs a reason and a regression check.
- Record SHA-256 hashes for input images and important extracted files. Refuse to patch an unexpected input revision.
- Distribute a patch or reproducible transformation, never a complete game image or binary copyrighted payload. Keep the Japanese text export separate from installer payloads.

## Engineering

- First prove byte-identical extraction and rebuild of each format where practical. Verify every technique against Kizuato before using it.
- Keep stable string IDs based on archive, scene, and source location. Store the Japanese source and original control bytes separately from English text.
- Keep translation drafts separate from line wrapping and engine encoding. Never send control bytes or branch commands to a translation model.
- Restrict context and translation history to a known branch or common prefix. Maintain one glossary with reviewed terms.
- Read `docs/story_reference.md` for internal spoilers, but never send that file wholesale to a model. Release only facts known at the current message and supported on its verified route. The Japanese game script, not walkthrough wording, is the translation source.
- Codex manages extraction, context, model calls, validation, and patch building. Use the selected local model for translation samples by default. A separate GPT API backend requires explicit configuration and must never activate implicitly.
- Cache successful model outputs by source, context, glossary, model, and prompt revision. Retry failures without repeating successful calls.
- Validate duplicate and missing IDs, source drift, damaged commands, branch targets, encoded length, and measured text-box overflow before insertion.
- A claim that a passage or choice works requires an emulator run with both paths checked and FM music and effects observed. Record emulator version/settings and evidence in `STATUS.md`.

## Immediate objective

Get one English Kizuato passage and a following choice working in a PC-98 emulator. Current blocker and exact next actions are in `STATUS.md`.
