# Translation and insertion conventions

These are project rules, not claims about the decoded Kizuato format.

## Records

When extraction is available, export one JSONL record per player-visible string with fields such as `id`, `source_ja`, `source_bytes_hex`, `archive`, `scene`, `source_offset`, `route`, `branch_path`, `kind` (`narration`, `dialogue`, or `choice`), `control_segments`, and `context_ids`. The ID must remain stable across translation revisions and identify the source location; duplicate Japanese sentences at different locations receive different IDs. Keep raw bytes and commands immutable.

Translation output belongs in separate JSONL records keyed by ID. Store `english`, `review_state`, `model_id`, `prompt_revision`, and source hash. Engine wrapping and encoding belong in a separate build stage; never insert model output directly into game data.

## Context and glossary

Send nearby Japanese lines and reviewed previous translations from the same branch or its common prefix. Mark speaker, scene, and route when verified. Do not blend context from mutually exclusive choices. Keep glossary entries with Japanese term, approved English spelling, notes, and review status. Do not infer a character's name from later routes when an earlier line is intentionally ambiguous.

Use natural, concise English that preserves viewpoint, tense, uncertainty, and character voice. Keep proper names consistent. Record ambiguous source readings for human review. Avoid silently adding information absent from the Japanese.

## Validation gates

Before insertion, reject missing or duplicated IDs; changed source hashes; altered command/control bytes; missing choice branches or changed targets; unencodable glyphs; scene/archive length violations; and overflow against text-box measurements obtained in the actual engine. An estimated character count is only a warning until font metrics and wrapping rules are measured. Test both branches in the emulator.
