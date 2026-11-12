#!/usr/bin/env python3
"""Create a source-checked draft manifest from extracted messages and safe context.

The generated manifest is a queue of model drafts, not reviewed translation or
engine-ready patch data. Keep it in ignored work/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from compare_local import CONTEXT_SCOPES, ORIGINAL_SCN_SHA256, load_messages, sha256
from leafpack_pc98 import read_archive, decode_scene
from scenes import messages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("context_map", type=Path)
    parser.add_argument("glossary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--last-context", type=int, default=3)
    args = parser.parse_args()
    if args.last_context < 0:
        parser.error("--last-context must be nonnegative")
    if args.output.exists():
        raise ValueError("output already exists; choose a new manifest path")
    records = load_messages(args.messages)
    if sha256(args.archive) != ORIGINAL_SCN_SHA256:
        raise ValueError("unexpected original scene archive revision")
    expected = {}
    for entry in read_archive(args.archive).entries:
        _, block = decode_scene(entry)
        for index, raw in enumerate(messages(block)):
            expected[f"MAX2_SCN/{entry.name}/text/{index:03d}"] = hashlib.sha256(raw).hexdigest()
    if set(records) != set(expected) or any(records[ident]["raw_sha256"] != digest
                                               for ident, digest in expected.items()):
        raise ValueError("extracted messages are missing, duplicated, or changed from the original archive")
    context = json.loads(args.context_map.read_text())
    if context["source_sha256"] != ORIGINAL_SCN_SHA256 or context["scope"] not in CONTEXT_SCOPES:
        raise ValueError("unexpected context map provenance/scope")
    glossary = json.loads(args.glossary.read_text())
    choice_ids = set(context.get("choice_option_ids", []))
    rows = []
    skipped = []
    for ident, item in sorted(records.items(), key=lambda pair: (pair[1]["scene"], pair[1]["index"])):
        if item["parse_error"]:
            skipped.append({"id": ident, "reason": item["parse_error"]})
            continue
        if not item["source"].strip():
            skipped.append({"id": ident, "reason": "no_source_text"})
            continue
        safe = context["context_ids"].get(ident, [])
        recent = safe[-args.last_context:] if args.last_context else []
        # A route-safe selected option can carry the branch decision beyond
        # the three recent messages. The global must-analysis excludes sibling
        # options and drops an option after branches merge.
        choices = [cid for cid in safe if cid in choice_ids][-2:]
        prior = [cid for cid in safe if cid in set(recent) | set(choices)]
        if any(cid not in records or records[cid]["parse_error"] for cid in prior):
            raise ValueError(f"invalid prior context for {ident}")
        rows.append({"id": ident, "source_sha256": item["raw_sha256"], "context_ids": prior})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"source_archive_sha256": ORIGINAL_SCN_SHA256,
                                       "context_scope": context["scope"],
                                       "glossary": glossary, "samples": rows,
                                       "skipped": skipped}, ensure_ascii=False, indent=2) + "\n")
    print(f"queued {len(rows)} draft IDs; skipped {len(skipped)} IDs without translatable text; output {args.output}")


if __name__ == "__main__":
    main()
