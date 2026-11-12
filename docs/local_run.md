# Watch and control the local PLaMo run

This page describes the opening comparison batch: `000.SCN/text/001` and all 19 messages of `001.SCN`. `examples/model_sample.json` lists those IDs and their route-safe context. This batch is already cached in ignored `work/model-comparison.jsonl`; rerunning it prints `cached` and makes no model requests. For the conservative whole-corpus first pass, see [whole_run.md](whole_run.md).

Set `KIZUATO_MODEL_PATH` to your local GGUF file, then start the server:

```sh
export KIZUATO_MODEL_PATH="/path/to/plamo-3-translate-8b-Q4_K_M.gguf"
work/llama-build/bin/llama-server -m "$KIZUATO_MODEL_PATH" --host 127.0.0.1 --port 8080 --ctx-size 4096 --n-gpu-layers 0
```

Run the batch in another terminal from the repository root. It prints each ID and its English output as it completes, including cached output:

```sh
rm -f work/stop-plamo
python -u tools/compare_local.py work/messages.jsonl examples/model_sample.json "$KIZUATO_MODEL_PATH" work/model-comparison.jsonl --archive work/original-extract/KIZUATO/MAX2_SCN.PAK --show-output --stop-file work/stop-plamo | tee -a work/plamo-live.log
```

For a trial, add `--max-new 5` to limit **uncached** IDs. To stop cleanly after the current request, run `touch work/stop-plamo` from another terminal. To stop immediately, press Ctrl+C in the translation terminal. Each completed result is flushed and synced to the ignored JSONL cache before the next ID; resume by removing the stop file and running the same command. Failed IDs remain retryable. `tail -f work/plamo-live.log` watches a detached run. Stop the server with Ctrl+C when done.

Source text and model output stay in ignored `work/`. The local model drafts translation; they are not automatically wrapped, approved, or inserted. The initial 20-ID run completed on CPU and was checked for all 19 scene-001 IDs, nonempty output, and source-hash matches.
