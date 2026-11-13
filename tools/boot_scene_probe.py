#!/usr/bin/env python3
"""Boot a disposable scene-jump HDI in an already-running X11 NP2 Kai window.

This only handles the sound, title, and blank-bookmark menus. It saves ignored
screenshots for review and never presses Return through scene text.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("window_id")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--display", default=":98")
    parser.add_argument("--xdotool", default="xdotool")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory exists")
    args.output_dir.mkdir(parents=True)
    env = os.environ.copy()
    env["DISPLAY"] = args.display

    def snap(name: str) -> str:
        path = args.output_dir / f"{name}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab",
                        "-window_id", args.window_id, "-i", args.display,
                        "-frames:v", "1", str(path)], env=env, check=True)
        return subprocess.check_output(["tesseract", str(path), "stdout", "--psm", "6"],
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def key(name: str) -> None:
        subprocess.run([args.xdotool, "windowfocus", "--sync", args.window_id],
                       env=env, check=True, stdout=subprocess.DEVNULL)
        subprocess.run([args.xdotool, "keydown", name], env=env, check=True)
        time.sleep(.25)
        subprocess.run([args.xdotool, "keyup", name], env=env, check=True)

    for _ in range(args.timeout):
        sound = snap("sound")
        if "FM" in sound.upper() or "MIDI" in sound.upper():
            print("sound menu:", repr(sound[:90]), flush=True)
            break
        time.sleep(1)
    else:
        raise RuntimeError("sound menu not found before timeout")
    key("Return")
    time.sleep(24)
    for attempt in range(8):
        key("space")
        time.sleep(1.5)
        title = snap(f"title-{attempt+1}")
        if "DOS" in title.upper():
            print("title menu:", repr(title[:90]), flush=True)
            break
    else:
        raise RuntimeError("title menu not recognized")
    key("z")
    time.sleep(1)
    bookmark = snap("bookmark")
    print("bookmark menu:", repr(bookmark[:90]), flush=True)
    key("KP_Enter")
    time.sleep(2)
    result = snap("result")
    print("first scene OCR:", repr(result[:160]), flush=True)
    print("review", args.output_dir / "result.png", flush=True)


if __name__ == "__main__":
    main()
