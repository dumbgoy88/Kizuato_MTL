# Whole-corpus local draft run

Checkpoint on 2026-11-10: the first local pass has finished. Its cache contains 3,308 rows; the regenerated manifest queues 3,306 translatable IDs, all drafted. Two failed IDs are command-only and need no translation. Twelve IDs have conflicting outputs for shared prompts. The patch builder leaves conflicts untouched. See `STATUS.md` for the current build coverage. Re-running the command below reuses successful responses.

This is a **first-pass translation queue**, not a finished English patch. It covers 3,306 of 3,309 extracted message IDs. `201.SCN/text/032` has an unknown `0x26` command; `202.SCN/text/005` and `/007` are command-only with no source text. All three are deliberately skipped. The input archive, extracted messages, and each queued source hash are checked before the manifest is written. Completed model calls are cached in ignored `work/full_draft_cache.jsonl`; a resumed run skips matching prompt/model results.

The current context is conservative: at most three earlier Japanese messages proven to precede the current message in the same event block, relevant terms from `config/glossary.json`, and the one PC-98-anchored story fact in `config/story_facts.json` when its anchor appears in that prior context. The 1996 walkthrough and Renewal charts are indexed in `docs/story_reference.md` but **not** automatically poured into prompts. Cross-scene flags and route reachability are not yet sufficiently understood to release route-specific spoilers safely. This limits translation quality, especially at scene starts; review those drafts with the story reference before insertion.

From the repository root, with the user's existing model drive mounted and the compatible `work/llama-build/bin/llama-server` build present:

```sh
bash tools/full_run.sh run --max-new 5
```

Watch those five fresh outputs and the ignored `work/plamo-full-live.log`. The command runs the server locally on `127.0.0.1`, prints each completed ID and draft, and exits cleanly. To continue through the entire remaining queue, run:

```sh
bash tools/full_run.sh run
```

The run stays in the foreground. To stop after the active request, use a second terminal:

```sh
bash tools/full_run.sh stop
```

While it runs, `bash tools/review_now.sh` takes a read-only snapshot of the current cache and prints coverage and issue counts. The ignored JSONL snapshot includes each stable ID, Japanese source, original command bytes, English draft, and QA flags. `missing_draft` means the model has not reached that ID. `needs_manual_wrapping` uses the observed 24-glyph line limit as a warning; it does not know the final text-box layout. `needs_case_conversion` marks lowercase letters because the current encoder accepts uppercase Latin only. `needs_glyph_or_punctuation_review` identifies characters outside the encoder even after uppercasing. These flags help triage human review; they do not judge translation quality. Review wording, names, voice, ambiguity, and spoiler timing against `docs/story_reference.md` and the PC-98 source before creating `text_runs` edits for `tools/scenes.py apply`.

Ctrl+C in the run terminal stops immediately. Repeat `bash tools/full_run.sh run` to resume. The script removes the old stop file on restart. Successful responses are flushed and synced before the next ID; errors are recorded and retried on the next run. `--max-new N` counts only cache misses. To watch from another terminal, use `tail -f work/plamo-full-live.log`. Generated logs, cache, and manifest stay in ignored `work/`. This CPU build was the one confirmed to load PLaMo 3; Vulkan remains unavailable in the current local build.

If derived files need rebuilding, first follow `README.md` to extract `MAX2_SCN.PAK` and `work/messages.jsonl`, then run:

```sh
python tools/event_graph.py work/original-extract/KIZUATO/MAX2_SCN.PAK work/event_graph.json
python tools/common_context.py work/event_graph.json work/common_context.json
python tools/build_batch.py work/messages.jsonl work/original-extract/KIZUATO/MAX2_SCN.PAK work/common_context.json config/glossary.json work/full_draft_manifest-new.json
```

The builder refuses to overwrite an existing manifest; use a new filename when revising the glossary or context. The runner cache key includes the exact prompt, model hash, token limit, and prompt revision, so a changed glossary/context produces fresh calls. The wrapper uses `work/full_draft_manifest.json`; replace that ignored file deliberately after reviewing a new manifest. Do not copy model drafts straight into engine text: source commands, layout, branch targets, encoded length, and glyph fit still need validation and emulator checks. The current English demo and first reachable choice are not yet fully verified in the emulator.
