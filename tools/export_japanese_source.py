#!/usr/bin/env python3
"""Export decoded Japanese message text without engine bytes or commands.

The source is the hash-pinned extraction of the supplied original PC-98 scene
archive. Stable IDs and raw-message hashes align it with english_edits.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

MESSAGES_SHA256 = "d29b766245825546e2e7fa083fb005407a22b97e7ef8984e14ee7bb4a0e11650"
ENGLISH_SHA256 = "a1e846b6d25d4fc0d12ac2a5918a5d2451bd6d3b3269936be1ea2efb7d34a26b"
ID_RE = re.compile(r"MAX2_SCN/\d{3}\.SCN/text/\d{3}")
HASH_RE = re.compile(r"[0-9a-f]{64}")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extracted_messages", type=Path)
    parser.add_argument("english_edits", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve() in (args.extracted_messages.resolve(), args.english_edits.resolve()):
        parser.error("output must be new and distinct from inputs")
    source_data = args.extracted_messages.read_bytes()
    english_data = args.english_edits.read_bytes()
    if sha(source_data) != MESSAGES_SHA256 or sha(english_data) != ENGLISH_SHA256:
        raise ValueError("extraction or English edit hash differs from verified revision")
    rows = [json.loads(line) for line in source_data.splitlines()]
    edits = json.loads(english_data)
    if len(rows) != 3309 or len(edits) != 3264:
        raise ValueError("unexpected source or translation count")
    output = []
    by_id = {}
    for row in rows:
        ident, source_hash, japanese = row["id"], row["raw_sha256"], row["source"]
        if (not ID_RE.fullmatch(ident) or not HASH_RE.fullmatch(source_hash) or
                not isinstance(japanese, str) or row["parse_error"] or "\ufffd" in japanese or
                ident in by_id):
            raise ValueError(f"invalid extracted source record: {ident}")
        by_id[ident] = source_hash
        output.append({"id": ident, "source_sha256": source_hash, "japanese": japanese})
    for edit in edits:
        if by_id.get(edit["id"]) != edit["source_sha256"]:
            raise ValueError(f"English/source alignment differs: {edit['id']}")
    body = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(body, encoding="utf-8")
    readback = [json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines()]
    if readback != output:
        args.output.unlink(missing_ok=True)
        raise AssertionError("Japanese text export changed on readback")
    print(f"wrote {len(output)} Japanese text records; {len(edits)} English hashes matched")
    print(f"SHA-256 {sha(args.output.read_bytes())}")


if __name__ == "__main__":
    main()
