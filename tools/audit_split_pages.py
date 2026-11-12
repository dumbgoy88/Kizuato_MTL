#!/usr/bin/env python3
"""Independently audit continuation-message insertion and event relocation."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from event_graph import parse_scene
from leafpack_pc98 import decode_scene, read_archive
from scenes import font_table, messages, segments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paginated", type=Path)
    parser.add_argument("split", type=Path)
    parser.add_argument("edits", type=Path)
    parser.add_argument("font_table", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("report exists")
    before = read_archive(args.paginated)
    after = read_archive(args.split)
    if [e.name for e in before.entries] != [e.name for e in after.entries]:
        raise ValueError("scene list changed")
    marker_counts = {row["id"]: sum(run.count("\f") for run in row["text_runs"])
                     for row in json.loads(args.edits.read_text())}
    table = font_table(args.font_table)
    totals = Counter()
    unresolved = []
    for old_entry, new_entry in zip(before.entries, after.entries):
        old_event, old_text = decode_scene(old_entry)
        new_event, new_text = decode_scene(new_entry)
        old_items, new_items = messages(old_text), messages(new_text)
        old_scene, new_scene = parse_scene(old_entry.name, old_event), parse_scene(new_entry.name, new_event)
        if len(old_scene["blocks"]) != len(new_scene["blocks"]):
            raise ValueError("event block count changed")
        calls: dict[int, set[tuple[int, ...]]] = {}
        preludes: dict[int, set[tuple[int, ...]]] = {}
        for old_block, new_block in zip(old_scene["blocks"], new_scene["blocks"]):
            old_cmds, new_cmds = old_block["commands"], new_block["commands"]
            cursor = 0
            positions = {}
            actual_commands = {}
            for command in old_cmds:
                entry_offset = new_cmds[cursor]["offset"]
                if command["opcode"] == "25":
                    prompt = command["choice"]["prompt"]
                    ident = f"MAX2_SCN/{old_entry.name}/text/{prompt:03d}"
                    needed = marker_counts.get(ident, 0)
                    prefix = new_cmds[cursor:cursor + needed]
                    if len(prefix) != needed or any(x["opcode"] != "51" for x in prefix):
                        raise ValueError(f"missing choice prelude call: {ident}")
                    preludes.setdefault(prompt, set()).add(tuple(x["message"] for x in prefix))
                    cursor += needed
                current = new_cmds[cursor]
                if current["opcode"] != command["opcode"]:
                    raise ValueError("original event opcode changed")
                if command["opcode"] not in ("41", "42", "25") and current["raw"] != command["raw"]:
                    raise ValueError("original event command changed")
                positions[command["offset"]] = entry_offset
                actual_commands[command["offset"]] = current
                cursor += 1
                if command["opcode"] == "51":
                    ident = f"MAX2_SCN/{old_entry.name}/text/{command['message']:03d}"
                    needed = marker_counts.get(ident, 0)
                    extra = new_cmds[cursor:cursor + needed]
                    if any(x["opcode"] != "51" for x in extra) or len(extra) != needed:
                        raise ValueError(f"missing continuation call: {ident}")
                    sequence = tuple(x["message"] for x in extra)
                    calls.setdefault(command["message"], set()).add(sequence)
                    cursor += needed
            positions[old_block["end"]] = new_block["end"]
            if cursor != len(new_cmds):
                raise ValueError("extra unexpected event calls")
            for old_command in old_cmds:
                current = actual_commands[old_command["offset"]]
                if "conditional" in old_command:
                    if current["conditional"]["target"] != positions[old_command["conditional"]["target"]]:
                        raise ValueError("conditional branch target changed")
                if "choice" in old_command:
                    old_choice, new_choice = old_command["choice"], current["choice"]
                    if old_choice["prompt"] != new_choice["prompt"] or len(old_choice["options"]) != len(new_choice["options"]):
                        raise ValueError("choice changed")
                    for a, b in zip(old_choice["options"], new_choice["options"]):
                        if a["message"] != b["message"] or positions[a["target"]] != b["target"]:
                            raise ValueError("choice branch target changed")
        for index, old_raw in enumerate(old_items):
            ident = f"MAX2_SCN/{old_entry.name}/text/{index:03d}"
            needed = marker_counts.get(ident, 0)
            sequences = calls.get(index, set())
            prompt_sequences = preludes.get(index, set())
            if needed and not sequences and not prompt_sequences:
                unresolved.append(ident)
                if new_items[index] != old_raw:
                    raise ValueError("unreferenced message changed")
                continue
            if len(sequences) > 1 or len(prompt_sequences) > 1 or (sequences and prompt_sequences):
                raise ValueError("same source call uses different continuations")
            extra = next(iter(sequences or prompt_sequences), ())
            if len(extra) != needed:
                raise ValueError("continuation count mismatch")
            pages = ([new_items[i] for i in extra] + [new_items[index]]) if prompt_sequences else ([new_items[index]] + [new_items[i] for i in extra])
            joined = b"".join(page[:-1] for page in pages[:-1]) + pages[-1]
            if joined != old_raw:
                raise ValueError(f"page reconstruction changed bytes: {ident}")
            totals["split_messages"] += bool(needed)
            totals["continuation_messages"] += needed
        for index, raw in enumerate(new_items):
            parts = segments(raw, table)
            for at, part in enumerate(parts):
                if part.get("opcode") == "b3" and any(x["kind"] == "text" for x in parts[at + 1:]):
                    if old_entry.name != "201.SCN":
                        raise ValueError(f"mid-message B3 remains: {old_entry.name}/{index}")
                    totals["bonus_mid_message_b3"] += 1
        for block in new_scene["blocks"]:
            for command in block["commands"]:
                if "choice" not in command:
                    continue
                ids = [command["choice"]["prompt"]] + [option["message"] for option in command["choice"]["options"]]
                row = column = indent = 0
                for index in ids:
                    for part in segments(new_items[index], table):
                        if part["kind"] == "command":
                            if part["opcode"] == "b0":
                                row += 1
                                column = indent
                            elif part["opcode"] == "b3":
                                row = 0
                                column = indent
                            elif part["opcode"] == "b9":
                                indent = math.ceil(int(part["raw"][2:], 16) / 2)
                                column = max(column, indent)
                        else:
                            for char in part["text"]:
                                if row >= 12 or column + 1 > 24:
                                    raise ValueError(f"choice group exceeds 24x12: {old_entry.name} {ids}")
                                column += 1
                totals["choice_groups_within_24x12"] += 1
        totals["scenes"] += 1
        totals["messages"] += len(new_items)
    result = {**totals, "unreferenced_unsplit": unresolved}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
