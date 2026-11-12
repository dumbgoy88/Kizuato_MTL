#!/usr/bin/env python3
"""Build a disposable choice-layout probe from the nine-message demo PAK.

The fifteen text-display commands before 001.SCN's first choice are replaced
by no-ops. With --skip-opening, scene 000's twenty-three preceding display
commands are also no-ops; its conditions and scene-load commands stay intact.
The choice, its destinations, and all text stay intact.
Never use this probe archive as the distributable translation patch.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from leafpack_pc98 import Archive, Entry, build_archive, decode_scene, read_archive
from scenes import compress_literals

EXPECTED_DEMO_SHA256 = "c24ce40957e27f4b5901f2fb00b6e616feb43511bdc9f3aab0bfd57a93bec1c0"
DISPLAY_COMMANDS = b"".join(bytes((0x51, i)) for i in range(15))
OPENING_DISPLAY_COMMANDS = b"".join(bytes((0x51, i)) for i in range(23))
CHOICE_SUFFIX = bytes.fromhex("27 25 0f 03 10 00 11 04 12 08 52 24 02 01 52 24 03 01 52 24 04 01 20 ff")


def replace_event(entry: Entry, new_event: bytes, old_text: bytes) -> Entry:
    raw = entry.data
    event_at = struct.unpack_from("<H", raw, 0)[0] * 16
    text_at = struct.unpack_from("<H", raw, 2)[0] * 16
    new_raw = bytearray(raw[:event_at])
    new_raw += struct.pack("<I", len(new_event)) + compress_literals(new_event)
    new_raw += bytes((-len(new_raw)) % 16)
    struct.pack_into("<H", new_raw, 2, len(new_raw) // 16)
    new_raw += raw[text_at:]
    replacement = Entry(entry.name, 0, len(new_raw), 0, bytes(new_raw), entry.raw_name)
    if decode_scene(replacement) != (new_event, old_text):
        raise ValueError("probe scene failed round trip")
    return replacement


def build_probe(source: Path, output: Path, *, skip_opening: bool = False) -> None:
    if output.resolve() == source.resolve() or output.exists():
        raise ValueError("output must be a new file distinct from the input")
    if hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED_DEMO_SHA256:
        raise ValueError("unexpected nine-message demo archive revision")
    archive = read_archive(source)
    changed = []
    for entry in archive.entries:
        if entry.name not in ({"000.SCN", "001.SCN"} if skip_opening else {"001.SCN"}):
            changed.append(entry)
            continue
        old_event, old_text = decode_scene(entry)
        if entry.name == "001.SCN":
            if old_event[11:] != DISPLAY_COMMANDS + CHOICE_SUFFIX:
                raise ValueError("scene 001 event sequence differs from verified revision")
            new_event = old_event[:11] + b"\x52" * len(DISPLAY_COMMANDS) + CHOICE_SUFFIX
        else:
            if old_event[19:65] != OPENING_DISPLAY_COMMANDS:
                raise ValueError("scene 000 opening display sequence differs from verified revision")
            new_event = old_event[:19] + b"\x52" * len(OPENING_DISPLAY_COMMANDS) + old_event[65:]
        changed.append(replace_event(entry, new_event, old_text))
    expected = ["000.SCN", "001.SCN"] if skip_opening else ["001.SCN"]
    if [e.name for e in changed if e.data != next(o.data for o in archive.entries if o.name == e.name)] != expected:
        raise ValueError("unexpected scene changed")
    result = build_archive(Archive(archive.label, tuple(changed)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    print(f"wrote disposable probe {output}; choice, conditions, branches, and text unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--skip-opening", action="store_true",
                        help="also bypass scene 000 display commands on a disposable copy")
    args = parser.parse_args()
    build_probe(args.source, args.output, skip_opening=args.skip_opening)
