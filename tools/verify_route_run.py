#!/usr/bin/env python3
"""Check a route-aware PLaMo manifest before an overnight run; no model calls."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from compare_local import ORIGINAL_SCN_SHA256, load_messages, prompt_for
from route_context import SCOPE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    parser.add_argument("graph", type=Path)
    parser.add_argument("context", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("facts", type=Path)
    args = parser.parse_args()
    records = load_messages(args.messages)
    graph = json.loads(args.graph.read_text())
    context = json.loads(args.context.read_text())
    manifest = json.loads(args.manifest.read_text())
    facts = json.loads(args.facts.read_text())["facts"]
    if (graph["source_sha256"] != ORIGINAL_SCN_SHA256 or
            context["source_sha256"] != ORIGINAL_SCN_SHA256 or
            manifest["source_archive_sha256"] != ORIGINAL_SCN_SHA256):
        raise ValueError("source archive revision mismatch")
    if context["scope"] != SCOPE or manifest["context_scope"] != SCOPE:
        raise ValueError("route context scope mismatch")
    samples = manifest["samples"]
    expected_count = sum(not row["parse_error"] and bool(row["source"].strip())
                         for row in records.values())
    if len(samples) != expected_count or len({row["id"] for row in samples}) != len(samples):
        raise ValueError("unexpected sample count or duplicate IDs")
    for fact in facts:
        if not fact.get("enabled"):
            continue
        anchor = fact.get("available_after")
        if (anchor not in records or not fact.get("source", "").startswith("P98 ") or
                anchor.split("/")[1] not in fact["source"] or not fact.get("trigger_terms")):
            raise ValueError(f"unverified route fact anchor: {fact.get('id')}")
    allowed = {key: set(value) for key, value in context["context_ids"].items()}
    for scene in graph["scenes"]:
        for block in scene["blocks"]:
            for command in block["commands"]:
                if "choice" not in command:
                    continue
                options = [f"MAX2_SCN/{scene['scene']}/text/{item['message']:03d}"
                           for item in command["choice"]["options"]]
                for option in options:
                    if (set(options) - {option}) & allowed.get(option, set()):
                        raise ValueError(f"sibling option leaked into context: {option}")
    for scene, included, excluded in (("002", "016", ("017", "018")),
                                      ("003", "017", ("016", "018")),
                                      ("004", "018", ("016", "017"))):
        prior = allowed[f"MAX2_SCN/{scene}.SCN/text/000"]
        if f"MAX2_SCN/001.SCN/text/{included}" not in prior or any(
                f"MAX2_SCN/001.SCN/text/{other}" in prior for other in excluded):
            raise ValueError(f"first-choice branch isolation failed: {scene}")
    cross = 0
    with_context = 0
    fact_hits: collections.Counter[str] = collections.Counter()
    glossary_hits = 0
    longest = (0, "")
    for row in samples:
        key = row["id"]
        if key not in records or row["source_sha256"] != records[key]["raw_sha256"]:
            raise ValueError(f"source mismatch: {key}")
        prior = row["context_ids"]
        if len(prior) > 5 or key in prior or any(item not in allowed.get(key, set()) for item in prior):
            raise ValueError(f"unsafe selected context: {key}")
        if prior:
            with_context += 1
        if any(item.split('/')[1] != key.split('/')[1] for item in prior):
            cross += 1
        prompt = prompt_for(row, records, manifest["glossary"], {}, allowed, facts)
        if len(prompt) > longest[0]:
            longest = len(prompt), key
        if "<|plamo:tag|>glossary" in prompt:
            glossary_hits += 1
        for fact in facts:
            if fact.get("enabled") and fact["note"] in prompt:
                fact_hits[fact["id"]] += 1
    print(json.dumps({"samples": len(samples), "with_prior_context": with_context,
                      "with_cross_scene_selected_context": cross,
                      "with_glossary": glossary_hits, "fact_hits": dict(fact_hits),
                      "longest_prompt_characters": longest[0], "longest_prompt_id": longest[1]},
                     indent=2))


if __name__ == "__main__":
    main()
