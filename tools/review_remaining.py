#!/usr/bin/env python3
"""Make an ignored, offline review page for actual Japanese fallbacks.

This reads the current diagnostic build report and source-linked draft snapshot.
It never changes the game or sends text to a model. Run again after each build.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

from compare_local import ORIGINAL_SCN_SHA256, load_messages
from review_drafts import cache_successes, read_cache

ROOT = Path(__file__).resolve().parent.parent
SENSITIVE_IDS = {"MAX2_SCN/157.SCN/text/005"}


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path,
                        default=ROOT / "build/choice-wrap-experiment-20261110-v6-report.json")
    parser.add_argument("--messages", type=Path, default=ROOT / "work/messages.jsonl")
    parser.add_argument("--review", type=Path,
                        default=ROOT / "work/review-20261110T121422Z-1589598.jsonl")
    parser.add_argument("--cache", type=Path, default=ROOT / "work/full_draft_cache.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "build/review-remaining.html")
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if report["source_archive_sha256"] != ORIGINAL_SCN_SHA256:
        raise ValueError("unexpected source archive in build report")
    records = load_messages(args.messages)
    reviews = {row["id"]: row for row in map(json.loads, args.review.read_text().splitlines())}
    cache = read_cache(args.cache)
    pending = [row for row in report["messages"] if row["state"] == "left_japanese"]
    if len(pending) != report["left_japanese"] or len({row["id"] for row in pending}) != len(pending):
        raise ValueError("report pending count or IDs differ")
    cards = []
    for item in pending:
        ident = item["id"]
        source = records[ident]
        draft = reviews[ident]
        if draft["source_sha256"] != source["raw_sha256"] or draft["source_ja"] != source["source"]:
            raise ValueError(f"source drift: {ident}")
        if ident in SENSITIVE_IDS:
            body = "<p>Source and draft hidden: sensitive passage. Review in the ignored source files if appropriate.</p>"
        else:
            candidates = []
            if draft.get("cache_key"):
                successes, invalid = cache_successes(cache.get(draft["cache_key"], []), records)
                if invalid:
                    raise ValueError(f"cache source mismatch: {ident}")
                candidates = list(dict.fromkeys(row["translation"] for row in successes))
            if not candidates and draft.get("english_draft"):
                candidates = [draft["english_draft"]]
            runs = "".join(f"<li>{escape(part['text'])}</li>" for part in source["segments"]
                           if part["kind"] == "text")
            options = "".join(f"<li><pre>{escape(value)}</pre></li>" for value in candidates)
            body = (f"<p><strong>Japanese source</strong></p><pre>{escape(source['source'])}</pre>"
                    f"<details><summary>Original text runs ({runs.count('<li>')})</summary><ol>{runs}</ol></details>"
                    f"<p><strong>PLaMo draft{' candidates' if len(candidates) != 1 else ''}</strong></p>"
                    f"<ol>{options}</ol>")
        anchor = hashlib.sha256(ident.encode()).hexdigest()[:10]
        cards.append((item["reason"],
                      f'<section id="id-{anchor}"><h2>{escape(ident)}</h2>'
                      f'<p class="reason">{escape(item["reason"])}</p>'
                      f'{body}<p class="hash">Source SHA-256: {escape(source["raw_sha256"])}</p></section>'))
    counts = {reason: sum(reason == row[0] for row in cards) for reason, _ in cards}
    summary = ", ".join(f"{count} {escape(reason)}" for reason, count in sorted(counts.items()))
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Kizuato remaining review</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;background:#f5f2e9;color:#222}}
section{{background:white;border:1px solid #bbb;border-radius:8px;margin:1rem 0;padding:1rem}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:1.1rem/1.6 sans-serif}}
.reason{{font-weight:bold;color:#71352b}}.hash{{font-size:.8rem;color:#666}}</style>
<h1>Kizuato remaining Japanese text</h1><p>{len(cards)} entries: {summary}.</p>
<p>This is an offline script review, not an emulator test. Scene order alone does not establish route order.
Choice layout and selection need separate on-screen checks. This page is generated from ignored local data; do not commit it.</p>
{''.join(card for _, card in cards)}</html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page)
    print(f"wrote {len(cards)} local review entries to {args.output}")


if __name__ == "__main__":
    main()
