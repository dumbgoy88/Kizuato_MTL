#!/usr/bin/env python3
"""Export Kizuato text losslessly and build a scene from explicit text edits.

The EUC-JP font table is an external research input, not bundled game data.
Unknown commands and invalid pointers fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from leafpack_pc98 import Archive, Entry, build_archive, decode_scene, read_archive

COMMAND_LENGTHS = {
    # In 201.SCN/text/032, 0x26 occurs three times after a 0x3a command.
    # Treating it as one byte yields complete 24-glyph text runs and an AF
    # terminator; all original bytes are preserved. Native effect is unknown.
    0x26: 1,
    **{k: 2 for k in (0x30, 0x31, 0x34, 0x35, 0x36, 0x39, 0x3A, 0x3B, 0x3C,
                      0x62, 0x63, 0x67, 0x68, 0x6B, 0x6C, 0x80, 0x84, 0x87,
                      0xA0, 0xB6, 0xB7, 0xB9)},
    **{k: 1 for k in (0x60, 0x61, 0x64, 0x65, 0x66, 0x69, 0x6A, 0x81, 0x82,
                      0x85, 0xA1, 0xA3, 0xA6, 0xAF, 0xB0, 0xB2, 0xB3, 0xBB,
                      0xBC, 0xC9, 0xCA, 0xCB, 0xCD)},
    **{k: 3 for k in (0x37, 0x38, 0xA2, 0xC1, 0xC2, 0xC3, 0xC8, 0xCC)},
    **{k: 4 for k in (0xBD, 0xBE, 0xBF, 0xC0)},
    0xC4: 6, 0xC6: 7,
}


def font_table(path: Path) -> str:
    table = path.read_bytes().decode("euc_jp")
    if not table.startswith("　■ＡＢＣ"):
        raise ValueError("unexpected font table; expected XLVNS kizfont.tbl ordering")
    return table


def table_index(code: int) -> int:
    # This original PC-98 revision skips two XLVNS table positions. The
    # boundaries are inferred from observed punctuation and opening text;
    # verify against the native font before treating the whole corpus as final.
    return code + (code > 0xD0) + (code >= 0xE4)


def messages(block: bytes) -> list[bytes]:
    if len(block) < 2:
        raise ValueError("truncated text block")
    count = struct.unpack_from("<H", block)[0]
    if count == 0 or 2 + 2 * count > len(block):
        raise ValueError("invalid message pointer count")
    offsets = [struct.unpack_from("<H", block, 2 + 2 * i)[0] for i in range(count)]
    if offsets[0] != 2 + 2 * count or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("message pointers are not contiguous/increasing")
    if offsets[-1] >= len(block):
        raise ValueError("last pointer exceeds text block")
    return [block[start:end] for start, end in zip(offsets, offsets[1:] + [len(block)])]


def segments(message: bytes, table: str) -> list[dict]:
    out = []
    i = 0
    while i < len(message):
        b = message[i]
        if b <= 0x20:
            if i + 1 >= len(message):
                raise ValueError("truncated glyph code")
            code = (b << 8) | message[i + 1]
            mapped = table_index(code)
            char = table[mapped] if mapped < len(table) else "�"
            if out and out[-1]["kind"] == "text":
                out[-1]["text"] += char
                out[-1]["raw"] += message[i:i + 2].hex()
            else:
                out.append({"kind": "text", "text": char, "raw": message[i:i + 2].hex()})
            i += 2
        else:
            size = COMMAND_LENGTHS.get(b)
            if size is None or i + size > len(message):
                raise ValueError(f"unknown/truncated command {b:02x} at {i}")
            out.append({"kind": "command", "opcode": f"{b:02x}", "raw": message[i:i + size].hex()})
            i += size
            if b == 0xAF and i != len(message):
                raise ValueError("bytes after message terminator")
    if not out or out[-1].get("opcode") != "af":
        raise ValueError("message lacks AF terminator")
    return out


def make_text_block(items: list[bytes]) -> bytes:
    start = 2 + 2 * len(items)
    offsets = []
    for item in items:
        if start > 0xFFFF:
            raise ValueError("16-bit message pointer overflow")
        offsets.append(start)
        start += len(item)
    if start > 0x10000:
        raise ValueError("16-bit text block overflow")
    return struct.pack("<H", len(items)) + b"".join(struct.pack("<H", p) for p in offsets) + b"".join(items)


def compress_literals(data: bytes) -> bytes:
    """Valid LZS stream using only inverted literal groups (larger than original)."""
    out = bytearray()
    for i in range(0, len(data), 8):
        group = data[i:i + 8]
        out.append((1 << (8 - len(group))) - 1)
        out.extend((~value) & 0xFF for value in group)
    return bytes(out)


def replace_text_block(entry: Entry, new_text: bytes) -> bytes:
    raw = entry.data
    event_at = struct.unpack_from("<H", raw, 2)[0] * 16
    old_text_at = struct.unpack_from("<H", raw, 4)[0] * 16
    event_block = raw[event_at:old_text_at]
    text_at = event_at + len(event_block)
    if text_at % 16:
        raise ValueError("old event block alignment invalid")
    new_block = struct.pack("<I", len(new_text)) + compress_literals(new_text)
    out = bytearray(raw[:text_at])
    struct.pack_into("<H", out, 4, text_at // 16)
    out += new_block
    out += bytes((-len(out)) % 16)
    if decode_scene(Entry(entry.name, 0, len(out), 0, bytes(out), entry.raw_name)) != (decode_scene(entry)[0], new_text):
        raise ValueError("modified scene failed decompress round trip")
    return bytes(out)


ENGLISH_CODES = {chr(ord("A") + i): i + 2 for i in range(26)}
ENGLISH_CODES.update({str(i): i + 28 for i in range(10)})
ENGLISH_CODES.update({" ": 0, "■": 1, ".": 0xD5, ",": 0xD6, "?": 0xCF,
                      "!": 0xD0, "「": 0xCB, "」": 0xCC,
                      "−": 0xD2, "…": 0xDB, "（": 0xCD, "）": 0xCE,
                      "・": 0xD9, "〜": 0xD4})


def encode_english(value: str, max_run_glyphs: int = 24) -> bytes:
    if len(value) > max_run_glyphs:
        raise ValueError(f"text run exceeds {max_run_glyphs}-glyph limit: {value!r}")
    try:
        return b"".join(struct.pack(">H", ENGLISH_CODES[char]) for char in value)
    except KeyError as exc:
        raise ValueError(f"unsupported English glyph {exc.args[0]!r}") from exc


def encode_paged_english(value: str) -> bytes:
    """Encode formatter-inserted line/page breaks inside one original text run."""
    out = bytearray()
    for part in re.split(r"([\n\f])", value):
        if part == "\n":
            out.append(0xB0)
        elif part == "\f":
            out.append(0xB3)
        elif part:
            out.extend(encode_english(part, 24))
    return bytes(out)


def apply_edits(archive_path: Path, table_path: Path, edits_path: Path, output: Path,
                max_run_glyphs: int = 24) -> None:
    if output.resolve() == archive_path.resolve() or output.exists():
        raise ValueError("output must be a new file distinct from the input")
    archive = read_archive(archive_path)
    table = font_table(table_path)
    edit_rows = json.loads(edits_path.read_text())
    edits = {}
    for row in edit_rows:
        key = row["id"]
        if key in edits:
            raise ValueError(f"duplicate edit ID: {key}")
        edits[key] = row
    used = set()
    new_entries = []
    for entry in archive.entries:
        scene_edits = {key: value for key, value in edits.items() if key.startswith(f"MAX2_SCN/{entry.name}/text/")}
        if not scene_edits:
            new_entries.append(entry)
            continue
        event, block = decode_scene(entry)
        items = messages(block)
        new_items = []
        for index, original in enumerate(items):
            key = f"MAX2_SCN/{entry.name}/text/{index:03d}"
            if key not in scene_edits:
                new_items.append(original)
                continue
            row = scene_edits[key]
            if hashlib.sha256(original).hexdigest() != row["source_sha256"]:
                raise ValueError(f"source changed for {key}")
            original_segments = segments(original, table)
            text_count = sum(s["kind"] == "text" for s in original_segments)
            if len(row["text_runs"]) != text_count:
                raise ValueError(f"wrong text run count for {key}: expected {text_count}")
            replacements = iter(row["text_runs"])
            paginated = row.get("format") == "paginated"
            if row.get("format") not in (None, "paginated"):
                raise ValueError(f"unknown format for {key}")
            raw = b"".join((encode_paged_english(next(replacements)) if paginated else
                            encode_english(next(replacements), max_run_glyphs)) if s["kind"] == "text"
                           else bytes.fromhex(s["raw"]) for s in original_segments)
            parsed_new = segments(raw, table)
            old_commands = [s["raw"] for s in original_segments if s["kind"] == "command"]
            new_commands = [s["raw"] for s in parsed_new if s["kind"] == "command"]
            if not paginated and old_commands != new_commands:
                raise ValueError(f"control codes changed for {key}")
            if paginated:
                expected_commands = []
                for part in original_segments:
                    if part["kind"] == "command":
                        expected_commands.append(part["raw"])
                # The only extra commands are generated from formatter markers.
                extra_count = sum(run.count("\n") + run.count("\f") for run in row["text_runs"])
                if len(new_commands) != len(expected_commands) + extra_count:
                    raise ValueError(f"unexpected pagination commands for {key}")
            new_items.append(raw)
            used.add(key)
        new_text = make_text_block(new_items)
        replacement = replace_text_block(entry, new_text)
        if decode_scene(Entry(entry.name, 0, len(replacement), 0, replacement, entry.raw_name))[0] != event:
            raise ValueError(f"event data changed in {entry.name}")
        new_entries.append(Entry(entry.name, 0, len(replacement), 0, replacement, entry.raw_name))
    if used != set(edits):
        raise ValueError(f"missing/unknown edit IDs: {sorted(set(edits) - used)}")
    result = build_archive(Archive(archive.label, tuple(new_entries)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    print(f"wrote {output}: {len(used)} edited messages; events unchanged")


def export(archive: Path, table_path: Path, output: Path) -> None:
    table = font_table(table_path)
    rows = []
    errors = 0
    for entry in read_archive(archive).entries:
        _, block = decode_scene(entry)
        for index, raw in enumerate(messages(block)):
            try:
                parsed = segments(raw, table)
            except ValueError as exc:
                parsed = []
                error = str(exc)
                errors += 1
            else:
                error = None
            rows.append({"id": f"MAX2_SCN/{entry.name}/text/{index:03d}",
                         "scene": entry.name, "index": index,
                         "source": "".join(s.get("text", "") for s in parsed),
                         "raw_sha256": hashlib.sha256(raw).hexdigest(),
                         "raw": raw.hex(), "segments": parsed, "parse_error": error})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    print(f"exported {len(rows)} messages from {len(read_archive(archive).entries)} scenes to {output}; {errors} require command research")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("export")
    p.add_argument("archive", type=Path)
    p.add_argument("font_table", type=Path)
    p.add_argument("output", type=Path)
    p = sub.add_parser("apply")
    p.add_argument("archive", type=Path)
    p.add_argument("font_table", type=Path)
    p.add_argument("edits", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--max-run-glyphs", type=int, default=24,
                   help="24 is the observed line limit; larger values are experimental")
    args = parser.parse_args()
    if args.command == "export":
        export(args.archive, args.font_table, args.output)
    elif args.command == "apply":
        if args.max_run_glyphs < 1:
            parser.error("--max-run-glyphs must be positive")
        apply_edits(args.archive, args.font_table, args.edits, args.output,
                    args.max_run_glyphs)


if __name__ == "__main__":
    main()
