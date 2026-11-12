#!/usr/bin/env python3
"""Parse the supplied PC-98 Kizuato event blocks and export control-flow facts.

Unknown opcodes, invalid pointers and invalid branch/load targets fail closed.
This is a static graph; flag conditions and route order still need verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from leafpack_pc98 import decode_scene, read_archive
from scenes import COMMAND_LENGTHS

SOURCE_SHA256 = "beec74329493a72fcdb61c914539d3d210f0193d714fdc583189aec1e9a5cace"
LENGTHS = dict(COMMAND_LENGTHS)
LENGTHS.update({0x20: 1, 0x23: 2, 0x24: 3, 0x27: 1, 0x41: 4,
                0x42: 4, 0x4B: 3, 0x51: 2, 0x52: 1, 0x94: 1,
                0x95: 2, 0x96: 2, 0xFF: 1})


def parse_scene(name: str, event: bytes) -> dict:
    if len(event) < 4:
        raise ValueError(f"{name}: short event block")
    count = struct.unpack_from("<H", event)[0]
    if count < 1 or 2 + 2 * (count + 1) > len(event):
        raise ValueError(f"{name}: invalid block count")
    ptr = [struct.unpack_from("<H", event, 2 + 2 * i)[0] for i in range(count + 1)]
    if ptr[0] != 2 + 2 * (count + 1) or ptr[-1] != len(event) or any(a > b for a, b in zip(ptr, ptr[1:])):
        raise ValueError(f"{name}: invalid event pointer table")
    blocks = []
    for block, (start, end) in enumerate(zip(ptr, ptr[1:])):
        commands = []
        pos = start
        while pos < end:
            op = event[pos]
            size = 3 + 2 * event[pos + 2] if op == 0x25 and pos + 2 < end else LENGTHS.get(op)
            if size is None or pos + size > end:
                raise ValueError(f"{name} block {block} offset {pos}: unknown/truncated opcode {op:02x}")
            args = event[pos + 1:pos + size]
            row = {"offset": pos, "opcode": f"{op:02x}", "raw": event[pos:pos + size].hex()}
            if op == 0x51:
                row["message"] = args[0]
            elif op == 0x24:
                row["load"] = {"scene": args[0], "block": args[1]}
            elif op in (0x41, 0x42):
                row["conditional"] = {"flag": args[0], "value": args[1],
                                      "kind": "eq" if op == 0x41 else "ne",
                                      "target": pos + size + args[2]}
            elif op == 0x25:
                row["choice"] = {"prompt": args[0], "options": [
                    {"message": args[2 + 2 * i], "target": pos + size + args[3 + 2 * i]}
                    for i in range(args[1])]}
            commands.append(row)
            pos += size
        boundaries = {x["offset"] for x in commands} | {end}
        for row in commands:
            targets = []
            if "conditional" in row:
                targets.append(row["conditional"]["target"])
            if "choice" in row:
                targets += [x["target"] for x in row["choice"]["options"]]
            if any(t not in boundaries for t in targets):
                raise ValueError(f"{name} block {block}: branch target is not a command boundary")
        blocks.append({"block": block, "start": start, "end": end, "commands": commands})
    return {"scene": name, "event_sha256": hashlib.sha256(event).hexdigest(), "blocks": blocks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise SystemExit("unexpected original MAX2_SCN.PAK revision")
    archive = read_archive(args.archive)
    scenes = [parse_scene(entry.name, decode_scene(entry)[0]) for entry in archive.entries]
    by_number = {int(s["scene"][:3]): s for s in scenes}
    for scene in scenes:
        for block in scene["blocks"]:
            for command in block["commands"]:
                if "load" in command:
                    dest = command["load"]
                    if dest["scene"] not in by_number or dest["block"] >= len(by_number[dest["scene"]]["blocks"]):
                        raise ValueError(f"invalid scene load in {scene['scene']}: {dest}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"source_sha256": SOURCE_SHA256, "scenes": scenes}, indent=2) + "\n")
    commands = [c for s in scenes for b in s["blocks"] for c in b["commands"]]
    print(f"parsed {len(scenes)} scenes, {sum(len(s['blocks']) for s in scenes)} blocks, "
          f"{sum('choice' in c for c in commands)} choices, {sum('load' in c for c in commands)} loads")


if __name__ == "__main__":
    main()
