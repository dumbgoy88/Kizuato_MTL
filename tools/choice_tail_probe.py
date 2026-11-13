#!/usr/bin/env python3
"""Make a disposable direct choice probe from a sharded linear scene.

Only the selected scene's leading text calls are removed. Its choice, branch
commands, text payloads, and every other scene are checked on readback.
This shortcut must never be distributed as a game patch.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from event_graph import parse_scene
from leafpack_pc98 import Archive, build_archive, decode_scene, read_archive
from shard_linear_scene import event_with_block, scene_entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--scene", type=int, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.exists():
        parser.error("output must be new and distinct from source")
    actual = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if actual != args.expected_sha256:
        raise ValueError(f"source PAK hash differs: {actual}")
    archive = read_archive(args.source)
    name = f"{args.scene:03d}.SCN"
    found = False
    entries = []
    for entry in archive.entries:
        if entry.name != name:
            entries.append(entry)
            continue
        found = True
        event, text = decode_scene(entry)
        parsed = parse_scene(name, event)
        if len(parsed["blocks"]) != 3:
            raise ValueError(f"{name}: unsupported event block shape")
        commands = parsed["blocks"][1]["commands"]
        cut = next((i for i, command in enumerate(commands) if command["opcode"] != "51"), len(commands))
        tail = commands[cut:]
        if not cut or [command["opcode"] for command in tail] != ["27", "25", "52", "24", "52", "24", "20"]:
            raise ValueError(f"{name}: unsupported choice tail")
        new_event = event_with_block(b"".join(bytes.fromhex(command["raw"]) for command in tail))
        parsed_new = parse_scene(name, new_event)
        new_commands = parsed_new["blocks"][1]["commands"]
        if [command["raw"] for command in new_commands] != [command["raw"] for command in tail]:
            raise AssertionError("choice/branch command bytes changed")
        if [command.get("load") for command in new_commands if "load" in command] != [command.get("load") for command in tail if "load" in command]:
            raise AssertionError("branch loads changed")
        entries.append(scene_entry(entry, name, new_event, text))
    if not found:
        raise ValueError(f"{name}: scene missing")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_archive(Archive(archive.label, tuple(entries))))
    rebuilt = read_archive(args.output)
    for before, after in zip(archive.entries, rebuilt.entries):
        if before.name == name:
            if decode_scene(before)[1] != decode_scene(after)[1]:
                raise AssertionError("choice text changed on readback")
        elif before.data != after.data:
            raise AssertionError(f"{before.name}: unrelated scene changed")
    print(f"wrote diagnostic {name} direct choice with {cut} preceding calls skipped")


if __name__ == "__main__":
    main()
