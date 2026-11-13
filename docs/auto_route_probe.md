# Guarded Chizuru route probe

The project has a **23-choice Chizuru good-route selection list** in `config/route_chizuru_good_choices.json`, correlated from the [1996 walkthrough](https://lastcharles.com/pc-18/walkthrough/pc-18/kizuato) to exact Japanese options in the pinned PC-98 event graph. The list stores scene/block, number of options, and selected index, not guide prose or extracted text. `tools/build_route_probe_plan.py` joins that list to the pinned v6 English edits and writes an ignored plan for `tools/auto_route_probe.py`. The plan is a hypothesis about a reachable route until a full emulator run succeeds.

The experimental auto probe needs Python Pillow in addition to FFmpeg, xdotool, and Tesseract. It uses a second OCR pass over enlarged, thresholded white text because artwork behind the choice options defeated raw OCR on the first observed choice. Artwork can also produce fake option numbers; the unknown-choice guard requires at least three readable words of four or more letters. This is an observed-screen heuristic, not proof against every artwork or choice layout.

The second observed choice needed an ordered multi-stretch similarity score: its long option was legible except for an extra OCR glyph, which broke the earlier longest-stretch detector. The current detector requires two listed options to score at least 0.75 in ordered fragments and 0.40 in their longest uninterrupted match. A narration screen had high fragment scores but uninterrupted ratios no higher than 0.25; saved real choice OCR had ratios of at least 0.50 for the accepted options. It also requires one visible numbered option line. If two option bodies match but no number is readable, it stops rather than pressing Return. Later screens still need review.

The first automated pass reached the wrong branch after its second choice. The X11 cursor sometimes did not move before Return was sent. The probe captures the white triangular choice cursor, samples up to 32 frames for its slow blink, and cycles through all option rows to map their screen positions. It then moves to the selected row and verifies that position before Return. This handles a key that merely reveals the arrow without moving it, and a wrapped cursor on a resumed choice. If all expected rows cannot be observed or the target is not reached, it stops and saves the screen. A complete gameplay replay must still prove the route.

Build the plan from this repo's ignored inputs:

```sh
python tools/build_route_probe_plan.py config/route_chizuru_good_choices.json work/event_graph-route-v1.json build/all-english-diagnostic-20261111-v6-unsafe-intermediate-edits.json work/route-test/chizuru_good_plan.json
```

Use a **copy** of the v6 HDI in an X11 emulator window. The runner records a video segment, captures one screen per advance, and OCRs it. It presses Return through narration; at a choice it requires at least two expected English options to match, selects the configured option, and continues. If OCR sees an unrecognized numbered choice, the emulator process changes, the video recorder stops, the screen stalls, or the press cap is hit, it stops with state in ignored `build/auto-route/<route>/state.json`. It does not silently choose an unknown option. After the 23rd choice it looks for the route's v6 ending marker.

```sh
python tools/auto_route_probe.py work/route-test/chizuru_good_plan.json --window-id WINDOW_ID --max-presses 1200 --interval 0.6
```

Send SIGINT or SIGTERM to stop after the current key; leave the emulator open. Resume with the same window and exact plan using `--resume-live`. The video segment, OCR log, choice screenshots, and state stay ignored. This probe is experimental: OCR may miss a choice, and pressing Return at that screen could choose a default. Review the recording and branch evidence before trusting any route outcome. The probe does not edit the game image or prove audio/effect timing. Do not publish recordings or extracted plan text.

If the game leaves a repeated DOS `A>` prompt, the probe stops with `dos_exit` and saves `dos-exit.png`. A DOS prompt is a failed route run, not an ending marker. Investigate the first transition into DOS before restarting from a clean image.

For an unattended run, `tools/hourly_route_status.py STATE_JSON RUNNER_PID LOG_JSONL` appends one progress snapshot immediately and then hourly while the runner PID exists. The log is local only; it does not send chat updates. A stopped runner exits the logger after its next snapshot. Start it under a persistent user service if it must survive the terminal session.

On this desktop, isolated `Xvfb :98` plus a minimal X11 window manager made keyboard focus work without taking control of the user's Wayland session. The required binaries were unpacked into ignored `build/route-test/xroot`; no system packages were installed. A copied `FONT.ROM` was needed for game boot. In the opening, Space toggled text visibility; Return advanced to the next text message. This local arrangement is diagnostic, not a portable installer.
