#!/usr/bin/env python3
"""Independently audit a disposable all-English scene archive and its drafts.

Checks every message against the original, preserves original command bytes,
rejects Japanese letters in the rebuilt archive, and proves the formatter did
not drop any nonspace character from selected model drafts. This is a static
check; it cannot prove visible layout, audio, choice selection, or meaning.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from build_live_patch import MODEL, normalize, preview_punctuation
from compare_local import PROMPT_REVISION, load_messages, prompt_for, sha256
from leafpack_pc98 import decode_scene, read_archive
from review_drafts import cache_successes, read_cache
from scenes import font_table, messages, segments

JP_LETTERS = re.compile("[\u3040-\u30fa\u30fc-\u30ff\u3400-\u9fff]")


def without_space(value: str) -> str:
    return "".join(char for char in value if not char.isspace())


def command_delta(original: list[str], patched: list[str]) -> list[str]:
    """Consume original commands in order; only B0/B3 may be new."""
    old_at = 0
    inserted = []
    for command in patched:
        if old_at < len(original) and command == original[old_at]:
            old_at += 1
        elif command in {"b0", "b3"}:
            inserted.append(command)
        else:
            raise ValueError(f"unexpected new/changed command: {command}")
    if old_at != len(original):
        raise ValueError("an original command was removed")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("patched", type=Path)
    parser.add_argument("messages", type=Path)
    parser.add_argument("edits", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("context", type=Path)
    parser.add_argument("facts", type=Path)
    parser.add_argument("cache", type=Path)
    parser.add_argument("selections", type=Path)
    parser.add_argument("font_table", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("audit output exists; use a fresh filename")
    records = load_messages(args.messages)
    edits = {item["id"]: item for item in json.loads(args.edits.read_text())}
    report = json.loads(args.report.read_text())
    statuses = {item["id"]: item for item in report["messages"]}
    manifest = json.loads(args.manifest.read_text())
    context = json.loads(args.context.read_text())
    facts = json.loads(args.facts.read_text())["facts"]
    cache = read_cache(args.cache)
    selections = {row["id"]: row for row in json.loads(args.selections.read_text())}
    if (len(edits) != len(set(edits)) or len(statuses) != len(report["messages"]) or
            len(selections) != len(json.loads(args.selections.read_text()))):
        raise ValueError("duplicate IDs")
    if (report["source_archive_sha256"] != sha256(args.original) or
            report["manifest_sha256"] != sha256(args.manifest) or
            report["context_map_sha256"] != sha256(args.context) or
            report["facts_sha256"] != sha256(args.facts)):
        raise ValueError("input provenance changed since build")
    if manifest["context_scope"] != context["scope"]:
        raise ValueError("manifest/context scope mismatch")
    source_archive = read_archive(args.original)
    patched_archive = read_archive(args.patched)
    if [entry.name for entry in source_archive.entries] != [entry.name for entry in patched_archive.entries]:
        raise ValueError("scene archive order changed")
    table = font_table(args.font_table)
    original_raw = {}
    patched_raw = {}
    for source_entry, patched_entry in zip(source_archive.entries, patched_archive.entries):
        source_event, source_text = decode_scene(source_entry)
        patched_event, patched_text = decode_scene(patched_entry)
        if source_event != patched_event:
            raise ValueError(f"event block changed: {source_entry.name}")
        source_items, patched_items = messages(source_text), messages(patched_text)
        if len(source_items) != len(patched_items):
            raise ValueError(f"message count changed: {source_entry.name}")
        for index, (source, patched) in enumerate(zip(source_items, patched_items)):
            ident = f"MAX2_SCN/{source_entry.name}/text/{index:03d}"
            if hashlib.sha256(source).hexdigest() != records[ident]["raw_sha256"]:
                raise ValueError(f"source hash changed: {ident}")
            original_raw[ident], patched_raw[ident] = source, patched
    if set(original_raw) != set(records):
        raise ValueError("missing or duplicate extracted IDs")
    if set(edits) != {ident for ident, item in statuses.items() if item["state"] == "inserted"}:
        raise ValueError("edit/report ID mismatch")
    japanese_rows = []
    inserted_commands: collections.Counter[str] = collections.Counter()
    for ident, patched in patched_raw.items():
        parsed = segments(patched, table)
        displayed = "".join(part["text"] for part in parsed if part["kind"] == "text")
        if JP_LETTERS.search(displayed):
            japanese_rows.append(ident)
        if ident not in edits:
            if patched != original_raw[ident]:
                raise ValueError(f"unlisted message changed: {ident}")
            continue
        source_parts = segments(original_raw[ident], table)
        old_commands = [part["raw"] for part in source_parts if part["kind"] == "command"]
        new_commands = [part["raw"] for part in parsed if part["kind"] == "command"]
        inserted_commands.update(command_delta(old_commands, new_commands))
    if japanese_rows:
        raise ValueError(f"Japanese letters remain in {len(japanese_rows)} messages: {japanese_rows[:5]}")
    model_hash = sha256(MODEL)
    allowed = {key: set(value) for key, value in context["context_ids"].items()}
    checked_drafts = 0
    manual_overrides = 0
    for row in manifest["samples"]:
        ident = row["id"]
        if ident not in edits:
            continue
        if statuses[ident].get("source") in {"explicit_manual_override", "provisional_opening_choice_overlay"}:
            manual_overrides += 1
            continue
        prompt = prompt_for(row, records, manifest["glossary"], {}, allowed, facts)
        key = hashlib.sha256(json.dumps({"revision": PROMPT_REVISION, "model_sha256": model_hash,
                                         "max_tokens": row.get("max_tokens", 512), "prompt": prompt},
                                        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if ident in selections:
            selection = selections[ident]
            if selection["source_sha256"] != records[ident]["raw_sha256"]:
                raise ValueError(f"selected source drift: {ident}")
            key = selection["cache_key"]
            matching = [item["translation"] for item in cache.get(key, [])
                        if item.get("status") == "ok" and
                        hashlib.sha256(item["translation"].encode()).hexdigest() == selection["translation_sha256"]]
            if not matching:
                raise ValueError(f"selected output missing: {ident}")
            draft = matching[-1]
        else:
            successful, invalid = cache_successes(cache.get(key, []), records)
            if invalid or len({item["translation"] for item in successful}) != 1:
                raise ValueError(f"cached draft invalid/ambiguous: {ident}")
            draft = successful[-1]["translation"]
        value, _ = preview_punctuation(draft) if report["preview_punctuation_experimental"] else (draft, [])
        value = normalize(value, records[ident]["source"], report["apostrophe_dot_experimental"],
                          report["allow_unbalanced_quotes_experimental"])
        formatted = "".join(edits[ident]["text_runs"])
        if without_space(formatted) != without_space(value):
            raise ValueError(f"formatter lost or changed a nonspace character: {ident}")
        checked_drafts += 1
    result = {"original_archive_sha256": sha256(args.original),
              "patched_archive_sha256": sha256(args.patched),
              "message_count": len(records), "inserted_english": len(edits),
              "unchanged_nontext_or_neutral": len(records) - len(edits),
              "japanese_letter_messages": len(japanese_rows),
              "unchanged_event_blocks": len(source_archive.entries),
              "new_layout_commands": dict(inserted_commands),
              "drafts_checked_no_character_loss": checked_drafts,
              "manual_or_overlay_edits": manual_overrides}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
