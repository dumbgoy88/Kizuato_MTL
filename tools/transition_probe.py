#!/usr/bin/env python3
"""Make a disposable one-message test of a sharded scene handoff.

The source must be an already-sharded PAK. Only the selected scene's event
is shortened to its final text call followed by the existing load command.
Decoded text and every other scene remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from event_graph import parse_scene
from leafpack_pc98 import Archive, build_archive, decode_scene, read_archive
from scene_jump_probe import replace_event


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--scene", type=int, default=16)
    parser.add_argument("--target", type=int, default=203)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.exists():
        parser.error("output must be new and distinct from source")
    actual = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if actual != args.expected_sha256:
        raise ValueError(f"source PAK hash differs: {actual}")
    archive = read_archive(args.source)
    source_name = f"{args.scene:03d}.SCN"
    target_name = f"{args.target:03d}.SCN"
    if source_name not in {entry.name for entry in archive.entries} or target_name not in {entry.name for entry in archive.entries}:
        raise ValueError("source or target scene is missing")
    entries = []
    for entry in archive.entries:
        if entry.name != source_name:
            entries.append(entry)
            continue
        old_event, old_text = decode_scene(entry)
        old_commands = parse_scene(entry.name, old_event)["blocks"][1]["commands"]
        tail = b"".join(bytes.fromhex(command["raw"]) for command in old_commands[-3:])
        if [command["opcode"] for command in old_commands[-3:]] != ["51", "24", "20"] or old_commands[-2].get("load") != {"scene": args.target, "block": 1}:
            raise ValueError(f"{source_name}: expected final message/load handoff is missing")
        end = 11 + len(tail)
        new_event = (struct.pack("<5H", 3, 10, 11, end, end + 1) + b"\x20" +
                     tail + b"\xff")
        commands = parse_scene(entry.name, new_event)["blocks"][1]["commands"]
        if [command["opcode"] for command in commands] != ["51", "24", "20"]:
            raise AssertionError("transition event parse changed")
        replacement = replace_event(entry, new_event)
        if decode_scene(replacement) != (new_event, old_text):
            raise AssertionError("transition text changed")
        entries.append(replacement)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_archive(Archive(archive.label, tuple(entries))))
    readback = read_archive(args.output)
    for before, after in zip(archive.entries, readback.entries):
        if before.name == source_name:
            if decode_scene(after)[1] != decode_scene(before)[1]:
                raise AssertionError(f"{source_name}: text changed on readback")
        elif before.data != after.data:
            raise AssertionError(f"{before.name}: unrelated scene changed")
    print(f"wrote diagnostic {source_name} final-message -> {target_name} transition")


if __name__ == "__main__":
    main()
