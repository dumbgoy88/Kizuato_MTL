#!/usr/bin/env python3
"""Find prior messages that dominate later messages inside one event block.

This is a conservative same-block context map. It never mixes branches or
crosses scene loads; cross-scene story context requires separate route proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from event_graph import SOURCE_SHA256


def block_context(scene: str, block: dict) -> dict[str, list[str]]:
    commands = block["commands"]
    if not commands:
        return {}
    by_offset = {row["offset"]: row for row in commands}
    offsets = set(by_offset)
    successor: dict[int, set[int]] = {}
    for i, row in enumerate(commands):
        op = row["opcode"]
        following = commands[i + 1]["offset"] if i + 1 < len(commands) else None
        if op in {"20", "23", "24", "95", "ff"}:
            targets: set[int] = set()
        elif "choice" in row:
            targets = {item["target"] for item in row["choice"]["options"]}
        elif "conditional" in row:
            targets = {row["conditional"]["target"]}
            if following is not None:
                targets.add(following)
        else:
            targets = {following} if following is not None else set()
        successor[row["offset"]] = targets & offsets

    start = commands[0]["offset"]
    reachable = {start}
    pending = [start]
    while pending:
        for target in successor[pending.pop()]:
            if target not in reachable:
                reachable.add(target)
                pending.append(target)
    predecessors = {p: set() for p in reachable}
    for source in reachable:
        for target in successor[source] & reachable:
            predecessors[target].add(source)
    dom = {p: ({start} if p == start else set(reachable)) for p in reachable}
    changed = True
    while changed:
        changed = False
        for p in reachable - {start}:
            parents = predecessors[p]
            new = {p} | (set.intersection(*(dom[q] for q in parents)) if parents else set())
            if new != dom[p]:
                dom[p] = new
                changed = True
    result = {}
    for row in commands:
        if "message" not in row or row["offset"] not in reachable:
            continue
        ident = f"MAX2_SCN/{scene}/text/{row['message']:03d}"
        earlier = [other for other in commands if "message" in other and
                   other["offset"] in dom[row["offset"]] and other["offset"] != row["offset"]]
        result[ident] = [f"MAX2_SCN/{scene}/text/{other['message']:03d}" for other in earlier]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text())
    if graph["source_sha256"] != SOURCE_SHA256:
        raise SystemExit("graph is not from the expected original archive")
    context = {}
    for scene in graph["scenes"]:
        for block in scene["blocks"]:
            for ident, earlier in block_context(scene["scene"], block).items():
                if ident in context:
                    context[ident] = [item for item in context[ident] if item in earlier]
                else:
                    context[ident] = earlier
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"source_sha256": SOURCE_SHA256,
                                       "scope": "same-event-block-common-prefix",
                                       "context_ids": context}, indent=2) + "\n")
    print(f"mapped {len(context)} message IDs; {sum(bool(v) for v in context.values())} have safe same-block context")


if __name__ == "__main__":
    main()
