#!/usr/bin/env bash
# Rebuild an all-English HDI copy and run the static audits; never overwrite.
set -euo pipefail
cd "$(dirname "$0")/.."

name="${1:-all-english-$(date -u +%Y%m%dT%H%M%SZ)}"
python tools/build_live_patch.py \
  --manifest work/route_draft_manifest-v2.json \
  --context-map work/route_context-v1.json \
  --facts config/route_facts.json \
  --cache work/full_draft_cache.jsonl \
  --paginate --apostrophe-dot --preview-punctuation --split-long-words \
  --choice-line-wrap --opening-choice-overlay \
  --overrides examples/beta_opening_overrides.json \
  --overrides examples/typewriter_overrides.json \
  --overrides examples/kaede_conflict_overrides.json \
  --overrides examples/azusa_shout_overrides.json \
  --draft-selections examples/draft_selections.json \
  --allow-unbalanced-quotes --name "$name"

python tools/audit_layout.py work/messages.jsonl "build/$name-edits.json" "build/$name-layout.json"
python tools/audit_timing.py work/messages.jsonl "build/$name-edits.json" "build/$name-timing.json"
python tools/audit_full_demo.py \
  work/original-extract/KIZUATO/MAX2_SCN.PAK "build/$name.PAK" \
  work/messages.jsonl "build/$name-edits.json" "build/$name-report.json" \
  work/route_draft_manifest-v2.json work/route_context-v1.json config/route_facts.json \
  work/full_draft_cache.jsonl examples/draft_selections.json work/xlvns-src/kizfont.tbl \
  "build/$name-audit.json"
