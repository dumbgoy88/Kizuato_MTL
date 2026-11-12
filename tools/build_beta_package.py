#!/usr/bin/env python3
"""Package the v6 English edit instructions and installer, without game files."""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
NAME = "Kizuato-English-v6-beta"
EDITS = BUILD / "all-english-diagnostic-20261111-v6-unsafe-intermediate-edits.json"
EXPECTED_EDITS = "a1e846b6d25d4fc0d12ac2a5918a5d2451bd6d3b3269936be1ea2efb7d34a26b"
FINAL_PAK = BUILD / "all-english-diagnostic-20261111-v6.PAK"
EXPECTED_PAK = "b5a64890f9ffca8e7c02625696c866629d5e1f2b78c0540e7a86c3a1b4389249"
SOURCES = {
    "install.py": ROOT / "tools/beta_install.py",
    "fat12_hdi.py": ROOT / "tools/fat12_hdi.py",
    "leafpack_pc98.py": ROOT / "tools/leafpack_pc98.py",
    "scenes.py": ROOT / "tools/scenes.py",
    "event_graph.py": ROOT / "tools/event_graph.py",
    "split_pages.py": ROOT / "tools/split_pages.py",
    "audit_split_pages.py": ROOT / "tools/audit_split_pages.py",
    "README.txt": ROOT / "docs/beta_installer_readme.txt",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    package_dir = BUILD / NAME
    archive_path = BUILD / (NAME + ".zip")
    if package_dir.exists() or archive_path.exists():
        raise ValueError("beta package exists; choose a new version before rebuilding")
    edit_bytes = EDITS.read_bytes()
    if digest(edit_bytes) != EXPECTED_EDITS or digest(FINAL_PAK.read_bytes()) != EXPECTED_PAK:
        raise ValueError("v6 edit instructions or verified PAK changed")
    edits = json.loads(edit_bytes)
    if len(edits) != 3264 or len({row["id"] for row in edits}) != 3264:
        raise ValueError("unexpected beta edit IDs")
    if any(set(row) - {"id", "source_sha256", "text_runs", "format"} for row in edits):
        raise ValueError("edit package contains source/game fields")
    package_dir.mkdir(parents=True)
    try:
        for name, source in SOURCES.items():
            shutil.copyfile(source, package_dir / name)
        (package_dir / "edits.json.gz").write_bytes(gzip.compress(edit_bytes, compresslevel=9, mtime=0))
        (package_dir / "Install beta.bat").write_bytes(
            b'@echo off\r\nif "%~1"=="" (\r\n  echo Drag a clean Kizuato HDI onto this file.\r\n  pause\r\n  exit /b 1\r\n)\r\npy -3 "%~dp0install.py" "%~1"\r\npause\r\n')
        files = sorted(p for p in package_dir.iterdir() if p.is_file())
        manifest = {"version": "v6-beta", "source_hdi_sha256":
                    "783adfa48bf5b8efcb9ae681e726f3c6180e8cac2d2bc568a5953aa32b992d04",
                    "patched_scene_pak_sha256": EXPECTED_PAK,
                    "files": {p.name: digest(p.read_bytes()) for p in files}}
        (package_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(package_dir.iterdir()):
                info = zipfile.ZipInfo(f"{NAME}/{path.name}", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP integrity check failed")
            names = archive.namelist()
            if any(name.lower().endswith((".hdi", ".pak", ".kcd", ".exe")) for name in names):
                raise ValueError("game asset in beta package")
        print(f"Package: {archive_path}")
        print(f"Size: {archive_path.stat().st_size} bytes")
        print(f"SHA-256: {digest(archive_path.read_bytes())}")
    except Exception:
        archive_path.unlink(missing_ok=True)
        shutil.rmtree(package_dir)
        raise


if __name__ == "__main__":
    main()
