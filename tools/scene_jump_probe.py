#!/usr/bin/env python3
"""Make a disposable scene-load probe by redirecting a new game's first event.

The source archive is hash pinned by the caller. Only 000.SCN's event changes;
its text and every other scene remain byte-identical. Use on ignored copies
for diagnosis, never as a distributable patch or full-route proof.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from event_graph import parse_scene
from leafpack_pc98 import Archive, Entry, build_archive, decode_scene, read_archive
from scenes import compress_literals

INITIAL_SETUP = bytes.fromhex("30 00 60 38 00 00 27 6a")


def replace_event(entry: Entry, new_event: bytes) -> Entry:
    old_event, old_text = decode_scene(entry)
    raw = entry.data
    event_at = struct.unpack_from("<H", raw, 0)[0] * 16
    text_at = struct.unpack_from("<H", raw, 2)[0] * 16
    rebuilt = bytearray(raw[:event_at])
    rebuilt += struct.pack("<I", len(new_event)) + compress_literals(new_event)
    rebuilt += bytes((-len(rebuilt)) % 16)
    struct.pack_into("<H", rebuilt, 2, len(rebuilt) // 16)
    rebuilt += raw[text_at:]
    replacement = Entry(entry.name, 0, len(rebuilt), 0, bytes(rebuilt), entry.raw_name)
    if decode_scene(replacement) != (new_event, old_text):
        raise AssertionError("scene failed event/text round trip")
    return replacement


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--scene", required=True, type=int)
    parser.add_argument("--block", type=int, default=1)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.exists():
        parser.error("output must be a new file distinct from input")
    if not (0 <= args.scene <= 255 and 0 <= args.block <= 255):
        parser.error("scene and block must be one-byte values")
    actual = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if actual != args.expected_sha256:
        raise ValueError(f"source archive hash mismatch: {actual}")
    archive = read_archive(args.source)
    target_name = f"{args.scene:03d}.SCN"
    if target_name not in {entry.name for entry in archive.entries}:
        raise ValueError("target scene missing from archive")
    changed = []
    for entry in archive.entries:
        if entry.name != "000.SCN":
            changed.append(entry)
            continue
        event, _ = decode_scene(entry)
        if event[11:19] != INITIAL_SETUP:
            raise ValueError("000.SCN initial setup differs from verified form")
        # 3 blocks: startup (20), first event (setup + load + 20), terminator (ff).
        new_event = (struct.pack("<5H", 3, 10, 11, 23, 24) + b"\x20" +
                     INITIAL_SETUP + bytes((0x24, args.scene, args.block, 0x20, 0xff)))
        parsed = parse_scene("000.SCN", new_event)
        loads = [cmd.get("load") for block in parsed["blocks"]
                 for cmd in block["commands"] if "load" in cmd]
        if loads != [{"scene": args.scene, "block": args.block}]:
            raise AssertionError("probe load target not preserved")
        changed.append(replace_event(entry, new_event))
    result = build_archive(Archive(archive.label, tuple(changed)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    rebuilt = read_archive(args.output)
    if [entry.name for entry in rebuilt.entries] != [entry.name for entry in archive.entries]:
        raise AssertionError("scene list changed")
    if any(a.data != b.data for a, b in zip(archive.entries, rebuilt.entries)
           if a.name != "000.SCN"):
        raise AssertionError("non-probe scene changed")
    print(f"wrote diagnostic scene jump to {target_name} block {args.block}: {args.output}")


if __name__ == "__main__":
    main()
