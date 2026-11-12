#!/usr/bin/env python3
"""Read and losslessly rebuild this revision's PC-98 LEAFPACK archives.

The archive table and file data use a repeating 13-byte additive key. This
implementation was checked against the supplied Kizuato MAX2_*.PAK files.
It deliberately does not assume the Windows LEAFPACK layout.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path

KEY = bytes.fromhex("6a d1 4b 13 58 7c f7 55 71 48 9f 3e b7")
COUNT_BIAS = 0x3F75
ENTRY_SIZE = 24
MAGIC = b"LEAFPACK:"


def decode(data: bytes) -> bytes:
    return bytes((value - KEY[i % len(KEY)]) & 0xFF for i, value in enumerate(data))


def encode(data: bytes) -> bytes:
    return bytes((value + KEY[i % len(KEY)]) & 0xFF for i, value in enumerate(data))


@dataclass(frozen=True)
class Entry:
    name: str
    offset: int
    length: int
    next_offset: int
    data: bytes  # decoded but still internally compressed/padded
    raw_name: bytes  # retain original NUL/space padding for byte-exact rebuild


@dataclass(frozen=True)
class Archive:
    label: bytes
    entries: tuple[Entry, ...]


def read_archive(path: Path) -> Archive:
    raw = path.read_bytes()
    if len(raw) < 18 or not raw.startswith(MAGIC):
        raise ValueError("not a PC-98 LEAFPACK archive")
    count = struct.unpack_from("<H", raw, 16)[0] - COUNT_BIAS
    if not 1 <= count <= 4096:
        raise ValueError(f"implausible archive count: {count}")
    table_start = len(raw) - count * ENTRY_SIZE
    if table_start <= 18:
        raise ValueError("table overlaps archive data")
    table = decode(raw[table_start:])
    entries = []
    expected_offset = 18
    for index in range(count):
        row = table[index * ENTRY_SIZE:(index + 1) * ENTRY_SIZE]
        name_bytes, offset, length, next_offset = struct.unpack("<12sIII", row)
        if name_bytes[-1:] != b"\0":
            raise ValueError(f"invalid name terminator at {index}")
        stem = name_bytes[:8].split(b"\0", 1)[0].decode("ascii").rstrip()
        ext = name_bytes[8:11].split(b"\0", 1)[0].decode("ascii").rstrip()
        name = f"{stem}.{ext}"
        if not re.fullmatch(r"[A-Z0-9_]{1,8}\.[A-Z0-9]{1,3}", name):
            raise ValueError(f"invalid entry name at {index}: {name!r}")
        if offset != expected_offset or next_offset != offset + length:
            raise ValueError(f"invalid offsets at {index}: {offset}, {length}, {next_offset}")
        if next_offset > table_start:
            raise ValueError(f"entry {index} overlaps table")
        entries.append(Entry(name, offset, length, next_offset, decode(raw[offset:next_offset]), name_bytes))
        expected_offset = next_offset
    if expected_offset != table_start:
        raise ValueError(f"unaccounted data before table: {table_start - expected_offset} bytes")
    return Archive(raw[:16], tuple(entries))


def build_archive(archive: Archive) -> bytes:
    if len(archive.label) != 16 or not archive.label.startswith(MAGIC):
        raise ValueError("invalid archive label")
    if len(archive.entries) > 0xFFFF - COUNT_BIAS:
        raise ValueError("too many entries")
    out = bytearray(archive.label)
    out += struct.pack("<H", len(archive.entries) + COUNT_BIAS)
    table = bytearray()
    for entry in archive.entries:
        offset = len(out)
        out += encode(entry.data)
        table += struct.pack("<12sIII", entry.raw_name, offset, len(entry.data), len(out))
    out += encode(table)
    return bytes(out)


def decompress_lzs2(data: bytes, output_size: int) -> tuple[bytes, int]:
    """LZS variant used by scene event and text blocks; return bytes consumed."""
    if output_size < 0 or output_size > 16_000_000:
        raise ValueError("implausible uncompressed block length")
    ring = bytearray(4096)
    ring_pos = 0xFEE
    source_pos = 0
    flags = 0
    bits_left = 0
    result = bytearray()
    while len(result) < output_size:
        if bits_left == 0:
            if source_pos >= len(data):
                raise ValueError("truncated LZS flag")
            flags = (~data[source_pos]) & 0xFF
            source_pos += 1
            bits_left = 8
        else:
            flags = (flags << 1) & 0xFF
        bits_left -= 1
        if flags & 0x80:
            if source_pos >= len(data):
                raise ValueError("truncated LZS literal")
            value = (~data[source_pos]) & 0xFF
            source_pos += 1
            result.append(value)
            ring[ring_pos] = value
            ring_pos = (ring_pos + 1) & 0xFFF
        else:
            if source_pos + 2 > len(data):
                raise ValueError("truncated LZS copy")
            word = (~int.from_bytes(data[source_pos:source_pos + 2], "little")) & 0xFFFF
            source_pos += 2
            copy_pos = word >> 4
            copy_len = (word & 15) + 3
            if len(result) + copy_len > output_size:
                raise ValueError("LZS copy exceeds declared output length")
            for _ in range(copy_len):
                value = ring[copy_pos]
                result.append(value)
                ring[ring_pos] = value
                ring_pos = (ring_pos + 1) & 0xFFF
                copy_pos = (copy_pos + 1) & 0xFFF
    return bytes(result), source_pos


def decode_scene(entry: Entry) -> tuple[bytes, bytes]:
    data = entry.data
    if len(data) < 32 or data[:2] != b"\x01\x00":
        raise ValueError(f"{entry.name}: unexpected scene header")
    event_at, text_at = struct.unpack_from("<HH", data)
    event_at *= 16
    text_at *= 16
    if not (16 <= event_at + 4 < text_at < len(data) - 4):
        raise ValueError(f"{entry.name}: invalid block offsets")
    event_size = struct.unpack_from("<I", data, event_at)[0]
    text_size = struct.unpack_from("<I", data, text_at)[0]
    event, event_used = decompress_lzs2(data[event_at + 4:text_at], event_size)
    text, text_used = decompress_lzs2(data[text_at + 4:], text_size)
    if event_at + 4 + event_used > text_at or text_at + 4 + text_used > len(data):
        raise ValueError(f"{entry.name}: compressed blocks overlap")
    return event, text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("list", "verify", "extract"):
        p = sub.add_parser(command)
        p.add_argument("archive", type=Path)
        if command == "extract":
            p.add_argument("directory", type=Path)
    p = sub.add_parser("rebuild")
    p.add_argument("archive", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--replace", nargs=2, metavar=("NAME", "DECODED_FILE"))
    args = parser.parse_args()
    archive = read_archive(args.archive)
    if args.command == "list":
        for entry in archive.entries:
            print(f"{entry.name:12} {entry.offset:8} {entry.length:8}")
        print(f"{len(archive.entries)} entries")
    elif args.command == "verify":
        rebuilt = build_archive(archive)
        if rebuilt != args.archive.read_bytes():
            raise SystemExit("round trip differs")
        if archive.label == b"LEAFPACK:MAX2SCN":
            for entry in archive.entries:
                decode_scene(entry)
        print(f"byte-identical round trip: {hashlib.sha256(rebuilt).hexdigest()}")
        print(f"validated {len(archive.entries)} entries")
    elif args.command == "extract":
        args.directory.mkdir(parents=True, exist_ok=True)
        for entry in archive.entries:
            (args.directory / entry.name).write_bytes(entry.data)
            if archive.label == b"LEAFPACK:MAX2SCN":
                event, text = decode_scene(entry)
                (args.directory / f"{entry.name}.event").write_bytes(event)
                (args.directory / f"{entry.name}.text").write_bytes(text)
        print(f"extracted {len(archive.entries)} entries to {args.directory}")
    elif args.command == "rebuild":
        entries = list(archive.entries)
        if args.replace:
            name, filename = args.replace
            matching = [i for i, entry in enumerate(entries) if entry.name == name]
            if len(matching) != 1:
                raise SystemExit(f"expected exactly one entry named {name}")
            data = Path(filename).read_bytes()
            if len(data) % 16:
                raise SystemExit("replacement must include 16-byte alignment padding")
            replacement = Entry(name, 0, len(data), 0, data, entries[matching[0]].raw_name)
            if archive.label == b"LEAFPACK:MAX2SCN":
                decode_scene(replacement)
            entries[matching[0]] = replacement
        output = build_archive(Archive(archive.label, tuple(entries)))
        if args.output.resolve() == args.archive.resolve():
            raise SystemExit("refusing to overwrite input archive")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(output)
        print(f"wrote {args.output} ({len(output)} bytes)")


if __name__ == "__main__":
    main()
