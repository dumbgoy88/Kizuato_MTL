#!/usr/bin/env python3
"""Translate an explicit, source-checked manifest through a local PLaMo server.

Source text, prompts, and outputs stay in ignored work/ files. Successful
requests are cached by exact prompt and model hash; failures can be retried.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from leafpack_pc98 import decode_scene, read_archive

PROMPT_REVISION = "pfml3-sample-v1"
STOP = ["<|plamo:tag|>", "<|plamo:bos|>"]
ORIGINAL_SCN_SHA256 = "beec74329493a72fcdb61c914539d3d210f0193d714fdc583189aec1e9a5cace"
OPENING_EVENT_SHA256 = "a1db450bf9cc4b41b37661948bd4b4fb7e62ee42b098aab02de80a6fac2ca3d2"
CONTEXT_SCOPES = {"same-event-block-common-prefix", "static-cross-scene-common-prefix-v1"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_messages(path: Path) -> dict[str, dict]:
    records = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row["id"] in records:
            raise ValueError(f"duplicated extracted ID: {row['id']}")
        records[row["id"]] = row
    return records


def model_text(item: dict, *, join_wrapped: bool = False, strip_choice_number: bool = False) -> str:
    if join_wrapped:
        runs = [segment["text"] for segment in item["segments"] if segment["kind"] == "text"]
        if len(runs) < 2:
            raise ValueError(f"no wrapped text runs to join: {item['id']}")
        value = runs[0] + "".join(run.lstrip("　") for run in runs[1:])
    else:
        value = item["source"]
    if strip_choice_number:
        value, count = re.subn(r"^[０-９]+[、．.]", "", value)
        if count != 1:
            raise ValueError(f"choice number not found: {item['id']}")
    return value


def verified_context_prefix(archive_path: Path) -> dict[str, set[int]]:
    """Prove the only context path currently admitted by this small runner.

    Scene 001 displays messages 0–14 in order, then its choice shows prompt
    15 before branching to mutually exclusive options 16–18. Do not use text
    from an option or a post-choice branch as prior context.
    """
    if sha256(archive_path) != ORIGINAL_SCN_SHA256:
        raise ValueError("unexpected original scene archive revision")
    archive = read_archive(archive_path)
    entry = next((item for item in archive.entries if item.name == "001.SCN"), None)
    if entry is None:
        raise ValueError("001.SCN absent from scene archive")
    event, _ = decode_scene(entry)
    if hashlib.sha256(event).hexdigest() != OPENING_EVENT_SHA256:
        raise ValueError("001.SCN event block differs from verified revision")
    displayed = b"".join(bytes((0x51, index)) for index in range(15))
    choice = bytes.fromhex("27 25 0f 03 10 00 11 04 12 08")
    if event[11:41] != displayed or event[41:51] != choice:
        raise ValueError("001.SCN common-prefix sequence differs from verified revision")
    return {"001.SCN": set(range(16))}


def prompt_for(row: dict, records: dict[str, dict], glossary: dict[str, str],
               context_prefix: dict[str, set[int]], allowed_ids: dict[str, set[str]] | None = None,
               facts: list[dict] | None = None) -> str:
    ident = row["id"]
    source = records[ident]
    if row.get("source_sha256") and row["source_sha256"] != source["raw_sha256"]:
        raise ValueError(f"source changed for {ident}")
    if source["parse_error"]:
        raise ValueError(f"opaque source message: {ident}")
    if not source["source"].strip():
        raise ValueError(f"no translatable source text: {ident}")
    parts = ["<|plamo:tag|>dataset<|plamo:msg|>translation"]
    context = []
    for context_id in row.get("context_ids", []):
        if context_id not in records:
            raise ValueError(f"unknown context ID: {context_id}")
        item = records[context_id]
        allowed = (context_id in allowed_ids.get(ident, set()) if allowed_ids is not None else
                   item["scene"] == source["scene"] and item["index"] < source["index"] and
                   item["index"] in context_prefix.get(source["scene"], set()))
        if not allowed:
            raise ValueError(f"context is outside a verified common prefix: {context_id}")
        if item["parse_error"]:
            raise ValueError(f"opaque context message: {context_id}")
        context.append(item["source"])
    current_text = model_text(source, join_wrapped=row.get("join_wrapped", False),
                              strip_choice_number=row.get("strip_choice_number", False))
    japanese_context = tuple(context)
    for fact in facts or []:
        prior_ids = (allowed_ids.get(ident, set()) if allowed_ids is not None
                     else set(row.get("context_ids", []))) if fact.get("release_from_verified_prior") else set(row.get("context_ids", []))
        terms = fact.get("trigger_terms", [])
        if (fact.get("enabled", False) and fact["available_after"] in prior_ids and
                (not terms or any(term in current_text or any(term in line for line in japanese_context)
                                  for term in terms))):
            context.append(fact["note"])
    voice_note = row.get("voice_note", "")
    if voice_note:
        context.append(voice_note)
    if context:
        parts.extend(("<|plamo:tag|>context<|plamo:msg|>", "\n".join(context)))
    relevant_glossary = {ja: en for ja, en in glossary.items()
                         if ja in current_text or any(ja in line for line in context)}
    if relevant_glossary:
        parts.append("<|plamo:tag|>glossary")
        for japanese, english in relevant_glossary.items():
            parts.append(f"<|plamo:index|>{japanese}<|plamo:item|>{english}")
    parts.extend(("<|plamo:tag|>input<|plamo:key|>lang<|plamo:val|>ja<|plamo:msg|>",
                  current_text,
                  "<|plamo:tag|>output<|plamo:key|>lang<|plamo:val|>en<|plamo:msg|>"))
    return "".join(parts)


def request_translation(url: str, prompt: str, max_tokens: int) -> tuple[str, dict]:
    body = json.dumps({"prompt": prompt, "temperature": 0, "max_tokens": max_tokens,
                       "stop": STOP}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url.rstrip("/") + "/v1/completions", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.load(response)
    choice = result["choices"][0]
    output = choice["text"].strip()
    if not output or any(token in output for token in STOP):
        raise ValueError("empty or malformed model output")
    return output, result.get("usage", {})


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    parser.add_argument("sample", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("cache", type=Path)
    parser.add_argument("--archive", type=Path, required=True,
                        help="unchanged original MAX2_SCN.PAK for context-path verification")
    parser.add_argument("--context-map", type=Path,
                        help="checked same-block map for a generated full draft manifest")
    parser.add_argument("--facts", type=Path,
                        help="stage-gated story facts; released only when anchor is proven prior context")
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-output", action="store_true", help="print each completed translation")
    parser.add_argument("--max-new", type=int, default=0, help="stop after this many uncached IDs; 0 means all")
    parser.add_argument("--stop-file", type=Path, help="stop between IDs when this file exists")
    args = parser.parse_args()
    if args.max_new < 0:
        parser.error("--max-new must be nonnegative")
    records = load_messages(args.messages)
    context_prefix = verified_context_prefix(args.archive) if not args.context_map else {}
    allowed_ids = None
    if args.context_map:
        if sha256(args.archive) != ORIGINAL_SCN_SHA256:
            raise ValueError("unexpected original scene archive revision")
        context_map = json.loads(args.context_map.read_text())
        if context_map["source_sha256"] != ORIGINAL_SCN_SHA256 or context_map["scope"] not in CONTEXT_SCOPES:
            raise ValueError("unexpected context map provenance/scope")
        allowed_ids = {key: set(value) for key, value in context_map["context_ids"].items()}
    facts = json.loads(args.facts.read_text())["facts"] if args.facts else []
    spec = json.loads(args.sample.read_text())
    if spec.get("source_archive_sha256") and spec["source_archive_sha256"] != ORIGINAL_SCN_SHA256:
        raise ValueError("manifest source archive differs from verified revision")
    rows = spec["samples"]
    if args.context_map and spec.get("context_scope") != context_map["scope"]:
        raise ValueError("manifest and context map scopes differ")
    if len({row["id"] for row in rows}) != len(rows):
        raise SystemExit("duplicate sample ID")
    model_hash = sha256(args.model)
    cached = {}
    if args.cache.exists():
        for line in args.cache.read_text().splitlines():
            item = json.loads(line)
            if item.get("status") == "ok":
                cached[item["cache_key"]] = item
    attempted = 0
    for index, row in enumerate(rows, 1):
        if args.stop_file and args.stop_file.exists():
            print(f"stop file found: {args.stop_file}; completed results remain cached", flush=True)
            break
        prompt = prompt_for(row, records, spec["glossary"], context_prefix, allowed_ids, facts)
        key = hashlib.sha256(json.dumps({"revision": PROMPT_REVISION,
                                          "model_sha256": model_hash,
                                          "max_tokens": row.get("max_tokens", 512),
                                          "prompt": prompt}, ensure_ascii=False,
                                         sort_keys=True).encode()).hexdigest()
        if key in cached:
            print(f"[{index}/{len(rows)}] cached: {row['id']}", flush=True)
            if args.show_output:
                print(f"  {cached[key]['translation']}", flush=True)
            continue
        if args.dry_run:
            print(f"[{index}/{len(rows)}] ready: {row['id']} ({len(prompt)} prompt characters)", flush=True)
            continue
        if args.max_new and attempted >= args.max_new:
            print(f"reached --max-new {args.max_new}; completed results remain cached", flush=True)
            break
        attempted += 1
        error = None
        for attempt in range(1, 4):
            started = time.monotonic()
            try:
                output, usage = request_translation(args.server, prompt, row.get("max_tokens", 512))
                append_jsonl(args.cache, {"status": "ok", "id": row["id"],
                                           "cache_key": key, "model_sha256": model_hash,
                                           "source_sha256": records[row["id"]]["raw_sha256"],
                                           "prompt_revision": PROMPT_REVISION,
                                           "translation": output, "usage": usage,
                                           "seconds": round(time.monotonic() - started, 3)})
                cached[key] = {"translation": output}
                print(f"[{index}/{len(rows)}] translated: {row['id']} ({time.monotonic() - started:.1f}s)", flush=True)
                if args.show_output:
                    print(f"  {output}", flush=True)
                error = None
                break
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
                error = str(exc)
                if attempt < 3:
                    time.sleep(2 ** attempt)
        if error:
            append_jsonl(args.cache, {"status": "error", "id": row["id"],
                                       "cache_key": key, "error": error})
            print(f"[{index}/{len(rows)}] failed: {row['id']}: {error}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped by Ctrl+C; completed results remain cached", flush=True)
        raise SystemExit(130)
