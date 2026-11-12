#!/usr/bin/env python3
"""Lossless 24-bit offset table reader/writer for Leaf PC-98 KCD fonts.

Glyph payloads remain opaque. Never treat unrelated glyph numbering as
Kizuato's: their research character tables use different orders.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def unpack(data: bytes) -> list[bytes]:
    if len(data) < 6:
        raise ValueError("truncated KCD")
    count = int.from_bytes(data[:3], "little")
    if not 1 <= count <= 10000:
        raise ValueError("implausible glyph count")
    table_end = 3 + 3 * count
    if table_end > len(data):
        raise ValueError("truncated offset table")
    offsets = [int.from_bytes(data[3 + 3*i:6 + 3*i], "little") for i in range(count)]
    if offsets[0] != table_end or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("noncontiguous/nonincreasing glyph offsets")
    if offsets[-1] >= len(data):
        raise ValueError("last glyph offset outside file")
    return [data[start:end] for start, end in zip(offsets, offsets[1:] + [len(data)])]


def pack(glyphs: list[bytes]) -> bytes:
    if not 1 <= len(glyphs) <= 10000 or any(not glyph for glyph in glyphs):
        raise ValueError("invalid glyph set")
    offset = 3 + 3 * len(glyphs)
    table = bytearray()
    for glyph in glyphs:
        if offset > 0xFFFFFF:
            raise ValueError("KCD 24-bit offset overflow")
        table += offset.to_bytes(3, "little")
        offset += len(glyph)
    return len(glyphs).to_bytes(3, "little") + table + b"".join(glyphs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?", help="optional new output for a no-op rebuild")
    args = parser.parse_args()
    data = args.input.read_bytes()
    glyphs = unpack(data)
    rebuilt = pack(glyphs)
    if rebuilt != data:
        raise ValueError("KCD did not rebuild byte-identically")
    if args.output:
        if args.output.resolve() == args.input.resolve() or args.output.exists():
            raise ValueError("output must be a new file distinct from input")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(rebuilt)
    print(f"{args.input}: {len(glyphs)} glyph records, SHA-256 {hashlib.sha256(data).hexdigest()}, byte-identical table rebuild")


if __name__ == "__main__":
    main()
