#!/usr/bin/env python3
"""Recompress all PC-98 scene blocks without changing decoded events or text."""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from leafpack_pc98 import Archive, Entry, build_archive, compress_lzs2, decode_scene, read_archive


def recompress(entry: Entry) -> Entry:
    event, text = decode_scene(entry)
    event_at = struct.unpack_from("<H", entry.data, 0)[0] * 16
    out = bytearray(entry.data[:event_at])
    out += struct.pack("<I", len(event)) + compress_lzs2(event)
    out += bytes((-len(out)) % 16)
    struct.pack_into("<H", out, 2, len(out) // 16)
    out += struct.pack("<I", len(text)) + compress_lzs2(text)
    out += bytes((-len(out)) % 16)
    result = Entry(entry.name, 0, len(out), 0, bytes(out), entry.raw_name)
    if decode_scene(result) != (event, text):
        raise AssertionError(f"{entry.name}: decoded data changed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.exists():
        parser.error("output must be a new file distinct from input")
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    if source_hash != args.expected_sha256:
        raise ValueError(f"source archive SHA-256 differs: {source_hash}")
    source = read_archive(args.source)
    entries = tuple(recompress(entry) for entry in source.entries)
    result = build_archive(Archive(source.label, entries))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    readback = read_archive(args.output)
    if [entry.name for entry in readback.entries] != [entry.name for entry in source.entries]:
        raise AssertionError("scene list changed")
    for before, after in zip(source.entries, readback.entries):
        if decode_scene(before) != decode_scene(after):
            raise AssertionError(f"{before.name}: readback differs")
    print(f"recompressed {len(entries)} scenes without decoded changes")
    print(f"archive bytes: {args.source.stat().st_size} -> {args.output.stat().st_size}")


if __name__ == "__main__":
    main()
