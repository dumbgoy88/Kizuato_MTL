#!/usr/bin/env python3
"""Heuristic review of source-linked PLaMo drafts; keep detailed output ignored.

Flags are leads for human review, not proof of mistranslation. The summary
prints counts only, so game text and model output stay out of Git logs.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path


JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
TOKEN_RE = re.compile(r"<\|[^\n]*?\|>|\[INST\]|\[/INST\]", re.I)
NUMBER_RE = re.compile(r"^\s*([0-9０-９])[.、．)）]?\s*")


def analyze(row: dict, glossary: dict[str, str]) -> list[str]:
    source = row["source_ja"]
    output = row["english_draft"] or ""
    flags = list(row["issues"])
    if JP_RE.search(output):
        flags.append("japanese_left_in_draft")
    if TOKEN_RE.search(output):
        flags.append("model_token_in_draft")
    if "\ufffd" in source or "\ufffd" in output:
        flags.append("replacement_character")
    if "\ufffc" in source or "\ufffc" in output:
        flags.append("object_replacement_character")
    if re.search(r"\bJoe\b", output, re.I) and "ジョー" in source:
        flags.append("joke_misread_as_joe")
    if len(source.strip()) >= 10 and len(output) > 8 * len(source):
        flags.append("extreme_expansion")
    if len(source.strip()) >= 20 and len(output) < len(source.strip()) // 4:
        flags.append("extreme_contraction")
    number = NUMBER_RE.match(source)
    if number:
        expected = str(int(number.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))))
        found = NUMBER_RE.match(output)
        if not found:
            flags.append("choice_number_missing")
        elif found.group(1) != expected:
            flags.append("choice_number_changed")
    for japanese, english in glossary.items():
        if japanese in source and not re.search(r"\b" + re.escape(english) + r"\b", output, re.I):
            flags.append("glossary_missing:" + english)
    return sorted(set(flags))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("glossary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; choose a new ignored filename")
    glossary = json.loads(args.glossary.read_text())
    rows = [json.loads(line) for line in args.snapshot.read_text().splitlines()]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate review ID")
    output = [{"id": row["id"], "source_sha256": row["source_sha256"],
               "flags": analyze(row, glossary)} for row in rows]
    counts = collections.Counter(flag for row in output for flag in row["flags"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"reviewed": len(output), "flag_counts": dict(counts),
                                       "rows": output}, indent=2) + "\n")
    print(json.dumps({"reviewed": len(output), "flag_counts": dict(counts)}))


if __name__ == "__main__":
    main()
