#!/usr/bin/env python3
"""Build a disposable HDI copy from currently cached PLaMo drafts.

Never truncates text. Drafts that cannot fit or encode remain Japanese and are
listed in a report. Existing story commands and event blocks stay unchanged.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from compare_local import ORIGINAL_SCN_SHA256, PROMPT_REVISION, load_messages, prompt_for, sha256
from audit_layout import check as check_layout
from hdi_copy import EXPECTED_SHA256 as ORIGINAL_HDI_SHA256
from leafpack_pc98 import decode_scene, read_archive
from review_drafts import cache_successes, read_cache
from scenes import ENGLISH_CODES, encode_english, encode_paged_english, messages

ROOT = Path(__file__).resolve().parent.parent
MODEL = Path(os.environ.get("KIZUATO_MODEL_PATH", ROOT / "models/plamo-3-translate-8b-Q4_K_M.gguf"))


def preview_punctuation(value: str) -> tuple[str, list[str]]:
    """Render unsupported punctuation with existing glyphs for a preview.

    These choices need editorial review. Alphabetic and numeric tokens must
    remain byte-for-byte the same; no words are shortened or dropped.
    """
    def fold_latin(text: str) -> str:
        out = []
        for char in text:
            if unicodedata.name(char, "").startswith("LATIN"):
                out.extend(piece for piece in unicodedata.normalize("NFKD", char)
                           if not unicodedata.combining(piece))
            else:
                out.append(char)
        return "".join(out)

    def latin_tokens(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9]+", fold_latin(text))

    original_tokens = latin_tokens(value)
    changes = []
    quoted = re.sub(r"‘([^‘’\n]+)’", lambda match: "「" + match.group(1) + "」", value)
    if quoted != value:
        value = quoted
        changes.append("single_quotes_to_corner_quotes")
    accented = fold_latin(value)
    if accented != value:
        value = accented
        changes.append("latin_accents_to_ascii")
    if "ー" in value or "ッ" in value:
        value = value.replace("ー", "〜").replace("ッ", "!")
        changes.append("japanese_drawl_marks_to_native_punctuation")
    if "~" in value:
        value = value.replace("~", "〜")
        changes.append("tilde_to_native_wave_dash")
    if ";" in value:
        value = value.replace(";", ".")
        changes.append("semicolon_to_period")
    new_value = re.sub(r"(?<=[A-Za-z]):(?=\s|$)", " − ", value)
    if new_value != value:
        value = new_value
        changes.append("explanatory_colon_to_dash")
    new_value = re.sub(r"(?<=\d):(?=\d{2}\b)", ".", value)
    if new_value != value:
        value = new_value
        changes.append("clock_colon_to_period")
    if "*" in value:
        new_value = re.sub(r"(?<!\*)(\*{1,2})([^*\n]+?)\1(?!\*)",
                           lambda match: "「" + match.group(2) + "」", value)
        if new_value != value:
            value = new_value
            changes.append("paired_emphasis_to_corner_quotes")
    if latin_tokens(value) != original_tokens:
        raise AssertionError("preview punctuation changed words or numbers")
    return value, changes


def language_neutral(source: str) -> bool:
    """Source has only spacing/punctuation/symbols, with no letters or numbers."""
    return bool(source.strip()) and not any(unicodedata.category(char)[0] in ("L", "N")
                                            for char in source)


def normalize(value: str, source: str, apostrophe_dot: bool = False,
              allow_unbalanced_quotes: bool = False) -> str:
    replacements = {"“": "「", "”": "」", "-": "−", "–": "−", "—": "−",
                    "(": "（", ")": "）", "\u3000": " "}
    value = "".join(replacements.get(char, char) for char in value)
    # A few contractions expand without choosing between different meanings.
    expansions = {"I'M": "I AM", "WE'RE": "WE ARE", "YOU'RE": "YOU ARE",
                  "THEY'RE": "THEY ARE", "DON'T": "DO NOT", "DOESN'T": "DOES NOT",
                  "DIDN'T": "DID NOT", "CAN'T": "CANNOT", "WON'T": "WILL NOT",
                  "ISN'T": "IS NOT", "AREN'T": "ARE NOT", "WASN'T": "WAS NOT",
                  "WEREN'T": "WERE NOT", "COULDN'T": "COULD NOT",
                  "WOULDN'T": "WOULD NOT", "SHOULDN'T": "SHOULD NOT",
                  "HAVEN'T": "HAVE NOT", "HASN'T": "HAS NOT", "HADN'T": "HAD NOT",
                  "LET'S": "LET US"}
    value = value.upper().replace("’", "'")
    for short, expanded in expansions.items():
        value = re.sub(r"\b" + re.escape(short) + r"\b", expanded, value)
    if "'" in value:
        if apostrophe_dot:
            value = value.replace("'", "・")
        else:
            raise ValueError("apostrophe needs human wording review")
    if value.count('"') % 2 and not allow_unbalanced_quotes:
        raise ValueError("unbalanced quotation marks")
    opening = True
    out = []
    for char in value:
        if char == '"':
            out.append("「" if opening else "」")
            opening = not opening
        else:
            out.append(char)
    value = " ".join("".join(out).split())
    choice = re.match(r"^([０-９])、", source)
    if choice:
        number = str(ord(choice.group(1)) - ord("０"))
        other = re.match(r"^([0-9])[.、．)）]?\s*", value)
        if other:
            if other.group(1) != number:
                raise ValueError("choice number differs from Japanese source")
            value = number + ". " + value[other.end():]
        else:
            value = number + ". " + value
    if not value:
        raise ValueError("empty output")
    unknown = sorted(set(value) - set(ENGLISH_CODES))
    if unknown:
        raise ValueError("unsupported glyphs: " + "".join(unknown))
    return value


def split_runs(value: str, slots: int, width: int) -> list[str]:
    if slots < 1:
        raise ValueError("message has no text slots")
    words = value.split(" ")
    if any(len(word) > width for word in words):
        raise ValueError("a word exceeds run width")
    lines: list[list[str]] = []
    current: list[str] = []
    for word in words:
        proposed = " ".join(current + [word])
        if current and len(proposed) > width:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    if len(lines) > slots:
        raise ValueError(f"needs {len(lines)} runs; source has {slots}")
    while len(lines) < slots:
        options = [(len(" ".join(line)), index) for index, line in enumerate(lines) if len(line) > 1]
        if not options:
            raise ValueError(f"needs at least {slots} words for the source's text slots")
        _, index = max(options)
        line = lines[index]
        midpoint = min(range(1, len(line)), key=lambda at: abs(len(" ".join(line[:at])) - len(" ".join(line[at:]))))
        lines[index:index + 1] = [line[:midpoint], line[midpoint:]]
    result = [" ".join(line) for line in lines]
    if " ".join(result) != value:
        raise AssertionError("line fitting changed the English text")
    return result


def paginate_runs(value: str, source_segments: list[dict], rows_per_page: int = 12,
                  split_long_words: bool = False) -> list[str]:
    """Keep every word, using native B0 lines and B3 page waits as needed.

    The 12-row budget follows the visible limit in the native PC-98 emulator:
    row 13 was clipped in the opening passage. Page continuation still needs
    emulator verification.
    """
    slots = sum(part["kind"] == "text" for part in source_segments)
    distributed = split_runs(value, slots, max(24, len(value)))
    result = []
    row = col = indent = 0
    for segment in source_segments:
        if segment["kind"] == "command":
            if segment["opcode"] == "b0":
                row += 1
                col = indent
            elif segment["opcode"] == "b3":
                row = 0
                col = indent
            elif segment["opcode"] == "b9":
                indent = math.ceil(int(segment["raw"][2:], 16) / 2)
                if indent >= 24:
                    raise ValueError("B9 indent leaves no text columns")
                col = max(col, indent)
            continue
        words = distributed[len(result)].split(" ")
        encoded = []
        def next_line() -> None:
            nonlocal row, col
            row += 1
            col = indent
            encoded.append("\f" if row >= rows_per_page else "\n")
            if row >= rows_per_page:
                row = 0
        for word in words:
            if len(word) > 24 - indent:
                if not split_long_words:
                    raise ValueError("a word exceeds the 24-glyph line width")
                if col > indent or row >= rows_per_page:
                    next_line()
                remaining = word
                while remaining:
                    take = 24 - indent
                    chunk, remaining = remaining[:take], remaining[take:]
                    encoded.append(chunk)
                    col = indent + len(chunk)
                    if remaining:
                        next_line()
                continue
            separator = " " if col > indent else ""
            if col + len(separator) + len(word) > 24:
                next_line()
                separator = ""
            elif row >= rows_per_page:
                encoded.append("\f")
                row = 0
                col = indent
                separator = ""
            encoded.append(separator + word)
            col += len(separator) + len(word)
        result.append("".join(encoded))
    if re.sub(r"[ \n\f]", "", "".join(result)) != value.replace(" ", ""):
        raise AssertionError("pagination changed English characters")
    return result


def enforce_page_rows(source_segments: list[dict], runs: list[str], rows_per_page: int) -> list[str]:
    """Check the *combined* original/new command stream and page before row overflow.

    This independent pass catches drift at boundaries between source B0 commands
    and inserted line breaks. It adds only B3 markers and preserves every glyph.
    """
    row = 0
    run_at = 0
    fixed = []
    for segment in source_segments:
        if segment["kind"] == "command":
            if segment["opcode"] == "b0":
                row += 1
            elif segment["opcode"] == "b3":
                row = 0
            continue
        out = []
        for char in runs[run_at]:
            if char == "\n":
                row += 1
            elif char == "\f":
                row = 0
            elif row >= rows_per_page:
                out.append("\f")
                row = 0
            out.append(char)
        fixed.append("".join(out))
        run_at += 1
    if run_at != len(runs) or [x.replace("\f", "") for x in fixed] != [x.replace("\f", "") for x in runs]:
        raise AssertionError("page-row enforcement changed English glyphs or run count")
    return fixed


def choice_group_max_row(records: dict, edits: dict, ids: list[str]) -> int:
    """Estimate the occupied row while a prompt and its options render in order."""
    row = 0
    maximum = -1
    for ident in ids:
        source = records[ident]["segments"]
        runs = edits[ident]["text_runs"] if ident in edits else [part["text"] for part in source if part["kind"] == "text"]
        run_at = 0
        for part in source:
            if part["kind"] == "command":
                if part["opcode"] == "b0":
                    row += 1
                elif part["opcode"] == "b3":
                    row = 0
                continue
            for char in runs[run_at]:
                if char == "\n":
                    row += 1
                elif char == "\f":
                    row = 0
                else:
                    maximum = max(maximum, row)
            run_at += 1
    return maximum


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-run-glyphs", type=int, default=24,
                        help="observed safe limit is 24; larger values are experimental previews")
    parser.add_argument("--paginate", action="store_true",
                        help="experimental: insert native line/page commands to preserve full drafts")
    parser.add_argument("--apostrophe-dot", action="store_true",
                        help="experimental: show remaining apostrophes as native middle dots")
    parser.add_argument("--preview-punctuation", action="store_true",
                        help="experimental visible substitutions for tilde, semicolon, colon, and paired emphasis")
    parser.add_argument("--split-long-words", action="store_true",
                        help="experimental page/line breaks within words longer than 24 glyphs; preserves every character")
    parser.add_argument("--choice-line-wrap", action="store_true",
                        help="experimental B0-only wrapping inside choice text; selection/highlight unverified")
    parser.add_argument("--opening-choice-overlay", action="store_true",
                        help="use the three explicit provisional English choice edits in examples/opening_en.json")
    parser.add_argument("--overrides", type=Path, action="append",
                        help="explicit JSON edits; may repeat for separate reviewed batches")
    parser.add_argument("--skip-static-layout-flags", action="store_true",
                        help="leave drafts Japanese if the inferred 24-column/13-row layout audit flags them")
    parser.add_argument("--name", help="unique basename under build/; defaults to UTC timestamp")
    parser.add_argument("--manifest", type=Path, default=ROOT / "work/full_draft_manifest.json",
                        help="source-linked draft manifest; use route manifest for route-aware drafts")
    parser.add_argument("--context-map", type=Path, default=ROOT / "work/common_context.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "work/full_draft_cache.jsonl")
    parser.add_argument("--facts", type=Path, default=ROOT / "config/story_facts.json")
    parser.add_argument("--latest-cache-conflict", action="store_true",
                        help="diagnostic only: choose latest validated output when a prompt has conflicting responses")
    parser.add_argument("--allow-unbalanced-quotes", action="store_true",
                        help="diagnostic only: preserve unmatched model quote as an unmatched native corner quote")
    parser.add_argument("--draft-selections", type=Path,
                        help="source/output-hash-checked draft choices; contains IDs and hashes, not game text")
    args = parser.parse_args()
    if not 1 <= args.max_run_glyphs <= 255:
        parser.error("--max-run-glyphs must be between 1 and 255")
    if args.split_long_words and not args.paginate:
        parser.error("--split-long-words requires --paginate")
    if args.choice_line_wrap and not args.paginate:
        parser.error("--choice-line-wrap requires --paginate")
    name = args.name or "plamo-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        parser.error("--name must use letters, numbers, underscore, or hyphen")
    build = ROOT / "build"
    paths = {suffix: build / f"{name}{suffix}" for suffix in ("-edits.json", "-report.json", ".PAK", ".hdi")}
    if any(path.exists() for path in paths.values()):
        raise ValueError("output name already exists; choose a new --name")
    archive = ROOT / "work/original-extract/KIZUATO/MAX2_SCN.PAK"
    hdi = ROOT / "Kizuato (J).hdi"
    if sha256(archive) != ORIGINAL_SCN_SHA256 or sha256(hdi) != ORIGINAL_HDI_SHA256:
        raise ValueError("original archive or HDI has an unexpected revision")
    records = load_messages(ROOT / "work/messages.jsonl")
    expected = {}
    for entry in read_archive(archive).entries:
        _, block = decode_scene(entry)
        for index, raw in enumerate(messages(block)):
            expected[f"MAX2_SCN/{entry.name}/text/{index:03d}"] = hashlib.sha256(raw).hexdigest()
    if set(records) != set(expected) or any(records[key]["raw_sha256"] != digest for key, digest in expected.items()):
        raise ValueError("extracted records differ from the original archive")
    manifest = json.loads(args.manifest.read_text())
    context_map = json.loads(args.context_map.read_text())
    if manifest["source_archive_sha256"] != ORIGINAL_SCN_SHA256 or context_map["source_sha256"] != ORIGINAL_SCN_SHA256:
        raise ValueError("manifest/context source revision differs")
    if manifest["context_scope"] != context_map["scope"]:
        raise ValueError("manifest/context scope differs")
    graph = json.loads((ROOT / "work/event_graph.json").read_text())
    if graph["source_sha256"] != ORIGINAL_SCN_SHA256:
        raise ValueError("event graph source revision differs")
    choice_ids = set()
    choice_groups = []
    for scene in graph["scenes"]:
        for block in scene["blocks"]:
            for command in block["commands"]:
                if "choice" in command:
                    numbers = [command["choice"]["prompt"]]
                    numbers.extend(option["message"] for option in command["choice"]["options"])
                    ids = [f"MAX2_SCN/{scene['scene']}/text/{number:03d}" for number in numbers]
                    choice_ids.update(ids)
                    choice_groups.append(ids)
    allowed = {key: set(value) for key, value in context_map["context_ids"].items()}
    facts = json.loads(args.facts.read_text())["facts"]
    model_hash = sha256(MODEL)
    cache = read_cache(args.cache)
    selected_drafts = {}
    if args.draft_selections:
        choices = json.loads(args.draft_selections.read_text())
        if not isinstance(choices, list):
            raise ValueError("draft selections must be a JSON list")
        for choice in choices:
            if set(choice) != {"id", "source_sha256", "cache_key", "translation_sha256"}:
                raise ValueError("draft selection has missing or unsupported fields")
            ident = choice["id"]
            if ident in selected_drafts or ident not in records or choice["source_sha256"] != records[ident]["raw_sha256"]:
                raise ValueError(f"duplicate, unknown, or changed draft selection: {ident}")
            successes, invalid = cache_successes(cache.get(choice["cache_key"], []), records)
            if invalid:
                raise ValueError(f"source mismatch in selected cache key: {ident}")
            matches = {item["translation"] for item in successes
                       if hashlib.sha256(item["translation"].encode()).hexdigest() == choice["translation_sha256"]}
            if len(matches) != 1:
                raise ValueError(f"selected cached output is missing or ambiguous: {ident}")
            selected_drafts[ident] = matches.pop()
    edits = []
    report = []
    for row in manifest["samples"]:
        ident = row["id"]
        source = records[ident]
        prompt = prompt_for(row, records, manifest["glossary"], {}, allowed, facts)
        key = hashlib.sha256(json.dumps({"revision": PROMPT_REVISION, "model_sha256": model_hash,
                                         "max_tokens": row.get("max_tokens", 512), "prompt": prompt},
                                        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        successes, invalid = cache_successes(cache.get(key, []), records)
        reason = None
        punctuation_changes = []
        conflict_selected = False
        unbalanced_quote_preview = False
        selected = ident in selected_drafts
        if not successes and not selected:
            reason = "not_translated_yet"
        elif invalid and not selected:
            reason = "cache_source_mismatch"
        elif len({item["translation"] for item in successes}) != 1 and not args.latest_cache_conflict and not selected:
            reason = "conflicting_cached_outputs"
        else:
            try:
                conflict_selected = len({item["translation"] for item in successes}) != 1 and not selected
                draft = selected_drafts[ident] if selected else successes[-1]["translation"]
                if args.preview_punctuation:
                    draft, punctuation_changes = preview_punctuation(draft)
                unbalanced_quote_preview = draft.count('"') % 2 == 1
                value = normalize(draft, source["source"], args.apostrophe_dot,
                                  args.allow_unbalanced_quotes)
                count = sum(part["kind"] == "text" for part in source["segments"])
                paginated = args.paginate and (ident not in choice_ids or args.choice_line_wrap)
                if paginated:
                    # Choice text may gain B0 newlines, but never new B3 page
                    # waits. The static layout gate still applies below.
                    row_limit = 1000 if ident in choice_ids else 12
                    runs = paginate_runs(value, source["segments"], rows_per_page=row_limit,
                                         split_long_words=args.split_long_words)
                else:
                    indent = max((int(part["raw"][2:], 16) for part in source["segments"]
                                  if part["kind"] == "command" and part["opcode"] == "b9"), default=0)
                    estimated_width = args.max_run_glyphs - math.ceil(indent / 2)
                    runs = split_runs(value, count, estimated_width)
            except ValueError as exc:
                reason = str(exc)
            else:
                edits.append({"id": ident, "source_sha256": source["raw_sha256"],
                              "text_runs": runs,
                              **({"format": "paginated"} if paginated else {})})
        report.append({"id": ident, "state": "inserted" if reason is None else "left_japanese",
                       "reason": reason,
                       **({"preview_punctuation": punctuation_changes} if punctuation_changes else {}),
                       **({"selected_latest_conflicting_cache_output": True} if conflict_selected else {}),
                       **({"selected_hash_checked_draft": True} if selected and reason is None else {}),
                       **({"unbalanced_quote_preview": True} if unbalanced_quote_preview and reason is None else {})})
    overlay_ids = {f"MAX2_SCN/001.SCN/text/{index:03d}" for index in (16, 17, 18)}
    applied_overlays = []
    if args.opening_choice_overlay:
        example_rows = json.loads((ROOT / "examples/opening_en.json").read_text())
        overlays = {row["id"]: row for row in example_rows if row["id"] in overlay_ids}
        if set(overlays) != overlay_ids:
            raise ValueError("opening choice overlay is incomplete")
        edit_by_id = {row["id"]: row for row in edits}
        report_by_id = {row["id"]: row for row in report}
        for ident in sorted(overlay_ids):
            row = overlays[ident]
            source = records[ident]
            if row["source_sha256"] != source["raw_sha256"]:
                raise ValueError(f"opening choice source changed: {ident}")
            if len(row["text_runs"]) != sum(part["kind"] == "text" for part in source["segments"]):
                raise ValueError(f"opening choice run count changed: {ident}")
            for run in row["text_runs"]:
                encode_english(run, args.max_run_glyphs)
            edit_by_id[ident] = row
            report_by_id[ident] = {"id": ident, "state": "inserted", "reason": None,
                                   "source": "provisional_opening_choice_overlay"}
            applied_overlays.append(ident)
        edits = list(edit_by_id.values())
        report = [report_by_id[row["id"]] for row in manifest["samples"]]
    applied_manual_overrides = []
    if args.overrides:
        override_rows = []
        for path in args.overrides:
            batch = json.loads(path.read_text())
            if not isinstance(batch, list):
                raise ValueError(f"overrides must be a JSON list: {path}")
            override_rows.extend(batch)
        if len({row["id"] for row in override_rows}) != len(override_rows):
            raise ValueError("duplicate override ID across input files")
        edit_by_id = {row["id"]: row for row in edits}
        report_by_id = {row["id"]: row for row in report}
        for row in override_rows:
            if set(row) - {"id", "source_sha256", "text_runs", "format"}:
                raise ValueError("override contains unsupported fields")
            ident = row["id"]
            if ident not in report_by_id or row["source_sha256"] != records[ident]["raw_sha256"]:
                raise ValueError(f"unknown or changed override source: {ident}")
            if row.get("format") not in (None, "paginated"):
                raise ValueError(f"invalid override format: {ident}")
            if len(row["text_runs"]) != sum(part["kind"] == "text" for part in records[ident]["segments"]):
                raise ValueError(f"override run count differs from source: {ident}")
            for run in row["text_runs"]:
                if row.get("format") == "paginated":
                    encode_paged_english(run)
                else:
                    encode_english(run, args.max_run_glyphs)
            edit_by_id[ident] = row
            report_by_id[ident] = {"id": ident, "state": "inserted", "reason": None,
                                   "source": "explicit_manual_override"}
            applied_manual_overrides.append(ident)
        edits = list(edit_by_id.values())
        report = [report_by_id[row["id"]] for row in manifest["samples"]]
    # Explicit overrides replace formatter output, so enforce the native row
    # budget only after every source-hash-checked overlay has been applied.
    for edit in edits:
        if edit.get("format") == "paginated" and edit["id"] not in choice_ids:
            edit["text_runs"] = enforce_page_rows(records[edit["id"]]["segments"],
                                                   edit["text_runs"], 12)
    edit_by_id = {row["id"]: row for row in edits}
    split_choice_prompts = []
    for ids in choice_groups:
        if choice_group_max_row(records, edit_by_id, ids) < 12:
            continue
        prompt_id = ids[0]
        if prompt_id not in edit_by_id or edit_by_id[prompt_id].get("format") != "paginated":
            raise ValueError(f"choice prompt needs paginated edit: {prompt_id}")
        original_runs = edit_by_id[prompt_id]["text_runs"]
        for budget in range(12, 0, -1):
            candidate = enforce_page_rows(records[prompt_id]["segments"], original_runs, budget)
            edit_by_id[prompt_id]["text_runs"] = candidate
            if choice_group_max_row(records, edit_by_id, ids) < 12:
                if candidate == original_runs:
                    raise ValueError(f"choice group still overflows without new page: {prompt_id}")
                split_choice_prompts.append(prompt_id)
                break
        else:
            raise ValueError(f"choice group exceeds 12 rows after prompt split: {prompt_id}")
    skipped_layout = []
    if args.skip_static_layout_flags:
        kept = []
        report_by_id = {row["id"]: row for row in report}
        for edit in edits:
            ident = edit["id"]
            issues = check_layout(records[ident]["segments"], edit["text_runs"], 24, 12)
            if issues:
                skipped_layout.append(ident)
                report_by_id[ident] = {"id": ident, "state": "left_japanese",
                                       "reason": "static layout risk: " + ", ".join(issues)}
            else:
                kept.append(edit)
        edits = kept
        report = [report_by_id[row["id"]] for row in manifest["samples"]]
    if not edits:
        raise ValueError("no current PLaMo drafts fit; no image was created")
    for item in report:
        if item["state"] == "left_japanese" and language_neutral(records[item["id"]]["source"]):
            item["state"] = "kept_original_neutral"
    left_japanese = sum(item["state"] == "left_japanese" for item in report)
    kept_neutral = sum(item["state"] == "kept_original_neutral" for item in report)
    if len(edits) + left_japanese + kept_neutral != len(report):
        raise AssertionError("build report states do not cover every queued ID")
    build.mkdir(parents=True, exist_ok=True)
    paths["-edits.json"].write_text(json.dumps(edits, ensure_ascii=False, indent=2) + "\n")
    paths["-report.json"].write_text(json.dumps({"source_archive_sha256": ORIGINAL_SCN_SHA256,
                                                 "original_hdi_sha256": ORIGINAL_HDI_SHA256,
                                                 "manifest_sha256": sha256(args.manifest),
                                                 "context_map_sha256": sha256(args.context_map),
                                                 "facts_sha256": sha256(args.facts),
                                                 "max_run_glyphs": args.max_run_glyphs,
                                                 "pagination_experimental": args.paginate,
                                                 "apostrophe_dot_experimental": args.apostrophe_dot,
                                                 "preview_punctuation_experimental": args.preview_punctuation,
                                                 "split_long_words_experimental": args.split_long_words,
                                                 "choice_line_wrap_experimental": args.choice_line_wrap,
                                                 "latest_cache_conflict_experimental": args.latest_cache_conflict,
                                                 "allow_unbalanced_quotes_experimental": args.allow_unbalanced_quotes,
                                                 "draft_selections_sha256": sha256(args.draft_selections) if args.draft_selections else None,
                                                 "applied_overlays": applied_overlays,
                                                 "applied_manual_overrides": applied_manual_overrides,
                                                 "split_choice_prompts": sorted(set(split_choice_prompts)),
                                                 "skipped_static_layout": skipped_layout,
                                                 "inserted": len(edits),
                                                 "left_japanese": left_japanese,
                                                 "kept_original_neutral": kept_neutral,
                                                 "reasons": dict(collections.Counter(r["reason"] for r in report
                                                                                      if r["state"] == "left_japanese")),
                                                 "messages": report}, indent=2) + "\n")
    table = ROOT / "work/xlvns-src/kizfont.tbl"
    subprocess.run([sys.executable, str(ROOT / "tools/scenes.py"), "apply", str(archive), str(table),
                    str(paths["-edits.json"]), str(paths[".PAK"]),
                    "--max-run-glyphs", str(args.max_run_glyphs)], check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/hdi_copy.py"), str(hdi), str(paths[".hdi"]),
                    str(paths[".PAK"]), "KIZUATO/MAX2_SCN.PAK"], check=True)
    print(f"inserted {len(edits)} full drafts; left {left_japanese} messages in Japanese; "
          f"kept {kept_neutral} original punctuation-only messages")
    print(f"HDI copy: {paths['.hdi']}")
    print(f"report: {paths['-report.json']}")


if __name__ == "__main__":
    main()
