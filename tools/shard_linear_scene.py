#!/usr/bin/env python3
"""Diagnostic: split a linear scene before its choice into two loadable scenes.

All text payloads and original commands are retained. This currently accepts
only the verified shape of v6 016.SCN and is not a general release sharder.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from event_graph import parse_scene
from leafpack_pc98 import Archive, Entry, build_archive, compress_lzs2, decode_scene, read_archive
from scenes import make_text_block, messages


def event_with_block(block: bytes) -> bytes:
    end = 11 + len(block)
    return struct.pack("<5H", 3, 10, 11, end, end + 1) + b"\x20" + block + b"\xff"


def scene_entry(template: Entry, name: str, event: bytes, text: bytes) -> Entry:
    event_at = struct.unpack_from("<H", template.data, 0)[0] * 16
    out = bytearray(template.data[:event_at])
    out += struct.pack("<I", len(event)) + compress_lzs2(event)
    out += bytes((-len(out)) % 16)
    struct.pack_into("<H", out, 2, len(out) // 16)
    out += struct.pack("<I", len(text)) + compress_lzs2(text)
    out += bytes((-len(out)) % 16)
    stem, ext = name.split(".")
    raw_name = (template.raw_name if name == template.name else
                stem.encode("ascii").ljust(8, b" ") + ext.encode("ascii").ljust(3, b" ") + b"\0")
    result = Entry(name, 0, len(out), 0, bytes(out), raw_name)
    if decode_scene(result) != (event, text):
        raise AssertionError(f"{name}: decoded round trip failed")
    parse_scene(name, event)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--new-scene", type=int, default=203)
    parser.add_argument("--cut-after", type=int, default=50)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.exists():
        parser.error("output must be new and distinct from source")
    if not 0 <= args.new_scene <= 255:
        parser.error("new scene number must fit one byte")
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if source_hash != args.expected_sha256:
        raise ValueError(f"source hash differs: {source_hash}")
    archive = read_archive(args.source)
    new_name = f"{args.new_scene:03d}.SCN"
    if new_name in {entry.name for entry in archive.entries}:
        raise ValueError("new scene name is already in use")
    old_entry = next(entry for entry in archive.entries if entry.name == "016.SCN")
    old_event, old_text = decode_scene(old_entry)
    parsed = parse_scene("016.SCN", old_event)
    commands = parsed["blocks"][1]["commands"]
    linear = [cmd for cmd in commands if cmd["opcode"] == "51"]
    if len(linear) != 97 or commands[:97] != linear or not 0 < args.cut_after < len(linear):
        raise ValueError("016.SCN linear call prefix differs from verified form")
    tail = commands[97:]
    if [cmd["opcode"] for cmd in tail] != ["27", "25", "52", "24", "52", "24", "20"]:
        raise ValueError("016.SCN choice tail differs from verified form")
    items = messages(old_text)
    prompt = tail[1]["choice"]["prompt"]
    options = [option["message"] for option in tail[1]["choice"]["options"]]
    first_ids = {cmd["message"] for cmd in linear[:args.cut_after]}
    second_ids = {cmd["message"] for cmd in linear[args.cut_after:]} | {prompt, *options}
    if first_ids & second_ids or first_ids | second_ids != set(range(len(items))):
        raise ValueError("messages are duplicated or omitted across shards")
    first_order = sorted(first_ids)
    second_order = sorted(second_ids)
    first_map = {old: new for new, old in enumerate(first_order)}
    second_map = {old: new for new, old in enumerate(second_order)}
    if max(len(first_order), len(second_order)) > 255:
        raise ValueError("new text ID exceeds one-byte event reference")

    first_block = b"".join(bytes((0x51, first_map[cmd["message"]]))
                           for cmd in linear[:args.cut_after])
    first_block += bytes((0x24, args.new_scene, 1, 0x20))
    second_block = bytearray(b"".join(bytes((0x51, second_map[cmd["message"]]))
                                     for cmd in linear[args.cut_after:]))
    for command in tail:
        raw = bytearray.fromhex(command["raw"])
        if command["opcode"] == "25":
            raw[1] = second_map[prompt]
            for index, old_id in enumerate(options):
                raw[3 + 2 * index] = second_map[old_id]
        second_block.extend(raw)
    first_event = event_with_block(first_block)
    second_event = event_with_block(bytes(second_block))
    first_text = make_text_block([items[index] for index in first_order])
    second_text = make_text_block([items[index] for index in second_order])
    first_entry = scene_entry(old_entry, "016.SCN", first_event, first_text)
    second_entry = scene_entry(old_entry, new_name, second_event, second_text)

    # Reconstruct the original call order and choice references from both
    # shards. The suffix's branch byte skips are unchanged and parse_scene
    # already verifies that they land on the two original load commands.
    inverse_first = {new: old for old, new in first_map.items()}
    inverse_second = {new: old for old, new in second_map.items()}
    parsed_first = parse_scene("016.SCN", first_event)["blocks"][1]["commands"]
    parsed_second = parse_scene(new_name, second_event)["blocks"][1]["commands"]
    restored_calls = [inverse_first[cmd["message"]] for cmd in parsed_first if cmd["opcode"] == "51"]
    restored_calls += [inverse_second[cmd["message"]] for cmd in parsed_second if cmd["opcode"] == "51"]
    if restored_calls != [cmd["message"] for cmd in linear]:
        raise AssertionError("linear message order changed")
    second_choice = next(cmd["choice"] for cmd in parsed_second if cmd["opcode"] == "25")
    if inverse_second[second_choice["prompt"]] != prompt or [inverse_second[o["message"]] for o in second_choice["options"]] != options:
        raise AssertionError("choice message references changed")
    if [cmd.get("load") for cmd in parsed_second if "load" in cmd] != [cmd["load"] for cmd in tail if "load" in cmd]:
        raise AssertionError("choice branch destinations changed")
    rebuilt_entries = tuple(first_entry if entry.name == "016.SCN" else entry for entry in archive.entries) + (second_entry,)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_archive(Archive(archive.label, rebuilt_entries)))
    readback = read_archive(args.output)
    if len(readback.entries) != len(archive.entries) + 1:
        raise AssertionError("new scene was not added")
    for before, after in zip(archive.entries, readback.entries):
        if before.name != "016.SCN" and before.data != after.data:
            raise AssertionError(f"{before.name}: unrelated scene changed")
    if decode_scene(readback.entries[-1]) != (second_event, second_text):
        raise AssertionError("new scene readback changed")
    print(f"sharded 016.SCN at call {args.cut_after} into {new_name}")
    print(f"decoded text bytes: {len(old_text)} -> {len(first_text)} + {len(second_text)}")
    print(f"packed scene bytes: {old_entry.length} -> {first_entry.length} + {second_entry.length}")


if __name__ == "__main__":
    main()
