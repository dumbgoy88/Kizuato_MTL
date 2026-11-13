#!/usr/bin/env python3
"""Compare original and rebuilt PC-98 scene sizes without running the game.

The default 32 KiB boundary is a diagnostic threshold, not a proven engine
limit. This tool reports crossings and never edits either archive.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from leafpack_pc98 import decode_scene, read_archive


def measurements(path: Path) -> dict[str, dict[str, int]]:
    result = {}
    for entry in read_archive(path).entries:
        event, text = decode_scene(entry)
        result[entry.name] = {
            "packed": entry.length,
            "event": len(event),
            "text": len(text),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("rebuilt", type=Path)
    parser.add_argument("--threshold", type=int, default=32768)
    parser.add_argument("--output", type=Path, help="optional JSON report (must not exist)")
    args = parser.parse_args()
    if args.threshold < 1:
        parser.error("threshold must be positive")
    if args.output and args.output.exists():
        parser.error("output exists")
    original = measurements(args.original)
    rebuilt = measurements(args.rebuilt)
    if original.keys() != rebuilt.keys():
        raise ValueError("scene names differ between archives")
    original_max = {key: max(sizes[key] for sizes in original.values())
                    for key in ("packed", "event", "text")}
    over_original_max = [name for name, sizes in rebuilt.items()
                         if any(sizes[key] > original_max[key]
                                for key in ("packed", "event", "text"))]
    rows = []
    for name in original:
        old, new = original[name], rebuilt[name]
        crossings = [key for key in ("packed", "event", "text")
                     if old[key] < args.threshold <= new[key]]
        if crossings:
            rows.append({"scene": name, "original": old, "rebuilt": new,
                         "crossings": crossings})
    rows.sort(key=lambda row: max(row["rebuilt"].values()), reverse=True)
    report = {
        "original": str(args.original), "rebuilt": str(args.rebuilt),
        "threshold": args.threshold,
        "threshold_is_verified_engine_limit": False,
        "scene_count": len(original),
        "original_max": original_max,
        "rebuilt_over_original_max": over_original_max,
        "original_over_threshold": sum(any(n >= args.threshold for n in sizes.values())
                                       for sizes in original.values()),
        "rebuilt_over_threshold": sum(any(n >= args.threshold for n in sizes.values())
                                      for sizes in rebuilt.values()),
        "crossings": rows,
    }
    print(f"Scenes: {len(original)}; threshold: {args.threshold} bytes (hypothesis)")
    print(f"Original maxima: packed {original_max['packed']}, event {original_max['event']}, "
          f"text {original_max['text']}; rebuilt scenes over any original maximum: "
          f"{len(over_original_max)}")
    print(f"Over threshold: original {report['original_over_threshold']}, "
          f"rebuilt {report['rebuilt_over_threshold']}; crossings {len(rows)}")
    for row in rows:
        old, new = row["original"], row["rebuilt"]
        print(f"{row['scene']}: packed {old['packed']}->{new['packed']}, "
              f"event {old['event']}->{new['event']}, "
              f"text {old['text']}->{new['text']} ({','.join(row['crossings'])})")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
