#!/usr/bin/env python3
"""Turn experimental in-message page markers into real Kizuato messages.

Native Kizuato skips text after a B3 inserted inside a message. This tool
splits at those markers and adds event 0x51 calls for continuation messages.
It operates on a disposable patched PAK and refuses an unexpected source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from event_graph import parse_scene
from leafpack_pc98 import Archive, Entry, build_archive, compress_lzs2, decode_scene, read_archive
from scenes import font_table, make_text_block, messages, segments

ORIGINAL_SHA256 = "beec74329493a72fcdb61c914539d3d210f0193d714fdc583189aec1e9a5cace"


def split_message(raw: bytes, original: bytes, markers: int, table: str) -> list[bytes]:
    if not markers:
        return [raw]
    parsed = segments(raw, table)
    source = segments(original, table)
    new_b3 = [part for part in parsed if part.get("opcode") == "b3"]
    old_b3 = [part for part in source if part.get("opcode") == "b3"]
    if len(new_b3) != len(old_b3) + markers:
        raise ValueError("page marker count differs from parsed commands")
    # All source B3 commands terminate their message. A source with a mid-text
    # B3 needs separate handling instead of this positional assumption.
    for index, part in enumerate(source):
        if part.get("opcode") == "b3" and any(x["kind"] == "text" for x in source[index + 1:]):
            raise ValueError("source has mid-message B3")
    pages: list[bytes] = []
    current = bytearray()
    seen = 0
    for part in parsed:
        current.extend(bytes.fromhex(part["raw"]))
        if part.get("opcode") == "b3" and seen < markers:
            seen += 1
            if not any(x["kind"] == "text" for x in segments(bytes(current) + b"\xaf", table)):
                raise ValueError("empty page before inserted B3")
            pages.append(bytes(current) + b"\xaf")
            current = bytearray()
    if seen != markers or not current:
        raise ValueError("missing page boundary or final page")
    pages.append(bytes(current))
    if b"".join(page[:-1] for page in pages[:-1]) + pages[-1] != raw:
        raise AssertionError("split lost or changed source bytes")
    for page in pages:
        segments(page, table)
    return pages


def relocate_event(name: str, event: bytes, continuation: dict[int, list[int]],
                   preludes: dict[int, list[int]]) -> bytes:
    scene = parse_scene(name, event)
    blocks = []
    relocations = []
    for block in scene["blocks"]:
        old_commands = block["commands"]
        relative = bytearray()
        offsets = {}
        patches = []
        for command in old_commands:
            offsets[command["offset"]] = len(relative)
            if command["opcode"] == "25":
                relative.extend(b"".join(bytes((0x51, index))
                                         for index in preludes.get(command["choice"]["prompt"], [])))
            original = bytes.fromhex(command["raw"])
            position = len(relative)
            relative.extend(original)
            if command["opcode"] in ("41", "42", "25"):
                patches.append((position, command))
            if command["opcode"] == "51":
                relative.extend(b"".join(bytes((0x51, index)) for index in continuation.get(command["message"], [])))
        offsets[block["end"]] = len(relative)
        for position, command in patches:
            if command["opcode"] in ("41", "42"):
                target = command["conditional"]["target"]
                skip = offsets[target] - (position + 4)
                if not 0 <= skip <= 255:
                    raise ValueError(f"{name} block {block['block']}: conditional skip exceeds one byte")
                relative[position + 3] = skip
            else:
                size = len(bytes.fromhex(command["raw"]))
                for option_number, option in enumerate(command["choice"]["options"]):
                    skip = offsets[option["target"]] - (position + size)
                    if not 0 <= skip <= 255:
                        raise ValueError(f"{name} block {block['block']}: choice skip exceeds one byte")
                    relative[position + 4 + 2 * option_number] = skip
        blocks.append(bytes(relative))
        relocations.append(offsets)
    start = 2 + 2 * (len(blocks) + 1)
    pointers = [start]
    for block in blocks:
        pointers.append(pointers[-1] + len(block))
    if pointers[-1] > 0xFFFF:
        raise ValueError(f"{name}: event pointer overflow")
    rebuilt = struct.pack("<H", len(blocks)) + b"".join(struct.pack("<H", p) for p in pointers) + b"".join(blocks)
    checked = parse_scene(name, rebuilt)
    for before, after, offsets in zip(scene["blocks"], checked["blocks"], relocations):
        old = before["commands"]
        new = after["commands"]
        cursor = 0
        for command in old:
            if command["opcode"] == "25":
                prefix = preludes.get(command["choice"]["prompt"], [])
                if [x["raw"] for x in new[cursor:cursor + len(prefix)]] != [bytes((0x51, n)).hex() for n in prefix]:
                    raise AssertionError("choice prelude calls changed")
                cursor += len(prefix)
            current = new[cursor]
            if command["opcode"] != current["opcode"]:
                raise AssertionError("original event command was displaced")
            if command["opcode"] not in ("41", "42", "25") and command["raw"] != current["raw"]:
                raise AssertionError("original event command changed")
            if "conditional" in command:
                expected = after["start"] + offsets[command["conditional"]["target"]]
                if current["conditional"]["target"] != expected:
                    raise AssertionError("relocated conditional target changed")
            if "choice" in command:
                for old_option, new_option in zip(command["choice"]["options"], current["choice"]["options"]):
                    expected = after["start"] + offsets[old_option["target"]]
                    if new_option["target"] != expected:
                        raise AssertionError("relocated choice target changed")
            cursor += 1 + (len(continuation.get(command["message"], [])) if command["opcode"] == "51" else 0)
        if cursor != len(new):
            raise AssertionError("unexpected event commands after relocation")
    return rebuilt


def replace_blocks(entry: Entry, event: bytes, text: bytes) -> Entry:
    original = entry.data
    event_at = struct.unpack_from("<H", original, 0)[0] * 16
    out = bytearray(original[:event_at])
    out += struct.pack("<I", len(event)) + compress_lzs2(event)
    out += bytes((-len(out)) % 16)
    text_at = len(out)
    out += struct.pack("<I", len(text)) + compress_lzs2(text)
    out += bytes((-len(out)) % 16)
    if text_at // 16 > 0xFFFF:
        raise ValueError(f"{entry.name}: scene block offset overflow")
    struct.pack_into("<H", out, 2, text_at // 16)
    replacement = Entry(entry.name, 0, len(out), 0, bytes(out), entry.raw_name)
    if decode_scene(replacement) != (event, text):
        raise AssertionError("scene round trip changed event or text")
    return replacement


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("paginated", type=Path)
    parser.add_argument("edits", type=Path)
    parser.add_argument("font_table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--allow-unreferenced", action="store_true", help="leave unreferenced messages unsplit and report them")
    args = parser.parse_args()
    if args.output.exists() or args.report.exists():
        parser.error("output/report exists; choose new ignored paths")
    if hashlib.sha256(args.original.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        parser.error("unexpected original PAK revision")
    original = read_archive(args.original)
    paginated = read_archive(args.paginated)
    if [e.name for e in original.entries] != [e.name for e in paginated.entries]:
        raise ValueError("scene entry list changed")
    edits = {row["id"]: row for row in json.loads(args.edits.read_text())}
    table = font_table(args.font_table)
    rewritten = []
    unsplit = []
    stats = Counter()
    for source_entry, edit_entry in zip(original.entries, paginated.entries):
        source_event, source_text = decode_scene(source_entry)
        event, text = decode_scene(edit_entry)
        if event != source_event:
            raise ValueError(f"{edit_entry.name}: source event changed before splitting")
        source_items = messages(source_text)
        edited_items = messages(text)
        if len(source_items) != len(edited_items):
            raise ValueError(f"{edit_entry.name}: message count changed before splitting")
        source_commands = [c for b in parse_scene(edit_entry.name, event)["blocks"] for c in b["commands"]]
        refs = Counter(c["message"] for c in source_commands if c["opcode"] == "51")
        prompts = Counter(c["choice"]["prompt"] for c in source_commands if c["opcode"] == "25")
        continuation: dict[int, list[int]] = {}
        preludes: dict[int, list[int]] = {}
        next_items = list(edited_items)
        for index, (source_raw, edited_raw) in enumerate(zip(source_items, edited_items)):
            ident = f"MAX2_SCN/{edit_entry.name}/text/{index:03d}"
            row = edits.get(ident)
            markers = sum(run.count("\f") for run in row["text_runs"]) if row else 0
            if not markers:
                continue
            if hashlib.sha256(source_raw).hexdigest() != row["source_sha256"]:
                raise ValueError(f"source drift: {ident}")
            if not refs[index] and not prompts[index]:
                if not args.allow_unreferenced:
                    raise ValueError(f"{ident}: no event 51 call for continuation")
                unsplit.append(ident)
                continue
            if refs[index] and prompts[index]:
                raise ValueError(f"{ident}: both ordinary and choice-prompt references")
            pages = split_message(edited_raw, source_raw, markers, table)
            if len(next_items) + len(pages) - 1 > 256:
                raise ValueError(f"{edit_entry.name}: one-byte message index overflow")
            extra_ids = list(range(len(next_items), len(next_items) + len(pages) - 1))
            if prompts[index]:
                next_items[index] = pages[-1]
                preludes[index] = extra_ids
                next_items.extend(pages[:-1])
                stats["split_choice_prompts"] += 1
            else:
                next_items[index] = pages[0]
                continuation[index] = extra_ids
                next_items.extend(pages[1:])
            stats["split_messages"] += 1
            stats["continuation_messages"] += len(pages) - 1
        new_event = relocate_event(edit_entry.name, event, continuation, preludes) if continuation or preludes else event
        new_text = make_text_block(next_items)
        rewritten.append(replace_blocks(edit_entry, new_event, new_text) if continuation or preludes else edit_entry)
        if continuation or preludes:
            stats["changed_scenes"] += 1
    archive = Archive(paginated.label, tuple(rewritten))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_archive(archive))
    report = {"original_sha256": ORIGINAL_SHA256,
              "paginated_sha256": hashlib.sha256(args.paginated.read_bytes()).hexdigest(),
              "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
              **stats, "unreferenced_unsplit": unsplit}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
