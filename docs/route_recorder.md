# Route recording on a dedicated laptop

`tools/route_recorder.py` is a conservative action runner for a visible emulator window on an **X11** session. It records the window to Matroska segments and sends only keys explicitly listed in a route JSON file. It never infers a route or chooses an option by itself. Use your own installed beta HDI. Recordings and screenshots stay under ignored `build/route-recordings/`; do not commit or share game footage.

## Setup

Install `ffmpeg`, `xdotool`, and `tesseract` on the laptop. Python 3.10+ is sufficient for the script. The integrated GPU is fine for 15 fps capture; OCR runs on the CPU only at checkpoints. Log into an X11 desktop session, start Neko Project II Kai with your beta HDI, and locate its window ID:

```sh
xdotool search --name 'Neko Project'
```

Copy `config/route_recorder.example.json` to a route file under ignored `work/`. Replace the placeholder steps with the exact actions and screen markers for the route. A `press` step needs `key` (`Return`, `space`, `Up`, `Down`, `Left`, `Right`, or `Escape`), `count`, and optional `interval` seconds. Use single keypress steps around choices. A `wait` step needs `seconds`. A `checkpoint` needs an `expect` regular expression recognized in OCR text. Any step can have `expect` to verify the screen before acting. Screenshots and raw OCR text are saved for each check. OCR can be imperfect on PC-98 fonts; inspect failures manually.

After the **last verified choice** on a route, a final `advance_to_ending` step can press Return until it sees one of the v6 English ending markers from [route_endpoints.md](route_endpoints.md). Give that step `ending_id`, `max_presses`, and `interval`; see `config/route_recorder_end.example.json`. It stops when the marker is confirmed or when the cap is reached. It must not be used across unknown choices. The marker mapping has passed static PC-98 event and v6 edit checks but has not yet passed live OCR/gameplay checks.

Validate without touching the emulator:

```sh
python3 tools/route_recorder.py work/chizuru-route.json --dry-run
```

Start recording (replace the ID with the emulator window from `xdotool`):

```sh
python3 tools/route_recorder.py work/chizuru-route.json --window-id 12345678
```

To capture FM music and effects as well, identify the laptop's monitor source with `pactl list short sources` and add `--audio-source <monitor-source-name>`. Check a short segment for sound before an overnight run. Without that option, the video has no audio.

Press Ctrl+C to stop after the current key. The emulator remains open. Resume against **the same still-running emulator window**:

```sh
python3 tools/route_recorder.py work/chizuru-route.json --window-id 12345678 --resume-live
```

The script checks the route-file hash, window ID, and process ID before resuming. It stores a step index and keypress offset in `build/route-recordings/<route>/state.json`. Each start creates a new `.mkv` segment. If OCR stops at a checkpoint, inspect the saved PNG and TXT. When the screen is actually correct, resume with `--resume-live --ack-checkpoint` to bypass that one OCR check. If the emulator has closed or restarted, begin a new run in a fresh output directory; a matching route file alone cannot restore game state.

## Limits

The example route files are only templates, **not** verified Kizuato routes. No full route has yet been automated. Screen OCR does not prove translated wording is correct, text is complete, or audio/effects are preserved. Review the videos and tester notes against the route script. Record choice branches in separate runs, and verify music/effects by listening or reviewing the optional audio track. Unknown menus, variable pauses, and ambiguous text need explicit route steps and checkpoints before unattended use.
