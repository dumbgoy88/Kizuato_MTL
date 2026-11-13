# Public status — 2026-11-12

## Available release

The published download linked from `README.md` is still **v6 beta**. A player reported that text fit and translation quality looked good after about five minutes of play past the first choice. That is a player observation, not a complete route test. The v6 archive later failed to load several large scenes in targeted emulator checks with a `*MES DATA` allocation error. Do not treat v6 as a verified full-game patch.

## Verified v7 candidate work

- The local v7 build uses lossless LZS2 compression and splits 55 main-story source scenes into 66 additional numbered scenes. The resulting 239-scene PAK has SHA-256 `a9c35adf6e96d156405a937f7a0635a8bd8ba54075791792198170931cacc05b`. The sharder reconstructs every original source message and event command after reversing its ID remaps and removing only added handoffs. It rejects unsupported scene shapes, duplicated or unreferenced IDs, and branches into a split prefix.
- The copied public sharder was run against the same ignored pre-shard input from the working project and reproduced that exact v7 PAK hash. No generated PAK was placed in or committed from the public checkout.
- A fresh build completed the draft, layout, pagination, branch, sharding, and installed-file readback checks. The local v7 installer candidate ZIP has SHA-256 `d0ecb9613360d06a1ab9834b77aa8f2c41d2a7c5322c52830ffd024d52fe4ce2`. Running its packaged `install.py` against the hash-pinned clean HDI produced a new HDI with the expected scene PAK. The ZIP and HDI are ignored generated files and are not in Git.
- SDL NP2 Kai displayed English text from sharded `016.SCN`, added `170.SCN`, and unsplit bonus `201.SCN`. Disposable, hash-checked shortcut probes verified the added `016 → 203` and `203 → 204` scene loads. A shortened `204.SCN` choice probe displayed both English options; option 1 reached `017.SCN` and option 2 reached `018.SCN`, each confirmed by the destination's opening text. FM was selected in these boots; playback and effects were not independently reviewed for the full route.

## Limits and next checks

- The handoff and choice probes deliberately shorten preceding display calls. They verify engine commands and branch destinations in native play, but do not prove the unshortened scene chain or prior route state. No complete v7 route has been verified.
- `201.SCN` loads in a direct jump but has twelve dynamically referenced bonus messages and page behavior that still need route-specific checks. It is an explicit exception to the 16,000-byte main-story text budget.
- Next: test the unshortened route approach to the first sharded choice, audit the bonus-scene dynamic messages, then run guarded route and save/load checks with audio and effects observation. Publish a new installer only after reviewing those results. The source build commands are in `docs/development_workflow.md`; diagnostic method and limits are in `docs/test_strategy.md`.

No game images, rebuilt archives, model weights, screenshots, or private research notes are tracked here.
An image embed from an earlier remote README edit was removed from the current README during this source update. The earlier Git commit and its hosted attachment still exist in remote history; this update does not rewrite or delete them.
