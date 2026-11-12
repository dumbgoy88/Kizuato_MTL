# Small opening translation comparison

The script is already extracted. Comparison should use stable IDs and the same Japanese source, without replaying hours of the game. This batch is non-explicit and stays in the opening common prefix of `001.SCN`.

Codex (GPT-6 Sol in this session) drafted `001.SCN/text/000`–`005` as one contiguous opening passage, plus the three previously selected sample IDs. Drafts with source hashes are in ignored `work/codex-translation-comparison.jsonl`. This was direct Codex translation; no separate OpenAI API call or paid API was used. The English is unreviewed and has not been wrapped or inserted.

PLaMo 3 Translate 8B Q4_K_M now has cached results for the same six-message `001.SCN/text/000`–`005` opening plus `000.SCN/text/001`, `001.SCN/text/013`, and `/017` in ignored `work/model-comparison.jsonl`. Five new local calls took 1.3, 3.8, 4.9, 5.5, and 8.2 seconds on the local CPU; four old results were reused. The common-prefix gate prevented sibling-choice context. The server has been stopped.

Two short side-by-side examples from the same source IDs:

| ID | Codex GPT draft | PLaMo 8B draft |
| --- | --- | --- |
| `001/000` | “I jolted upright, my upper body springing out of the futon.” | “Gasp! I bolted upright from my futon.” |
| `001/002` | “The room was unfamiliar. Was this still the dream? No... this was...” | “It was an unfamiliar room. …A continuation of the dream? No… that’s not it. This place is…” |

The source of `001/000` begins with a movement sound; PLaMo's “Gasp!” may suggest the wrong action. Codex is smoother in this sample but sometimes compresses nuance: in `001/004` it renders the closing remark as a “lovely day,” while PLaMo retains the explicit weather reference. PLaMo tends to be more literal and wordier. Both retain the key relationship and age facts in `001/005`. No draft is accepted without human review; this six-message sample is too small to establish quality across the game.

| ID suffix | Comparison so far |
| --- | --- |
| `000/001` | Both convey a dream, a dark room, and the narrator holding himself while trembling. The Codex draft is shorter; neither is engine-formatted. |
| `001/005` | Both retain Chizuru's name, cousin relationship, age, education, household role, and reason she was startled. Review the honorific and institution wording before insertion. |
| `001/013` | Both keep Chizuru's polite offer to analyze the dream and the narrator's impression of her. The Codex draft is more idiomatic; neither has been checked against a screen box. |
| `001/017` | PLaMo initially treated a display-split `ジョー　　ク` as a person named Joe. Dewrapping and removing the option number produced the intended joke; the Codex draft also preserves it. This is a source-preparation failure to guard against. |

If the local quality is acceptable, a future overnight run should traverse **verified route-safe batches** rather than issue 3,309 unscoped requests. It needs a scene/branch graph, a stage-tagged context packet with only prior Japanese and reviewed translations, glossary filtering, cache keys that include source/context/glossary/model/prompt, bounded retries, and a resumable ledger of accepted and failed IDs. The current runner has caching and bounded retries but only an opening common-prefix gate; it cannot yet safely translate the whole script overnight. After drafting, validate IDs, source hashes, commands, branches, encoding, and measured box overflow before any insertion. See `docs/translation.md` and `STATUS.md` for the remaining gates.
