# Development workflow

For maintainers building from their own hash-pinned source files. Read `AGENTS.md` and `STATUS.md` before modifying project tools.

## Reproducible workflow

1. Read [STATUS.md](../STATUS.md) and [docs/technical.md](technical.md).
2. Inspect the HDI without writing to it:

   ```sh
   sha256sum 'Kizuato (J).hdi'
   mdir -i 'Kizuato (J).hdi'@@38912 -/ ::KIZUATO
   ```

3. Extract only into ignored `work/`:

   ```sh
   mkdir -p work/original-extract
   mcopy -s -i 'Kizuato (J).hdi'@@38912 ::KIZUATO work/original-extract/
   ```

4. Verify and extract the PC-98 archive (untracked output):

   ```sh
   python tools/leafpack_pc98.py verify work/original-extract/KIZUATO/MAX2_SCN.PAK
   python tools/leafpack_pc98.py extract work/original-extract/KIZUATO/MAX2_SCN.PAK work/scenes
   ```

5. A no-op rebuilt archive can be inserted on an HDI **copy** and read back:

   ```sh
   python tools/leafpack_pc98.py rebuild work/original-extract/KIZUATO/MAX2_SCN.PAK build/MAX2_SCN.PAK
   python tools/hdi_copy.py 'Kizuato (J).hdi' build/kizuato-noop.hdi build/MAX2_SCN.PAK KIZUATO/MAX2_SCN.PAK
   ```

6. Export stable-ID records using an external XLVNS `kizfont.tbl` research table. The output stays ignored because it contains game text:

   ```sh
   python tools/scenes.py export work/original-extract/KIZUATO/MAX2_SCN.PAK /path/to/kizfont.tbl work/messages.jsonl
   ```

7. Build the small English sample and insert it on a new HDI copy. Use unused output names on repeated runs:

   ```sh
   python tools/scenes.py apply work/original-extract/KIZUATO/MAX2_SCN.PAK /path/to/kizfont.tbl examples/opening_en.json build/MAX2_SCN-demo.PAK
   python tools/hdi_copy.py 'Kizuato (J).hdi' build/kizuato-demo.hdi build/MAX2_SCN-demo.PAK KIZUATO/MAX2_SCN.PAK
   ```

8. Boot the copy in Neko Project II Kai with the HDI as a positional argument. Select FM audio and a blank bookmark slot. Verify the first reachable choice in `001.SCN` and its branches. See [STATUS.md](../STATUS.md) for what has actually passed.

On KDE Wayland, see [docs/emulator.md](emulator.md) for the local keyboard-control helper and the exact verification checklist.

For a short **diagnostic only**, `tools/choice_probe.py` can skip the fifteen display commands before that choice. It accepts only the hash-verified nine-message demo PAK and leaves the choice event and text unchanged. Insert its output into a fresh HDI copy using `tools/hdi_copy.py`. This probe changes the preceding event sequence, so verify the normal demo path separately before claiming a gameplay milestone. The probe itself is not a release artifact.

Compare only a few representative passages with a local model before expanding translation. See [docs/models.md](models.md) for candidates and the documented PFML3 prompt format.

The current local PLaMo opening run and its live stop/resume controls are in [docs/local_run.md](local_run.md). A conservative whole-corpus draft command is in [docs/whole_run.md](whole_run.md); it does not yet produce an insertion-ready patch.

The first whole-script draft pass has finished. Its 3,306 translatable IDs are cached; formatting, pause alignment, typography, and route-aware editorial review remain. [docs/review_findings.md](review_findings.md) gives the static QA counts. [docs/beta_test.md](beta_test.md) describes the earlier player-test image and its limitations; see the top of `STATUS.md` for the newer sharded candidate.

A second local pass with verified mandatory cross-scene context, choice breadcrumbs, expanded names, and stage-gated PC-98 facts is prepared. Run `bash tools/full_run.sh route` to start or resume it; use `bash tools/full_run.sh stop` from another terminal to stop after the current request. [docs/route_aware_run.md](route_aware_run.md) gives preparation, live monitoring, and precise context limits. This pass has only been smoke-tested so far.

To make a new HDI copy from PLaMo drafts completed so far, run `python tools/build_live_patch.py`. See [docs/live_patch.md](live_patch.md) for the no-truncation rules and the per-ID skip report.

For full-length passage experiments, [docs/pagination.md](pagination.md) describes native line/page command insertion and its remaining emulator checks. The user requires all English text to stay readable; no release build may truncate drafts or leave unreviewed overflow.

[docs/compact_font.md](compact_font.md) records the 36/48-column feasibility estimate and the native Kizuato font/EXE work needed for a smaller, legible English renderer. The current build does not contain that renderer.

For the four-message PLaMo sample, start a compatible local llama.cpp server bound to `127.0.0.1` with the downloaded model, then run:

```sh
python tools/compare_local.py work/messages.jsonl examples/model_sample.json /path/to/plamo-3-translate-8b-Q4_K_M.gguf work/model-comparison.jsonl --archive work/original-extract/KIZUATO/MAX2_SCN.PAK
```

The existing older llama.cpp executable does not understand this model's tokenizer. See [docs/models.md](models.md) for the tested local runtime. Sample outputs and cache stay in ignored `work/`. No GPT API backend is active; adding one would require separate explicit configuration and a deliberate run.

## Current sharded candidate

Run `bash tools/rebuild_split_demo.sh <unused-name>` to rebuild the full English local test HDI from ignored source and draft files. It audits pagination, compresses rebuilt scenes with LZS2, splits main-story text blocks to at most 16,000 decoded bytes, and verifies the installed PAK on a new HDI copy. It never overwrites an existing output. Review `build/<name>-split-audit.json` and `build/<name>-shard-report.json`; bonus scene `201.SCN` remains an explicit exception.

`python tools/build_beta_package.py` creates the ignored `build/Kizuato-English-v7-beta-candidate.zip` from the pinned edit set and checked PAK. The builder refuses to replace an existing ZIP. Its packaged `install.py` was run end to end on the pinned clean HDI; see `STATUS.md` for hashes and native checks. To verify another clean install, extract the ZIP and run its `install.py` with `--output` set to an unused path under `build/`.

The public README still links the older v6 beta. Do not publish the v7 candidate, extracted game files, or a patched HDI until the outstanding route checks in `STATUS.md` are reviewed.

## Project layout

- `AGENTS.md`: rules for future sessions.
- `STATUS.md`: dated evidence, blockers, next commands.
- `docs/`: reverse engineering notes, translation rules, model research.
- `tools/`: source-controlled local tooling as it is verified.
- `work/`, `build/`: ignored game data and generated output.
