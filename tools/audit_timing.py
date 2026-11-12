#!/usr/bin/env python3
"""Audit whether whole-message English reflow crosses original text commands.

Writes IDs and command opcodes only. Outputs belong in ignored build/ or work/.
This is a review gate, not an automatic repair of sentence/pause alignment.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from compare_local import load_messages


def intervening_commands(segments: list[dict]) -> list[str]:
    text_indices = [i for i, segment in enumerate(segments) if segment["kind"] == "text"]
    return [segment["opcode"]
            for start, end in zip(text_indices, text_indices[1:])
            for segment in segments[start + 1:end]
            if segment["kind"] == "command" and segment["opcode"] != "b0"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    parser.add_argument("edits", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; choose a new ignored filename")
    records = load_messages(args.messages)
    edits = json.loads(args.edits.read_text())
    if len({edit["id"] for edit in edits}) != len(edits):
        raise ValueError("duplicate edit ID")
    flagged = []
    counts: collections.Counter[str] = collections.Counter()
    for edit in edits:
        ident = edit["id"]
        if ident not in records or records[ident]["raw_sha256"] != edit["source_sha256"]:
            raise ValueError(f"source drift or unknown ID: {ident}")
        commands = intervening_commands(records[ident]["segments"])
        if commands:
            flagged.append({"id": ident, "intervening_commands": commands})
            counts.update(set(commands))
    result = {"edited": len(edits), "needs_timing_review": len(flagged),
              "by_opcode": dict(counts), "flagged": flagged}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "flagged"}))


if __name__ == "__main__":
    main()
