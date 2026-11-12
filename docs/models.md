# Local translation model investigation — 2026-11-09

PLaMo 3 Translate 8B Q4_K_M has been downloaded to the user's existing local AI/model location. Its 5,280,445,728 bytes hash to `94e5d3f91b421f7c8900ddaac27b11a19f7441426c954bbb25a2fd60a1640187`, matching the official file's linked ETag. The existing llama.cpp server rejects this model with `unknown tokenizer: 'plamo3'`. A current llama.cpp checkout (`3b4d6ab`, 2026-11-09) was built in ignored `work/` and loaded the model successfully on CPU. Vulkan headers were absent from the local build environment, so this comparison did not use the GPU. No paid API has been used.

[Preferred Networks' PLaMo 3 Translate 8B GGUF card](https://huggingface.co/pfnet/plamo-3-translate-8b-GGUF) lists Q4_K_M at 5.28 GB and supports Japanese→English, context, glossary, and previous translation pairs. It recommends llama.cpp and a direct PFML3 prompt for production use. The [31B model's card](https://huggingface.co/pfnet/plamo-3-translate-31b-GGUF) lists Q4_K_M at 19.53 GB, above the supplied 16 GB VRAM before context overhead; partial GPU offload plus system RAM would be needed. The 8B Q4 is the practical first candidate, but quality on this visual novel is untested. The cards report benchmark scores, which are not a substitute for a scene-specific comparison.

The existing local llama.cpp binary reports the RX 9070 XT through Vulkan. [llama.cpp's build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md) supports Vulkan and HIP backends. AMD's [ROCm Linux requirements](https://rocm.docs.amd.com/projects/install-on-linux/en/docs-7.2.0/reference/system-requirements.html) list the RX 9070 XT but limit the documented Radeon OS support to selected Ubuntu and RHEL releases, so HIP support on CachyOS is not assumed. Vulkan is locally detected; inference with PLaMo has not been tested.

`tools/compare_local.py` prepares four explicit sample IDs from ignored `work/messages.jsonl`, uses the PFML3 format below, filters glossary terms to those present in source/context, and caches successes by exact prompt and model hash. It now requires the hash-verified original scene archive and admits prior context only from `001.SCN` messages 0–15, the verified common prefix before its first branch. Cross-scene or later same-scene context awaits a verified event graph. The sample IDs and voice notes are in `examples/model_sample.json`. All four local requests completed before this stricter gate was added; the gate has been tested without new model calls. Results remain in ignored `work/model-comparison.jsonl`.

## Small local comparison

| Source ID suffix | Kind | CPU time | Review |
| --- | --- | ---: | --- |
| `000.SCN/text/001` | Opening narration | 2.1 s | Captured the dream, dark room, shaking, and self-clutching; wording needs an English editing pass for natural voice and a separate 24-glyph layout pass. |
| `001.SCN/text/005` | Chizuru introduction | 7.7 s | Kept her full name, cousin relationship, age, and household role. The glossary spelling was respected. |
| `001.SCN/text/013` | Chizuru dialogue | 6.2 s | Preserved her polite speech and the narrator's observation. Honorific style (`-san` versus localized address) is not yet standardized. |
| `001.SCN/text/017` | Name-bearing choice | 2.8 s after repair | Raw display wrapping split the Japanese word for “joke”; the first output invented a speaker named Joe. After explicitly joining that display break and removing the choice number from the model input, the output expressed the intended joke. This shows why source dewrapping needs review. |

These are four draft comparisons, not proof of quality across routes or adult scenes. PLaMo 8B Q4 is a practical **provisional drafting model** for the current sample. Human review, route-safe context, and renderer formatting remain required. The 31B candidate has not been run. The model outputs are not inserted automatically.

## PFML3 prompt form

The [official model card's prompt section](https://huggingface.co/pfnet/plamo-3-translate-8b-GGUF) specifies the element order: dataset, context, previous input/output pairs, glossary, current input, empty output. For a single passage:

```text
<|plamo:tag|>dataset<|plamo:msg|>translation<|plamo:tag|>context<|plamo:msg|>近くの日本語の文脈<|plamo:tag|>glossary<|plamo:index|>原語<|plamo:item|>approved term<|plamo:tag|>input<|plamo:key|>lang<|plamo:val|>ja<|plamo:msg|>翻訳する文<|plamo:tag|>output<|plamo:key|>lang<|plamo:val|>en<|plamo:msg|>
```

Do not add a leading BOS token or trailing newline. Stop generation on `<|plamo:tag|>` or `<|plamo:bos|>`. Use temperature 0 for reproducible drafts. Pass only visible Japanese text to the model; keep engine commands in extraction records. Cache each success by source, context, glossary, model file hash, and prompt revision. Retry failed requests with bounded backoff.

## Comparison before selection

Choose a few representative Kizuato passages already extracted: narration, character dialogue with names or ambiguous reference, and choice text. Use identical context and glossary for each candidate. Record output, latency, memory use, faithfulness, omitted nuance, naming consistency, and human edits. Keep the sample small; do not translate full routes. Compare 8B Q4 with 31B only if resources permit, or with another already-local model. Pick a model only after this comparison.
