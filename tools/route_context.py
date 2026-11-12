#!/usr/bin/env python3
"""Derive spoiler-safe prior messages across scene loads in the PC-98 graph.

The analysis overapproximates both conditional outcomes and all choices from
the fresh-game entry. An earlier message is admitted only if it occurs on
every modeled path to the current message. Unknown control commands stop a
path. Unreachable IDs retain only proven same-block context. This does not
decode save flags or establish route names.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path

from event_graph import SOURCE_SHA256

SCOPE = "static-cross-scene-common-prefix-v1"
TERMINALS = {"20", "23", "95", "ff"}


def ident(scene: str, number: int) -> str:
    return f"MAX2_SCN/{scene}/text/{number:03d}"


def build_flow(graph: dict) -> tuple[dict[str, set[str]], dict[str, str], str]:
    """Return CFG successors, emitted message per node, and fresh-game root."""
    successors: dict[str, set[str]] = {}
    emits: dict[str, str] = {}
    block_starts = {}
    rows_by_block = {}
    for scene in graph["scenes"]:
        name = scene["scene"]
        for block in scene["blocks"]:
            commands = block["commands"]
            if not commands:
                continue
            key = (name, block["block"])
            rows_by_block[key] = commands
            block_starts[key] = f"{name}/{block['block']}/{commands[0]['offset']}"
            for row in commands:
                node = f"{name}/{block['block']}/{row['offset']}"
                successors[node] = set()
                if "message" in row:
                    emits[node] = ident(name, row["message"])
                if "choice" in row:
                    emits[node] = ident(name, row["choice"]["prompt"])
                    for option_index, option in enumerate(row["choice"]["options"]):
                        branch = f"{node}/option/{option_index}"
                        successors[branch] = set()
                        emits[branch] = ident(name, option["message"])
    for (name, block), commands in rows_by_block.items():
        lookup = {row["offset"]: f"{name}/{block}/{row['offset']}" for row in commands}
        for index, row in enumerate(commands):
            node = lookup[row["offset"]]
            following = lookup[commands[index + 1]["offset"]] if index + 1 < len(commands) else None
            if row["opcode"] in TERMINALS:
                targets = set()
            elif "load" in row:
                dest = row["load"]
                target = block_starts.get((f"{dest['scene']:03d}.SCN", dest["block"]))
                if target is None:
                    raise ValueError(f"missing load target from {node}: {dest}")
                targets = {target}
            elif "choice" in row:
                targets = set()
                for option_index, option in enumerate(row["choice"]["options"]):
                    branch = f"{node}/option/{option_index}"
                    if option["target"] not in lookup:
                        raise ValueError(f"choice target outside block: {node}")
                    successors[branch] = {lookup[option["target"]]}
                    targets.add(branch)
            elif "conditional" in row:
                target = row["conditional"]["target"]
                targets = {lookup[target]} if target in lookup else set()
                if following:
                    targets.add(following)
            else:
                targets = {following} if following else set()
            successors[node] = targets
    root = block_starts[("000.SCN", 1)]
    return successors, emits, root


def mandatory_prior(successors: dict[str, set[str]], emits: dict[str, str], root: str) -> tuple[dict[str, set[str]], set[str]]:
    """Forward must-analysis; intersection at merges prevents branch leaks."""
    reachable = {root}
    pending = deque([root])
    while pending:
        for target in successors[pending.popleft()]:
            if target not in reachable:
                reachable.add(target)
                pending.append(target)
    predecessors: dict[str, set[str]] = {node: set() for node in reachable}
    for node in reachable:
        for target in successors[node] & reachable:
            predecessors[target].add(node)
    all_messages = {emits[node] for node in reachable if node in emits}
    before = {node: (set() if node == root else set(all_messages)) for node in reachable}
    after = {node: before[node] | ({emits[node]} if node in emits else set()) for node in reachable}
    queue = deque(reachable)
    queued = set(reachable)
    while queue:
        node = queue.popleft()
        queued.remove(node)
        parents = predecessors[node]
        incoming = (set.intersection(*(after[parent] for parent in parents))
                    if parents and node != root else set())
        outgoing = incoming | ({emits[node]} if node in emits else set())
        if incoming != before[node] or outgoing != after[node]:
            before[node], after[node] = incoming, outgoing
            for target in successors[node] & reachable:
                if target not in queued:
                    queue.append(target)
                    queued.add(target)
    return before, reachable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("local_context", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; use a fresh path")
    graph = json.loads(args.graph.read_text())
    local = json.loads(args.local_context.read_text())
    if graph["source_sha256"] != SOURCE_SHA256 or local["source_sha256"] != SOURCE_SHA256:
        raise ValueError("unexpected original archive revision")
    if local["scope"] != "same-event-block-common-prefix":
        raise ValueError("unexpected local context scope")
    successors, emits, root = build_flow(graph)
    choice_option_ids = sorted({ident(scene["scene"], option["message"])
                                for scene in graph["scenes"] for block in scene["blocks"]
                                for command in block["commands"] if "choice" in command
                                for option in command["choice"]["options"]})
    before, reachable = mandatory_prior(successors, emits, root)
    occurrences: dict[str, list[set[str]]] = defaultdict(list)
    for node in reachable:
        if node in emits:
            occurrences[emits[node]].append(before[node] - {emits[node]})
    global_prior = {key: set.intersection(*sets) for key, sets in occurrences.items()}
    # The number of mandatory ancestors gives a stable topological ranking:
    # if A is mandatory before B, then rank(A) < rank(B).
    rank = {key: len(value) for key, value in global_prior.items()}
    context = {}
    method = {}
    for key in sorted(set(local["context_ids"]) | set(global_prior)):
        if key in global_prior:
            context[key] = sorted(global_prior[key], key=lambda item: (rank.get(item, 0), item))
            method[key] = "fresh-game-global"
        else:
            context[key] = local["context_ids"].get(key, [])
            method[key] = "same-block-fallback"
    output = {"source_sha256": SOURCE_SHA256, "scope": SCOPE,
              "fresh_game_root": root, "context_ids": context, "method": method,
              "choice_option_ids": choice_option_ids,
              "reachable_event_nodes": len(reachable)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    cross = sum(any(other.split('/')[1] != key.split('/')[1] for other in prior)
                for key, prior in context.items())
    print(f"mapped {len(context)} IDs; {len(global_prior)} fresh-game reachable; "
          f"{cross} have mandatory cross-scene context")


if __name__ == "__main__":
    main()
