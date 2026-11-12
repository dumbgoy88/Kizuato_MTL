#!/usr/bin/env python3
"""Estimate compact-font capacity from a live draft cache without game text output.

These are character-count upper bounds, not measured native pixel layout.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from compare_local import load_messages
from review_drafts import read_cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    parser.add_argument("cache", type=Path)
    parser.add_argument("graph", type=Path)
    args = parser.parse_args()
    records = load_messages(args.messages)
    graph = json.loads(args.graph.read_text())
    choices = set()
    for scene in graph["scenes"]:
        for block in scene["blocks"]:
            for command in block["commands"]:
                if "choice" not in command:
                    continue
                choice = command["choice"]
                numbers = [choice["prompt"], *(option["message"] for option in choice["options"])]
                choices.update(f"MAX2_SCN/{scene['scene']}/text/{number:03d}" for number in numbers)
    latest = {}
    for items in read_cache(args.cache).values():
        for item in items:
            if item.get("status") == "ok":
                latest[item["id"]] = item
    counts = collections.Counter()
    for ident, item in latest.items():
        if ident not in records or records[ident]["raw_sha256"] != item["source_sha256"]:
            continue
        length = len(item["translation"])
        slots = sum(part["kind"] == "text" for part in records[ident]["segments"])
        counts["drafts"] += 1
        if ident in choices:
            counts["choice_drafts"] += 1
        for columns in (24, 36, 48):
            if length <= columns * slots:
                counts[f"{columns}_raw_original_run_capacity"] += 1
                if ident in choices:
                    counts[f"{columns}_raw_choice_run_capacity"] += 1
            if length <= columns * 13:
                counts[f"{columns}_raw_one_page_capacity"] += 1
    print(json.dumps(dict(counts), indent=2))


if __name__ == "__main__":
    main()
