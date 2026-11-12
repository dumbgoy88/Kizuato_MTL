#!/usr/bin/env python3
"""Snapshot the current PLaMo cache as an ignored, source-linked review queue.

This is a QA aid, not an automatic formatter or patch builder. It accepts a
cache that another process is appending and never writes to that cache.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

from compare_local import (ORIGINAL_SCN_SHA256, PROMPT_REVISION, load_messages,
                           prompt_for, sha256)
from scenes import ENGLISH_CODES


def read_cache(path: Path) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = collections.defaultdict(list)
    if not path.exists():
        return rows
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                break  # writer may be appending this line right now
            raise
        rows[item["cache_key"]].append(item)
    return rows


def cache_successes(items: list[dict], records: dict[str, dict]) -> tuple[list[dict], bool]:
    """Validate each cached response against its own source ID.

    Different IDs can have an identical prompt and share a cache key. Their
    raw hashes need not match because the engine commands may differ.
    """
    successes = [item for item in items if item.get("status") == "ok"]
    invalid = any(item.get("id") not in records or
                  item.get("source_sha256") != records[item["id"]]["raw_sha256"] or
                  not isinstance(item.get("translation"), str) or
                  not item["translation"].strip() for item in successes)
    return successes, invalid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("context_map", type=Path)
    parser.add_argument("facts", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path, help="new ignored JSONL review snapshot")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("review snapshot exists; choose a new output path")
    if args.output.resolve() == args.cache.resolve():
        raise ValueError("output must differ from cache")
    manifest = json.loads(args.manifest.read_text())
    context_map = json.loads(args.context_map.read_text())
    if manifest["source_archive_sha256"] != ORIGINAL_SCN_SHA256 or context_map["source_sha256"] != ORIGINAL_SCN_SHA256:
        raise ValueError("unexpected source archive revision")
    if manifest["context_scope"] != context_map["scope"]:
        raise ValueError("manifest/context scope mismatch")
    records = load_messages(args.messages)
    model_hash = sha256(args.model)
    cached = read_cache(args.cache)
    facts = json.loads(args.facts.read_text())["facts"]
    allowed_ids = {key: set(value) for key, value in context_map["context_ids"].items()}
    output = []
    issue_counts: collections.Counter[str] = collections.Counter()
    for row in manifest["samples"]:
        ident = row["id"]
        source = records[ident]
        prompt = prompt_for(row, records, manifest["glossary"], {}, allowed_ids, facts)
        key = hashlib.sha256(json.dumps({"revision": PROMPT_REVISION,
                                          "model_sha256": model_hash,
                                          "max_tokens": row.get("max_tokens", 512),
                                          "prompt": prompt}, ensure_ascii=False,
                                         sort_keys=True).encode()).hexdigest()
        successes, invalid = cache_successes(cached.get(key, []), records)
        result = successes[-1] if successes else None
        english = result["translation"] if result else None
        issues = []
        if result is None:
            issues.append("missing_draft")
        else:
            if invalid:
                issues.append("cache_source_mismatch")
            if len({item["translation"] for item in successes}) > 1:
                issues.append("conflicting_cached_outputs")
            if not english.strip():
                issues.append("empty_output")
            if len(english) > 24:
                issues.append("needs_manual_wrapping")
            if any("a" <= char <= "z" for char in english):
                issues.append("needs_case_conversion")
            if any(char.upper() not in ENGLISH_CODES for char in english):
                issues.append("needs_glyph_or_punctuation_review")
            if any(char in english for char in "\r\n\t"):
                issues.append("contains_layout_control")
            if any(char in english for char in "\ufffd\ufffc"):
                issues.append("replacement_character")
        for issue in issues:
            issue_counts[issue] += 1
        output.append({"id": ident, "source_sha256": source["raw_sha256"],
                       "source_ja": source["source"],
                       "source_text_runs": [part["text"] for part in source["segments"] if part["kind"] == "text"],
                       "original_commands": [part["raw"] for part in source["segments"] if part["kind"] == "command"],
                       "english_draft": english, "review_state": "unreviewed", "issues": issues,
                       "model_sha256": model_hash if result else None,
                       "cache_key": key if result else None})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in output))
    print(json.dumps({"queued": len(output), "drafted": len(output) - issue_counts["missing_draft"],
                      "issues": dict(issue_counts), "snapshot": str(args.output)}))


if __name__ == "__main__":
    main()
