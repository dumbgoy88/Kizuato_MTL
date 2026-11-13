#!/usr/bin/env bash
# Build a fresh English HDI copy, including bounded main-story scene shards.
set -euo pipefail
cd "$(dirname "$0")/.."

name="${1:-split-pages-$(date -u +%Y%m%dT%H%M%SZ)}"
intermediate="${name}-unsafe-intermediate"
paginated="${name}-pre-shard"
bash tools/rebuild_all_english_demo.sh "$intermediate"
python tools/split_pages.py \
  work/original-extract/KIZUATO/MAX2_SCN.PAK \
  "build/$intermediate.PAK" "build/$intermediate-edits.json" \
  work/xlvns-src/kizfont.tbl "build/$paginated.PAK" "build/$name-split-report.json" \
  --allow-unreferenced
python tools/audit_split_pages.py \
  "build/$intermediate.PAK" "build/$paginated.PAK" "build/$intermediate-edits.json" \
  work/xlvns-src/kizfont.tbl "build/$name-split-audit.json"
source_hash="$(sha256sum "build/$paginated.PAK" | cut -d' ' -f1)"
python tools/shard_main_scenes.py \
  "build/$paginated.PAK" "build/$name.PAK" "build/$name-shard-report.json" \
  --expected-sha256 "$source_hash" --capacity 16000
python tools/hdi_copy.py 'Kizuato (J).hdi' "build/$name.hdi" \
  "build/$name.PAK" KIZUATO/MAX2_SCN.PAK
printf 'Sharded test image: build/%s.hdi\n' "$name"
printf 'Review the split and shard reports for remaining exceptions.\n'
