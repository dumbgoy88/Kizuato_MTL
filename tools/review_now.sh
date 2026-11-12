#!/usr/bin/env bash
# Read-only snapshot of a live PLaMo draft cache.
set -euo pipefail
cd "$(dirname "$0")/.."
model="${KIZUATO_MODEL_PATH:-models/plamo-3-translate-8b-Q4_K_M.gguf}"
if [[ "${1:-}" == route ]]; then
  manifest='work/route_draft_manifest-v2.json'
  context='work/route_context-v1.json'
  facts='config/route_facts.json'
  prefix='route-review'
else
  manifest='work/full_draft_manifest.json'
  context='work/common_context.json'
  facts='config/story_facts.json'
  prefix='review'
fi
snapshot="work/$prefix-$(date -u +%Y%m%dT%H%M%SZ)-$$.jsonl"
python tools/review_drafts.py work/messages.jsonl "$manifest" \
  "$context" "$facts" "$model" \
  work/full_draft_cache.jsonl "$snapshot"
