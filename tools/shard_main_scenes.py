#!/usr/bin/env python3
"""Split large linear PC-98 scene events into memory-sized scene shards.

Only scenes with a straight 0x51 prefix and fully referenced messages are
supported. All message payloads, original control commands, and branch bytes
must reconstruct exactly. Special bonus scene 201 is reported separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from event_graph import parse_scene
from leafpack_pc98 import Archive, build_archive, decode_scene, read_archive
from scenes import make_text_block, messages
from shard_linear_scene import event_with_block, scene_entry


def referenced(command: dict) -> list[int]:
    if command["opcode"] == "51":
        return [command["message"]]
    if command["opcode"] == "25":
        return [command["choice"]["prompt"]] + [option["message"] for option in command["choice"]["options"]]
    return []


def map_command(command: dict, mapping: dict[int, int]) -> bytes:
    raw = bytearray.fromhex(command["raw"])
    if command["opcode"] == "51":
        raw[1] = mapping[command["message"]]
    elif command["opcode"] == "25":
        raw[1] = mapping[command["choice"]["prompt"]]
        for index, option in enumerate(command["choice"]["options"]):
            raw[3 + 2 * index] = mapping[option["message"]]
    return bytes(raw)


def divide(entry, capacity: int, new_numbers: list[int]):
    event, text = decode_scene(entry)
    items = messages(text)
    parsed = parse_scene(entry.name, event)
    if len(parsed["blocks"]) != 3 or [c["opcode"] for c in parsed["blocks"][0]["commands"]] != ["20"] or [c["opcode"] for c in parsed["blocks"][2]["commands"]] != ["ff"]:
        raise ValueError(f"{entry.name}: unsupported event block shape")
    commands = parsed["blocks"][1]["commands"]
    boundary = next((index for index, command in enumerate(commands) if command["opcode"] != "51"), len(commands))
    linear, tail = commands[:boundary], commands[boundary:]
    if not linear:
        raise ValueError(f"{entry.name}: no linear message prefix")
    if any("conditional" in command and command["conditional"]["target"] < tail[0]["offset"] for command in tail):
        raise ValueError(f"{entry.name}: branch enters the linear prefix")
    if any(option["target"] < tail[0]["offset"] for command in tail if "choice" in command for option in command["choice"]["options"]):
        raise ValueError(f"{entry.name}: choice enters the linear prefix")
    linear_ids = [command["message"] for command in linear]
    tail_ids = {ident for command in tail for ident in referenced(command)}
    if len(linear_ids) != len(set(linear_ids)) or set(linear_ids) & tail_ids or set(linear_ids) | tail_ids != set(range(len(items))):
        raise ValueError(f"{entry.name}: duplicated or unreferenced message IDs")

    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_size = 2
    for command in linear:
        cost = 2 + len(items[command["message"]])
        if cost + 2 > capacity:
            raise ValueError(f"{entry.name}: one message exceeds scene capacity")
        if current and current_size + cost > capacity:
            chunks.append(current)
            current, current_size = [], 2
        current.append(command)
        current_size += cost
    tail_cost = sum(2 + len(items[ident]) for ident in tail_ids)
    if tail_cost + 2 > capacity:
        raise ValueError(f"{entry.name}: choice/ending tail exceeds scene capacity")
    if current and current_size + tail_cost > capacity:
        chunks.append(current)
        current = []
    chunks.append(current)
    needed = len(chunks) - 1
    if needed > len(new_numbers):
        raise ValueError(f"{entry.name}: no free one-byte scene IDs")
    names = [entry.name] + [f"{number:03d}.SCN" for number in new_numbers[:needed]]
    rebuilt = []
    inverse_maps = []
    report_chunks = []
    for index, calls in enumerate(chunks):
        final = index == len(chunks) - 1
        ids = {command["message"] for command in calls} | (tail_ids if final else set())
        ordered = sorted(ids)
        mapping = {old: new for new, old in enumerate(ordered)}
        if len(mapping) > 255:
            raise ValueError(f"{entry.name}: too many IDs in shard")
        inverse_maps.append({new: old for old, new in mapping.items()})
        block = bytearray(b"".join(map_command(command, mapping) for command in calls))
        if final:
            block.extend(b"".join(map_command(command, mapping) for command in tail))
        else:
            block.extend(bytes((0x24, new_numbers[index], 1, 0x20)))
        shard_event = event_with_block(bytes(block))
        shard_text = make_text_block([items[old] for old in ordered])
        if len(shard_text) > capacity:
            raise AssertionError(f"{entry.name}: capacity planner overflow")
        shard = scene_entry(entry, names[index], shard_event, shard_text)
        rebuilt.append(shard)
        report_chunks.append({"scene": shard.name, "text_bytes": len(shard_text),
                              "packed_bytes": shard.length, "source_ids": ordered})

    # Map every new command back to the original bytes. Non-final shard loads
    # and terminators are the only inserted control commands.
    restored = bytearray()
    recovered = {}
    for index, shard in enumerate(rebuilt):
        shard_event, shard_text = decode_scene(shard)
        remapped = parse_scene(shard.name, shard_event)["blocks"][1]["commands"]
        if index < len(rebuilt) - 1:
            if [command["opcode"] for command in remapped[-2:]] != ["24", "20"] or remapped[-2]["load"] != {"scene": new_numbers[index], "block": 1}:
                raise AssertionError(f"{entry.name}: shard handoff changed")
            remapped = remapped[:-2]
        inverse = inverse_maps[index]
        for command in remapped:
            restored.extend(map_command(command, inverse))
        for new_id, payload in enumerate(messages(shard_text)):
            old_id = inverse[new_id]
            if old_id in recovered:
                raise AssertionError(f"{entry.name}: source message duplicated")
            recovered[old_id] = payload
    original_raw = b"".join(bytes.fromhex(command["raw"]) for command in commands)
    if restored != original_raw or [recovered[i] for i in range(len(items))] != items:
        raise AssertionError(f"{entry.name}: source command or message reconstruction failed")
    return rebuilt, report_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--capacity", type=int, default=16000)
    args = parser.parse_args()
    if args.capacity < 1024 or args.capacity > 17797:
        parser.error("capacity must be between 1024 and the original 17,797-byte maximum")
    if args.source.resolve() == args.output.resolve() or args.output.exists() or args.report.exists():
        parser.error("outputs must be new and distinct from input")
    actual = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if actual != args.expected_sha256:
        raise ValueError(f"source archive SHA-256 differs: {actual}")
    archive = read_archive(args.source)
    used = {int(entry.name[:3]) for entry in archive.entries}
    free = [number for number in list(range(203, 256)) + list(range(170, 200)) if number not in used]
    replacements = {}
    extras = []
    rows = []
    exemptions = []
    for entry in archive.entries:
        _, text = decode_scene(entry)
        if len(text) <= args.capacity:
            continue
        if entry.name == "201.SCN":
            exemptions.append({"scene": entry.name, "text_bytes": len(text),
                               "reason": "dynamic bonus-scene message references require separate handling"})
            continue
        shards, info = divide(entry, args.capacity, free)
        replacements[entry.name] = shards[0]
        extras.extend(shards[1:])
        del free[:len(shards)-1]
        rows.append({"source_scene": entry.name, "shards": info})
    entries = sorted((replacements.get(entry.name, entry) for entry in archive.entries),
                     key=lambda entry: int(entry.name[:3])) + extras
    entries.sort(key=lambda entry: int(entry.name[:3]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_archive(Archive(archive.label, tuple(entries))))
    rebuilt = read_archive(args.output)
    if [entry.name for entry in rebuilt.entries] != [entry.name for entry in entries]:
        raise AssertionError("archive scene order changed")
    for before in archive.entries:
        after = next(entry for entry in rebuilt.entries if entry.name == before.name)
        if before.name not in replacements and before.data != after.data:
            raise AssertionError(f"{before.name}: untouched scene changed")
    report = {"source_sha256": actual,
              "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
              "capacity": args.capacity, "original_scenes": len(archive.entries),
              "sharded_sources": len(rows), "added_scenes": len(extras),
              "total_scenes": len(entries), "exemptions": exemptions,
              "rows": rows}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"sharded {len(rows)} source scenes into {len(extras)} new scenes; "
          f"total {len(entries)}; exemptions {len(exemptions)}")
    print(f"PAK SHA-256 {report['output_sha256']}")


if __name__ == "__main__":
    main()
