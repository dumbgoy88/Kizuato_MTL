# Public handoff

Read `AGENTS.md`, `STATUS.md`, and `docs/development_workflow.md` first. The public download remains v6 beta; a v7 installer candidate with lossless compression and conservative scene sharding has been built and tested locally but is not yet published. Keep claims about native emulator checks separate from static archive checks.

The candidate's source tools are in `tools/`. `bash tools/rebuild_split_demo.sh <unused-name>` makes an ignored HDI copy from the hash-pinned original and private draft cache. `python tools/build_beta_package.py` packages the pinned English edit set and project-authored installer code into an ignored ZIP. Neither generated game data nor translation cache is included in this repository. See `STATUS.md` for exact PAK/ZIP hashes and the remaining route and bonus-scene checks.

Never commit a game image, rebuilt archive, screenshot with game art, model weight, save, or credential. Do not push from this checkout without a separate explicit instruction.
