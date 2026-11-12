#!/usr/bin/env python3
"""Install the Kizuato English v6 beta onto a clean owned PC-98 HDI.

No game image, rebuilt archive, model, or Japanese source text ships with the
installer. The package contains English edit instructions and build code.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from fat12_hdi import FAT12Image, replace_file

BASE = Path(__file__).resolve().parent
ORIGINAL_HDI_SHA256 = "783adfa48bf5b8efcb9ae681e726f3c6180e8cac2d2bc568a5953aa32b992d04"
ORIGINAL_PAK_SHA256 = "beec74329493a72fcdb61c914539d3d210f0193d714fdc583189aec1e9a5cace"
EDITS_SHA256 = "a1e846b6d25d4fc0d12ac2a5918a5d2451bd6d3b3269936be1ea2efb7d34a26b"
PAGED_PAK_SHA256 = "3e08ea4d39f74320bcbd4a3d7b017378df07bd22026c2a40655ca22f95d1c3ad"
FINAL_PAK_SHA256 = "b5a64890f9ffca8e7c02625696c866629d5e1f2b78c0540e7a86c3a1b4389249"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True, cwd=BASE)


def install(source: Path, output: Path) -> None:
    if sys.version_info < (3, 10):
        raise ValueError("Python 3.10 or newer is required")
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file() or source == output or output.exists():
        raise ValueError("choose an existing original HDI and a new output filename")
    print("Checking clean Kizuato HDI...", flush=True)
    source_data = source.read_bytes()
    if sha256(source_data) != ORIGINAL_HDI_SHA256:
        raise ValueError("unsupported HDI revision or modified/save-bearing image; see README.txt")
    original_pak = FAT12Image(source_data).read_scene_pak()
    if sha256(original_pak) != ORIGINAL_PAK_SHA256:
        raise ValueError("original scene archive hash mismatch")
    edits_data = gzip.decompress((BASE / "edits.json.gz").read_bytes())
    if sha256(edits_data) != EDITS_SHA256:
        raise ValueError("beta edit package hash mismatch")
    edits = json.loads(edits_data)
    if len(edits) != 3264 or len({row["id"] for row in edits}) != 3264:
        raise ValueError("beta edit ID count or uniqueness check failed")
    if any(set(row) - {"id", "source_sha256", "text_runs", "format"} for row in edits):
        raise ValueError("unexpected edit-package field")
    with tempfile.TemporaryDirectory(prefix="kizuato-beta-") as directory:
        temp = Path(directory)
        source_pak = temp / "original.PAK"
        paged_pak = temp / "paged.PAK"
        final_pak = temp / "patched.PAK"
        edits_path = temp / "edits.json"
        table_path = temp / "structural.tbl"
        split_report = temp / "split.json"
        audit_report = temp / "audit.json"
        source_pak.write_bytes(original_pak)
        edits_path.write_bytes(edits_data)
        # Only glyph boundaries and command bytes are needed to build a patch.
        # This synthetic table does not contain Japanese script or game font data.
        table_path.write_bytes(("　■ＡＢＣ" + "?" * 9000).encode("euc_jp"))
        print("Building English scene archive...", flush=True)
        run(str(BASE / "scenes.py"), "apply", str(source_pak), str(table_path),
            str(edits_path), str(paged_pak))
        if sha256(paged_pak.read_bytes()) != PAGED_PAK_SHA256:
            raise ValueError("paged archive differs from verified beta build")
        run(str(BASE / "split_pages.py"), str(source_pak), str(paged_pak),
            str(edits_path), str(table_path), str(final_pak), str(split_report),
            "--allow-unreferenced")
        final_data = final_pak.read_bytes()
        if sha256(final_data) != FINAL_PAK_SHA256:
            raise ValueError("final archive differs from verified beta build")
        run(str(BASE / "audit_split_pages.py"), str(paged_pak), str(final_pak),
            str(edits_path), str(table_path), str(audit_report))
        audit = json.loads(audit_report.read_text())
        if (audit.get("split_messages"), audit.get("continuation_messages"),
                audit.get("choice_groups_within_24x12"), len(audit.get("unreferenced_unsplit", []))) != (2566, 3493, 47, 12):
            raise ValueError("beta structural audit differs from verified build")
        print("Writing and verifying new HDI...", flush=True)
        replace_file(source, output, ORIGINAL_HDI_SHA256, ORIGINAL_PAK_SHA256,
                     final_data, FINAL_PAK_SHA256)
    print(f"Installed: {output}")
    print("Original HDI was not changed. Keep the beta image and saves separate.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_hdi", type=Path, help="clean original Kizuato HDI")
    parser.add_argument("--output", type=Path, help="new beta HDI path (default: alongside input)")
    args = parser.parse_args()
    output = args.output or args.original_hdi.with_name(args.original_hdi.stem + "-English-v6-beta.hdi")
    try:
        install(args.original_hdi, output)
    except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Installation failed: {exc}\n")


if __name__ == "__main__":
    main()
