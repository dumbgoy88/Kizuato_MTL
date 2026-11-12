#!/usr/bin/env bash
# Build a fresh all-English continuation probe from the hash-pinned original HDI.
set -euo pipefail
cd "$(dirname "$0")/.."

name="${1:-split-pages-$(date -u +%Y%m%dT%H%M%SZ)}"
intermediate="${name}-unsafe-intermediate"
bash tools/rebuild_all_english_demo.sh "$intermediate"
python tools/split_pages.py \
  work/original-extract/KIZUATO/MAX2_SCN.PAK \
  "build/$intermediate.PAK" "build/$intermediate-edits.json" \
  work/xlvns-src/kizfont.tbl "build/$name.PAK" "build/$name-split-report.json" \
  --allow-unreferenced
python tools/audit_split_pages.py \
  "build/$intermediate.PAK" "build/$name.PAK" "build/$intermediate-edits.json" \
  work/xlvns-src/kizfont.tbl "build/$name-split-audit.json"
python tools/hdi_copy.py 'Kizuato (J).hdi' "build/$name.hdi" \
  "build/$name.PAK" KIZUATO/MAX2_SCN.PAK
printf 'Continuation probe: build/%s.hdi\n' "$name"
printf 'The split report lists any unreferenced messages that still need engine research.\n'
