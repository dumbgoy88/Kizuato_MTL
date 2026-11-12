#!/usr/bin/env python3
"""Copy an HDI, replace one DOS file on the copy, and verify its readback."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

EXPECTED_SHA256 = "783adfa48bf5b8efcb9ae681e726f3c6180e8cac2d2bc568a5953aa32b992d04"
VOLUME_OFFSET = 38912


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mcopy(*args: str) -> None:
    env = os.environ.copy()
    env["MTOOLS_SKIP_CHECK"] = "1"
    subprocess.run(["mcopy", *args], check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_hdi", type=Path)
    parser.add_argument("output_hdi", type=Path)
    parser.add_argument("host_file", type=Path)
    parser.add_argument("dos_path", help="for example KIZUATO/MAX2_SCN.PAK")
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    args = parser.parse_args()
    source = args.source_hdi.resolve()
    output = args.output_hdi.resolve()
    host = args.host_file.resolve()
    if source == output or source == host or output == host:
        raise SystemExit("input, output, and replacement paths must differ")
    if output.exists():
        raise SystemExit("refusing to overwrite existing output HDI")
    if not source.is_file() or not host.is_file():
        raise SystemExit("missing input HDI or host file")
    source_hash = digest(source)
    if source_hash != args.expected_sha256:
        raise SystemExit(f"unexpected input HDI SHA-256: {source_hash}")
    if not args.dos_path.startswith("KIZUATO/") or ".." in args.dos_path:
        raise SystemExit("DOS target must be inside KIZUATO")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    image_spec = f"{output}@@{VOLUME_OFFSET}"
    dos_spec = f"::{args.dos_path}"
    try:
        mcopy("-o", "-i", image_spec, str(host), dos_spec)
        with tempfile.TemporaryDirectory() as tmp:
            readback = Path(tmp) / host.name
            mcopy("-i", image_spec, dos_spec, str(readback))
            if readback.read_bytes() != host.read_bytes():
                raise ValueError("readback differs from replacement file")
        if digest(source) != source_hash:
            raise ValueError("source HDI changed unexpectedly")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    print(f"copied {source.name} to {output}")
    print(f"verified {args.dos_path} SHA-256: {digest(host)}")
    print(f"source HDI remains SHA-256: {source_hash}")


if __name__ == "__main__":
    main()
