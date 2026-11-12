# Route-aware PLaMo rerun

The second pass has completed its cached draft run. It uses the **original PC-98 scene archive**, not walkthrough prose, as translation source. The [1996 guide](https://lastcharles.com/pc-18/walkthrough/pc-18/kizuato) confirms a route completion order but does not establish every binary flag state; the [Renewal Chizuru](https://shisnap.iza-yoi.net/game/pc/kizuato_r/kizuatoR_chizuru.htm) and [Azusa](https://shisnap.iza-yoi.net/game/pc/kizuato_r/kizuatoR_azusa.htm) charts differ in unlock details and are kept out of prompts. The spoiler index remains in [story_reference.md](story_reference.md). The current ignored v2 manifest adds the formerly opaque `201.SCN/text/032`, for **3,307** translatable IDs and two command-only exclusions.

## What a prompt receives

`tools/route_context.py` walks all parsed command paths from the fresh-game `000.SCN` entry. It explores both sides of flag conditions and every choice, follows scene loads, and admits an earlier Japanese message only when it occurs on **every modeled path** to the current message. It stops at commands whose continuation is unknown. Choice options are separate graph nodes, so one option never enters a sibling option's context; branch messages disappear from mandatory context after a merge. Unreachable passages fall back to same-block proven context only.

The manifest selects up to three recent mandatory Japanese messages plus up to two mandatory choice options as route breadcrumbs. It includes only glossary terms present in the current text or selected context. `config/route_facts.json` adds eight short, PC-98-anchored character and clue notes, each only after its source passage must already have occurred and a relevant Japanese term appears. The notes preserve narrator uncertainty. No guide paragraph, Renewal-only unlock claim, premature later revelation, or untranslated command byte is sent to PLaMo.

This is a **static common-path approximation**, not full route-state simulation. Flag writes are parsed but their save-state initialization and bonus entry behavior are not decoded. The guide's route labels and ending order are editorial references for later review, not automatic prompt facts. The parser maps 3,244 fresh-game-reachable message IDs; 49 IDs in `201.SCN`/`202.SCN` have no proven display path past an opaque `0x23` command, and 16 other IDs use same-block fallback. In both bonus scenes, the supplied event block begins `30 00 60 38 00 00 23 1e` before its text displays; the nearby XLVNS `kizuato.c` dispatch does not define `0x23`. Its native PC-98 behavior remains unverified. The 2002 Renewal charts must never fill that gap by assumption.

## Prepare, run, watch, stop, resume

Run from the repository root. Preparation rechecks the source archive, rebuilds the event and context maps, creates a new ignored manifest, and runs branch and source-hash checks. It makes no model calls:

```sh
bash tools/full_run.sh prepare-route
```

Try a few new prompts first, then start the whole foreground run:

```sh
bash tools/full_run.sh route --max-new 5
bash tools/full_run.sh route
```

Each ID and its result prints live. The log is ignored at `work/plamo-route-live.log`; from another terminal use `tail -f work/plamo-route-live.log`. To stop **after the current request**:

```sh
bash tools/full_run.sh stop
```

Run `bash tools/full_run.sh route` again to resume. The same ignored `work/full_draft_cache.jsonl` is shared with the first pass; exact unchanged prompts reuse successful outputs, while changed prompts get new cache keys. Failed requests are retried, successful calls are flushed before the next ID. `bash tools/review_now.sh route` writes an ignored source-linked snapshot while the run is active; it does not call the model.

## Verified preparation checkpoint

The v2 preparation parsed 173 scenes, 519 event blocks, 47 choices, and 243 loads from the hash-pinned original. The manifest queues 3,307 translatable IDs. The verifier found 3,251 with selected prior context, 2,448 with cross-scene context or choice breadcrumbs, and 2,679 with a relevant glossary entry. It checked all 47 choice groups for sibling leakage and the three distinct first-choice branches. The longest generated prompt with the current facts was 1,933 characters. The completed read-only review snapshot found 3,307 cached drafts; eight shared-key conflicts require explicit selection. A disposable all-English test copy and its static audit are described in [all_english_demo.md](all_english_demo.md).

These counts describe **prompt construction**, not translation quality. Read the resulting drafts against the source and [review findings](review_findings.md). The patch builder accepts `--manifest work/route_draft_manifest-v2.json --context-map work/route_context-v1.json --facts config/route_facts.json --cache work/full_draft_cache.jsonl`; the all-English diagnostic also passes explicit hash-only draft selections and preview typography options. Do not treat a built image as choice or audio verified without emulator checks.
