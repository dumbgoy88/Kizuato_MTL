# Japanese source and English script edits

[japanese_source.jsonl](japanese_source.jsonl) contains the decoded Japanese text of all 3,309 message records from the supplied original PC-98 scene archive. Each line has a stable ID, a SHA-256 hash of the original encoded message, and text only. It omits original control bytes, event commands, fonts, images, and audio. Two source records have no visible text. The current font-table decoding has been checked on representative passages but not every glyph in native play; flag suspected transcription errors by ID.

[english_edits.json](english_edits.json) is the complete project-authored English edit set used by the v7 beta candidate. It has 3,264 stable message IDs, each with the English text runs and a SHA-256 hash of the matching original message. The installer checks those hashes against a clean, owned Kizuato HDI before applying anything.

The JSON is readable and contains no Japanese source text, game image, font, music, or event-command bytes. `\n` marks a line break and `\f` a page advance in the English layout. The `text_runs` arrays preserve the engine's text-run boundaries; they are not separate story lines. Five hand-reviewed opening records omit the optional `format` field.

The files align on `id` and `source_sha256`. Forty-five original messages that are neutral, punctuation-only, or command-only are unchanged by the English edit set. Choices and branch commands remain in the original game data and are checked during installation. See [STATUS.md](../STATUS.md) for the current native test limits. This is an AI-assisted draft that still needs editorial and route review, including adult scenes.

For a new revision, edit the English records, review the changed source IDs and layout, then update the pinned edit and output hashes only after a full rebuild and emulator checks. The Japanese text export is an explicit user-requested exception to the project's no-extracted-assets rule; do not add raw game bytes or other copyrighted game assets here.
