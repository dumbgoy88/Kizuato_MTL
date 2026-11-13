Kizuato v6 beta laptop recording kit
==================================

This kit contains the tested English installer ZIP and a draft route recorder.
It contains no game image. Bring your own clean Kizuato HDI. The recorder has
no verified full-route action file yet; the included JSON is an example only.

On Artix, log into an X11 session and install the recording tools:

  sudo pacman -S --needed python ffmpeg xdotool tesseract tesseract-data-eng unzip

If your enabled Artix repositories lack a package, use your usual yay setup.
The emulator must already be installed separately.

1. Extract Kizuato-English-v6-beta.zip. Follow its README.txt to install the
   English patch onto a COPY made by the installer. Start that new HDI in Neko
   Project II Kai.
2. Copy route_recorder.example.json to a new route file, such as
   chizuru-route.json. Replace every example step with observed keypresses,
   waits, and OCR checkpoints for that route. After its last verified choice,
   add a final advance_to_ending step with an ending_id from
   route_endpoints_v6.json. See route_recorder_end.example.json for its format.
   One file is needed per route/choice path.
3. Check the route file without sending keys:

   python3 route_recorder.py chizuru-route.json --dry-run

4. Find the emulator window ID:

   xdotool search --name 'Neko Project'

5. Run, replacing 12345678 with that ID:

   python3 route_recorder.py chizuru-route.json --window-id 12345678

   Optional audio: add --audio-source NAME, where NAME is a monitor source from
   `pactl list short sources`. Test a short recording for sound first.

The recorder stops and closes its video file when the final ending marker is
recognized, or after the LAST scripted step if no ending action is present.
It stops for review if the marker is not recognized before max_presses. These
markers were correlated with the 1996 guide and PC-98 event data but have not
been tested by live OCR or full-route gameplay. Ctrl+C stops sooner after the
current key. Resume with the same live
emulator window and route file:

   python3 route_recorder.py chizuru-route.json --window-id 12345678 --resume-live

If an OCR checkpoint fails, inspect the saved PNG/TXT before deciding to add
--ack-checkpoint to that resume command. If the emulator was closed, start a
new run in a fresh output directory; a recorder state file cannot restore game
state. Output videos and screenshots are under build/route-recordings/ by default.
Do not share recordings or installed HDIs without permission from the game
rights holder. Share this tools-and-installer kit instead.
