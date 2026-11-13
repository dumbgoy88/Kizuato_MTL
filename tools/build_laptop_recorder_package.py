#!/usr/bin/env python3
"""Create a portable v6 installer plus route recorder kit; no game data."""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "build/Kizuato-v6-laptop-recorder-kit.zip"
INSTALLER = ROOT / "build/Kizuato-English-v6-beta.zip"
INSTALLER_SHA256 = "7de83dbfc32b8cbed450c3b51e45ed12de99ce7c8a8b57d8a1d0b252bdea2bf8"
FILES = {
    "README-LAPTOP.txt": ROOT / "docs/laptop_recorder_readme.txt",
    "route_recorder.py": ROOT / "tools/route_recorder.py",
    "route_recorder.example.json": ROOT / "config/route_recorder.example.json",
    "route_recorder_end.example.json": ROOT / "config/route_recorder_end.example.json",
    "route_endpoints_v6.json": ROOT / "config/route_endpoints_v6.json",
    "route_recorder_details.md": ROOT / "docs/route_recorder.md",
    "route_endpoints_details.md": ROOT / "docs/route_endpoints.md",
}
FORBIDDEN = (".hdi", ".fdd", ".pak", ".exe", ".gguf", ".bin")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise ValueError(f"Refusing to overwrite {OUTPUT}")
    installer_data = INSTALLER.read_bytes()
    if sha(installer_data) != INSTALLER_SHA256:
        raise ValueError("Installer ZIP differs from the tested v6 package")
    with zipfile.ZipFile(io.BytesIO(installer_data)) as inner:
        if inner.testzip() is not None:
            raise ValueError("Installer ZIP is damaged")
        if any(n.lower().endswith(FORBIDDEN) for n in inner.namelist()):
            raise ValueError("Installer ZIP contains a forbidden payload")
    members = {name: path.read_bytes() for name, path in FILES.items()}
    members[INSTALLER.name] = installer_data
    if any(name.lower().endswith(FORBIDDEN) for name in members):
        raise ValueError("Forbidden outer payload")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w") as archive:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            OUTPUT.unlink(missing_ok=True)
            raise ValueError("Output ZIP failed integrity check")
    print(f"{OUTPUT}\n{OUTPUT.stat().st_size} bytes\nSHA-256 {sha(OUTPUT.read_bytes())}")


if __name__ == "__main__":
    main()
