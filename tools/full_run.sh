#!/usr/bin/env bash
# Local, foreground PLaMo first-pass draft run. All generated files stay ignored.
set -euo pipefail
cd "$(dirname "$0")/.."

model="${KIZUATO_MODEL_PATH:-models/plamo-3-translate-8b-Q4_K_M.gguf}"
archive='work/original-extract/KIZUATO/MAX2_SCN.PAK'
manifest='work/full_draft_manifest.json'
context_map='work/common_context.json'
facts='config/story_facts.json'
cache='work/full_draft_cache.jsonl'
stop_file='work/stop-plamo-full'
live_log='work/plamo-full-live.log'

case "${1:-}" in
  prepare-route)
    test -f "$archive" || { printf 'Missing original extracted archive. See README.md\n' >&2; exit 1; }
    temp_dir=$(mktemp -d work/route-prep.XXXXXX)
    trap 'rm -rf "$temp_dir"' EXIT
    python tools/event_graph.py "$archive" "$temp_dir/graph.json"
    python tools/common_context.py "$temp_dir/graph.json" "$temp_dir/local.json"
    python tools/route_context.py "$temp_dir/graph.json" "$temp_dir/local.json" "$temp_dir/route.json"
    python tools/build_batch.py work/messages.jsonl "$archive" "$temp_dir/route.json" config/glossary.json "$temp_dir/manifest.json"
    python tools/verify_route_run.py work/messages.jsonl "$temp_dir/graph.json" "$temp_dir/route.json" "$temp_dir/manifest.json" config/route_facts.json
    mv "$temp_dir/graph.json" work/event_graph-route-v1.json
    mv "$temp_dir/local.json" work/local_context-route-v1.json
    mv "$temp_dir/route.json" work/route_context-v1.json
    mv "$temp_dir/manifest.json" work/route_draft_manifest-v2.json
    printf 'Route-aware run prepared. Start: bash tools/full_run.sh route\n'
    ;;
  stop)
    touch "$stop_file"
    printf 'Stop requested. The current ID will finish before the run exits.\n'
    ;;
  run|route)
    mode=$1
    shift
    exec 9>work/plamo-run.lock
    flock -n 9 || { printf 'Another PLaMo run is already active. Use stop or wait for it to finish.\n' >&2; exit 1; }
    if [[ "$mode" == route ]]; then
      manifest='work/route_draft_manifest-v2.json'
      context_map='work/route_context-v1.json'
      facts='config/route_facts.json'
      live_log='work/plamo-route-live.log'
      test -f "$manifest" && test -f "$context_map" || {
        printf 'Route run not prepared. Run: bash tools/full_run.sh prepare-route\n' >&2; exit 1;
      }
      python tools/verify_route_run.py work/messages.jsonl work/event_graph-route-v1.json "$context_map" "$manifest" "$facts"
    fi
    test -f "$model" || { printf 'Missing model: %s\n' "$model" >&2; exit 1; }
    test -x work/llama-build/bin/llama-server || { printf 'Missing compatible llama-server. See docs/whole_run.md\n' >&2; exit 1; }
    test -f "$archive" || { printf 'Missing original extracted archive. See README.md\n' >&2; exit 1; }
    test -f work/messages.jsonl || { printf 'Missing extracted messages. See README.md\n' >&2; exit 1; }
    test -f "$context_map" || { printf 'Missing context map. See docs/whole_run.md\n' >&2; exit 1; }
    if ! test -f "$manifest"; then
      python tools/build_batch.py work/messages.jsonl "$archive" "$context_map" config/glossary.json "$manifest"
    fi
    rm -f "$stop_file"
    work/llama-build/bin/llama-server -m "$model" --host 127.0.0.1 --port 8080 --ctx-size 4096 --n-gpu-layers 0 >work/plamo-full-server.log 2>&1 &
    server_pid=$!
    trap 'kill "$server_pid" 2>/dev/null || true' EXIT INT TERM
    for attempt in $(seq 1 60); do
      if python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1)' >/dev/null 2>&1; then break; fi
      if ! kill -0 "$server_pid" 2>/dev/null; then printf 'llama-server exited. See work/plamo-full-server.log\n' >&2; exit 1; fi
      sleep 1
    done
    if ! python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1)' >/dev/null 2>&1; then
      printf 'llama-server did not become ready. See work/plamo-full-server.log\n' >&2; exit 1
    fi
    python -u tools/compare_local.py work/messages.jsonl "$manifest" "$model" "$cache" \
      --archive "$archive" --context-map "$context_map" --facts "$facts" \
      --show-output --stop-file "$stop_file" "$@" | tee -a "$live_log"
    ;;
  *)
    printf 'Usage: bash tools/full_run.sh prepare-route | route [--max-new N] | run [--max-new N] | stop\n' >&2
    exit 2
    ;;
esac
