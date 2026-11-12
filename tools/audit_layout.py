#!/usr/bin/env python3
"""Static 24-column/12-row layout audit of a prepared edit set.

The B9 pixel offset and page behavior follow the related XLVNS interpreter;
native Kizuato rendering is still unverified. Keep detailed output ignored.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

from compare_local import load_messages


def check(segments: list[dict], runs: list[str], columns: int, rows: int) -> list[str]:
    line = 0
    column = 0
    indent = 0
    run_at = 0
    issues: set[str] = set()

    def newline() -> None:
        nonlocal line, column
        line += 1
        column = indent

    for segment in segments:
        if segment["kind"] == "command":
            opcode = segment["opcode"]
            if opcode == "b0":
                newline()
            elif opcode == "b3":
                line = 0
                column = indent
            elif opcode == "b9":
                indent = math.ceil(int(segment["raw"][2:], 16) / 2)
                column = max(column, indent)
        else:
            if run_at >= len(runs):
                raise ValueError("fewer edit runs than original text slots")
            for char in runs[run_at]:
                if char == "\n":
                    newline()
                elif char == "\f":
                    line = 0
                    column = indent
                else:
                    if line >= rows:
                        issues.add("past_page_row_budget")
                    column += 1
                    if column > columns:
                        issues.add("past_column_budget")
            run_at += 1
    if run_at != len(runs):
        raise ValueError("more edit runs than original text slots")
    return sorted(issues)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    parser.add_argument("edits", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, default=24)
    parser.add_argument("--rows", type=int, default=12)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; choose a new ignored filename")
    if args.columns <= 0 or args.rows <= 0:
        parser.error("columns and rows must be positive")
    records = load_messages(args.messages)
    edits = json.loads(args.edits.read_text())
    if len({row["id"] for row in edits}) != len(edits):
        raise ValueError("duplicate edit ID")
    details = []
    counts: collections.Counter[str] = collections.Counter()
    for edit in edits:
        ident = edit["id"]
        if ident not in records or records[ident]["raw_sha256"] != edit["source_sha256"]:
            raise ValueError(f"source drift or unknown edit: {ident}")
        issues = check(records[ident]["segments"], edit["text_runs"], args.columns, args.rows)
        if issues:
            details.append({"id": ident, "issues": issues})
            counts.update(issues)
    result = {"edited": len(edits), "flagged": len(details),
              "issue_counts": dict(counts), "details": details}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "details"}))


if __name__ == "__main__":
    main()
