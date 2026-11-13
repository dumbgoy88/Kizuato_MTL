#!/usr/bin/env python3
"""Record a scripted PC-98 playthrough on a dedicated X11 desktop.

This is a test harness, not a route solver. Actions are supplied by a human;
unknown choices stop at an explicit checkpoint instead of being guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STOP = False
ALLOWED_KEYS = {"Return", "space", "Up", "Down", "Left", "Right", "Escape"}


def normalized(s: str) -> str:
    """Ignore case, punctuation and line breaks in short OCR markers."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def on_stop(_signal, _frame):
    global STOP
    STOP = True


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def focus_window(window: str) -> None:
    try:
        run("xdotool", "windowactivate", "--sync", window)
    except subprocess.CalledProcessError:
        # Minimal X11 window managers may not implement _NET_ACTIVE_WINDOW.
        run("xdotool", "windowfocus", "--sync", window)


def save_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def validate(spec: dict) -> None:
    if not isinstance(spec, dict) or not isinstance(spec.get("route"), str):
        raise ValueError("Route file needs a route name")
    if not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise ValueError("Route file needs nonempty steps")
    names = set()
    for i, step in enumerate(spec["steps"]):
        if not isinstance(step, dict) or step.get("action") not in {"press", "wait", "checkpoint", "advance_to_ending"}:
            raise ValueError(f"Step {i}: unsupported action")
        name = step.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError(f"Step {i}: unique nonempty name required")
        names.add(name)
        if step["action"] == "press":
            if step.get("key") not in ALLOWED_KEYS or not isinstance(step.get("count"), int) or not 1 <= step["count"] <= 1000:
                raise ValueError(f"Step {i}: unsupported key or count")
            if not 0.05 <= float(step.get("interval", 0.3)) <= 10:
                raise ValueError(f"Step {i}: interval outside 0.05–10 seconds")
        if step["action"] == "wait" and not 0 <= float(step.get("seconds", -1)) <= 3600:
            raise ValueError(f"Step {i}: wait outside 0–3600 seconds")
        if step["action"] == "checkpoint" and not step.get("expect"):
            raise ValueError(f"Step {i}: checkpoint requires OCR regex")
        if step["action"] == "advance_to_ending":
            if i != len(spec["steps"]) - 1 or not isinstance(step.get("ending_id"), str):
                raise ValueError(f"Step {i}: advance_to_ending must be last and name an ending_id")
            if not isinstance(step.get("max_presses"), int) or not 1 <= step["max_presses"] <= 2000:
                raise ValueError(f"Step {i}: max_presses must be 1–2000")
            if not 0.2 <= float(step.get("interval", 1.0)) <= 10:
                raise ValueError(f"Step {i}: interval outside 0.2–10 seconds")
        if "expect" in step:
            re.compile(step["expect"])


def screenshot(window: str, output: Path, display: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "x11grab", "-window_id", window,
                    "-i", display, "-frames:v", "1", str(output)], check=True)


def check_screen(step: dict, window: str, folder: Path, index: int, display: str) -> bool:
    if "expect" not in step:
        return True
    png = folder / f"checkpoint-{index:04d}.png"
    screenshot(window, png, display)
    result = run("tesseract", str(png), "stdout", "--psm", "11")
    (folder / f"checkpoint-{index:04d}.txt").write_text(result + "\n")
    matched = re.search(step["expect"], result, flags=re.I | re.S) is not None
    print(f"OCR {'PASS' if matched else 'STOP'}: {step['name']} (screenshot: {png})", flush=True)
    return matched


def scan_ending(window: str, folder: Path, display: str) -> str:
    png = folder / "endpoint-current.png"
    screenshot(window, png, display)
    result = run("tesseract", str(png), "stdout", "--psm", "11")
    (folder / "endpoint-current.txt").write_text(result + "\n")
    return normalized(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route_file", type=Path)
    parser.add_argument("--window-id", help="X11 emulator window ID, e.g. from xdotool search --name Neko")
    parser.add_argument("--output-dir", type=Path, default=Path("build/route-recordings"))
    parser.add_argument("--audio-source", help="optional PulseAudio/PipeWire monitor source for emulator sound")
    parser.add_argument("--endpoints", type=Path, help="v6 ending marker manifest (default: beside script or config/)")
    parser.add_argument("--resume-live", action="store_true", help="resume only if the same emulator window and PID still exist")
    parser.add_argument("--ack-checkpoint", action="store_true", help="after inspecting its screenshot, bypass OCR for the current step once")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raw = args.route_file.read_bytes()
    spec = json.loads(raw)
    validate(spec)
    digest = hashlib.sha256(raw).hexdigest()
    print(f"Route {spec['route']}: {len(spec['steps'])} steps; spec SHA-256 {digest}", flush=True)
    endpoint_path = args.endpoints or Path(__file__).with_name("route_endpoints_v6.json")
    if args.endpoints is None and not endpoint_path.exists():
        endpoint_path = Path("config/route_endpoints_v6.json")
    endpoints = {}
    if any(s["action"] == "advance_to_ending" for s in spec["steps"]):
        endpoint_doc = json.loads(endpoint_path.read_text())
        if endpoint_doc.get("revision") != "v6-beta":
            raise ValueError("Ending markers require the v6 beta revision")
        endpoints = {row["id"]: row for row in endpoint_doc["endings"]}
        for step in spec["steps"]:
            if step["action"] == "advance_to_ending" and step["ending_id"] not in endpoints:
                raise ValueError(f"Unknown ending_id: {step['ending_id']}")
    if args.dry_run:
        for i, step in enumerate(spec["steps"]):
            suffix = f" -> {step['ending_id']}" if step["action"] == "advance_to_ending" else ""
            print(f"{i:03d} {step['action']:17} {step['name']}{suffix}")
        return 0
    if args.ack_checkpoint and not args.resume_live:
        raise ValueError("--ack-checkpoint requires --resume-live")
    for tool in ("ffmpeg", "xdotool", "tesseract"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"Install {tool} first")
    display = os.environ.get("DISPLAY")
    if not display or not args.window_id:
        raise RuntimeError("Set DISPLAY and pass --window-id on an X11 desktop")
    window = str(int(args.window_id, 0))
    pid = run("xdotool", "getwindowpid", window)
    folder = args.output_dir / re.sub(r"[^a-zA-Z0-9_-]", "_", spec["route"])
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / "state.json"
    if args.resume_live:
        state = json.loads(state_path.read_text())
        if (state.get("spec_sha256"), state.get("window_id"), state.get("window_pid")) != (digest, window, pid):
            raise RuntimeError("Route or live emulator window changed; refusing unsafe resume")
    else:
        if state_path.exists():
            raise RuntimeError(f"Existing state at {state_path}; use --resume-live with the same emulator")
        state = {"spec_sha256": digest, "window_id": window, "window_pid": pid, "step": 0, "press_offset": 0}
        save_json(state_path, state)
    if args.ack_checkpoint and (state["step"] >= len(spec["steps"]) or "expect" not in spec["steps"][state["step"]]):
        raise ValueError("Current step has no OCR checkpoint to acknowledge")
    segment = folder / f"segment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.mkv"
    capture = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "x11grab",
               "-framerate", "15", "-window_id", window, "-i", display]
    if args.audio_source:
        capture += ["-f", "pulse", "-i", args.audio_source]
    capture += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "27"]
    if args.audio_source:
        capture += ["-c:a", "aac", "-b:a", "128k"]
    capture += [str(segment)]
    video = subprocess.Popen(capture, stdin=subprocess.PIPE)
    time.sleep(0.3)
    if video.poll() is not None:
        raise RuntimeError("FFmpeg exited before recording started; check DISPLAY and window ID")
    print(f"Recording {segment}; Ctrl+C stops after the current key. Emulator stays open.", flush=True)
    try:
        while state["step"] < len(spec["steps"]) and not STOP:
            i = state["step"]
            step = spec["steps"][i]
            if run("xdotool", "getwindowpid", window) != pid:
                raise RuntimeError("Emulator window changed during recording")
            if video.poll() is not None:
                raise RuntimeError("FFmpeg stopped during recording")
            print(f"[{i+1}/{len(spec['steps'])}] {step['name']}", flush=True)
            already_started = step["action"] == "press" and state["press_offset"] > 0
            if not (args.ack_checkpoint or already_started) and not check_screen(step, window, folder, i, display):
                print("Stopped at unmatched OCR checkpoint; inspect image/text, then resume with --ack-checkpoint if the screen is correct.", flush=True)
                break
            args.ack_checkpoint = False
            if step["action"] == "checkpoint":
                print("Checkpoint accepted.", flush=True)
            elif step["action"] == "advance_to_ending":
                ending = endpoints[step["ending_id"]]
                focus_window(window)
                marker = normalized(ending["marker"])
                while not state.get("ending_found") and not STOP:
                    if marker in scan_ending(window, folder, display):
                        state["ending_found"] = True
                        save_json(state_path, state)
                        print(f"Ending marker matched: {ending['id']} ({ending['scene']})", flush=True)
                        break
                    if state["press_offset"] >= step["max_presses"]:
                        print("Maximum ending advances reached without marker; stopped safely.", flush=True)
                        break
                    run("xdotool", "key", "--window", window, "Return")
                    state["press_offset"] += 1
                    save_json(state_path, state)
                    time.sleep(float(step.get("interval", 1.0)))
                if not state.get("ending_found") or STOP:
                    break
                while state.get("post_offset", 0) < ending["post_presses"] and not STOP:
                    run("xdotool", "key", "--window", window, "Return")
                    state["post_offset"] = state.get("post_offset", 0) + 1
                    save_json(state_path, state)
                    time.sleep(float(step.get("interval", 1.0)))
                if STOP:
                    break
                if ending.get("post_marker") and normalized(ending["post_marker"]) not in scan_ending(window, folder, display):
                    print("Post-page ending marker was not recognized; stopped for review.", flush=True)
                    break
                print(f"Confirmed scripted endpoint {ending['id']}; recording complete.", flush=True)
            elif step["action"] == "wait":
                end = time.monotonic() + float(step["seconds"])
                while time.monotonic() < end and not STOP:
                    time.sleep(max(0, min(0.2, end - time.monotonic())))
                if STOP:
                    break
            else:
                focus_window(window)
                while state["press_offset"] < step["count"] and not STOP:
                    run("xdotool", "key", "--window", window, step["key"])
                    state["press_offset"] += 1
                    save_json(state_path, state)
                    time.sleep(float(step.get("interval", 0.3)))
                if STOP:
                    break
            state["step"] += 1
            state["press_offset"] = 0
            state.pop("ending_found", None)
            state.pop("post_offset", None)
            save_json(state_path, state)
        if state["step"] == len(spec["steps"]):
            print("Route script completed. Review recording and OCR checkpoints before claiming a tested route.", flush=True)
        else:
            print(f"Stopped at step {state['step']}; state saved in {state_path}", flush=True)
    finally:
        if video.poll() is None and video.stdin:
            try:
                video.stdin.write(b"q\n")
                video.stdin.flush()
                video.wait(timeout=10)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                video.terminate()
                video.wait(timeout=5)
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGINT, on_stop)
    signal.signal(signal.SIGTERM, on_stop)
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"route_recorder: {exc}", file=sys.stderr)
        raise SystemExit(2)
