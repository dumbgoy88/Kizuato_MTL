#!/usr/bin/env python3
"""Read and replace one 8.3 file in this hash-pinned PC-98 FAT12 HDI copy.

The installer verifies the entire source image and original scene PAK before
calling this module. This parser still validates BPB, FAT chains, and directory
entries instead of relying on fixed cluster numbers.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path

VOLUME_OFFSET = 38912


class FAT12Image:
    def __init__(self, data: bytes | bytearray):
        self.data = bytearray(data)
        self.volume = VOLUME_OFFSET
        if len(self.data) < self.volume + 1024:
            raise ValueError("HDI is too short")
        boot = self.data[self.volume:self.volume + 1024]
        self.bps = struct.unpack_from("<H", boot, 11)[0]
        self.spc = boot[13]
        self.reserved = struct.unpack_from("<H", boot, 14)[0]
        self.fats = boot[16]
        self.root_entries = struct.unpack_from("<H", boot, 17)[0]
        self.total_sectors = struct.unpack_from("<H", boot, 19)[0] or struct.unpack_from("<I", boot, 32)[0]
        self.spf = struct.unpack_from("<H", boot, 22)[0]
        if (self.bps, self.spc, self.reserved, self.fats, self.root_entries, self.spf) != (1024, 4, 1, 2, 1024, 4):
            raise ValueError("unexpected PC-98 FAT layout")
        if self.total_sectors * self.bps != len(self.data) - self.volume:
            raise ValueError("volume length does not match HDI")
        self.root_sectors = (self.root_entries * 32 + self.bps - 1) // self.bps
        self.root_sector = self.reserved + self.fats * self.spf
        self.data_sector = self.root_sector + self.root_sectors
        self.cluster_size = self.bps * self.spc
        self.cluster_count = (self.total_sectors - self.data_sector) // self.spc
        if not 1 <= self.cluster_count < 4085:
            raise ValueError("not a FAT12 volume")
        self.fat_start = self.volume + self.reserved * self.bps
        self.fat_bytes = self.spf * self.bps
        self.fat = bytearray(self.data[self.fat_start:self.fat_start + self.fat_bytes])
        for index in range(1, self.fats):
            start = self.fat_start + index * self.fat_bytes
            if self.data[start:start + self.fat_bytes] != self.fat:
                raise ValueError("FAT copies disagree")

    def fat_get(self, cluster: int) -> int:
        pos = cluster + cluster // 2
        if pos + 1 >= len(self.fat):
            raise ValueError("FAT entry outside table")
        word = self.fat[pos] | self.fat[pos + 1] << 8
        return (word >> 4) & 0xFFF if cluster & 1 else word & 0xFFF

    def fat_set(self, cluster: int, value: int) -> None:
        if not 0 <= value <= 0xFFF:
            raise ValueError("invalid FAT12 entry")
        pos = cluster + cluster // 2
        word = self.fat[pos] | self.fat[pos + 1] << 8
        word = (word & 0x000F) | (value << 4) if cluster & 1 else (word & 0xF000) | value
        self.fat[pos] = word & 0xFF
        self.fat[pos + 1] = word >> 8

    def cluster_offset(self, cluster: int) -> int:
        if not 2 <= cluster < self.cluster_count + 2:
            raise ValueError(f"cluster out of range: {cluster}")
        return self.volume + (self.data_sector + (cluster - 2) * self.spc) * self.bps

    def chain(self, first: int) -> list[int]:
        if first == 0:
            return []
        result = []
        seen = set()
        cluster = first
        while True:
            if cluster in seen or not 2 <= cluster < self.cluster_count + 2:
                raise ValueError("FAT chain loops or leaves volume")
            seen.add(cluster)
            result.append(cluster)
            next_cluster = self.fat_get(cluster)
            if next_cluster >= 0xFF8:
                return result
            if next_cluster in (0, 1, 0xFF7):
                raise ValueError("FAT chain ends in a free or bad cluster")
            cluster = next_cluster

    def directory(self, first: int | None) -> list[tuple[str, int, int, int, int]]:
        if first is None:
            start = self.volume + self.root_sector * self.bps
            offsets = range(start, start + self.root_entries * 32, 32)
        else:
            offsets = (at for cluster in self.chain(first)
                       for at in range(self.cluster_offset(cluster), self.cluster_offset(cluster) + self.cluster_size, 32))
        rows = []
        for at in offsets:
            name = bytes(self.data[at:at + 11])
            if name[0] == 0:
                break
            attr = self.data[at + 11]
            if name[0] == 0xE5 or attr == 0x0F or attr & 0x08:
                continue
            stem = name[:8].decode("ascii", errors="strict").rstrip()
            extension = name[8:].decode("ascii", errors="strict").rstrip()
            path_name = stem + ("." + extension if extension else "")
            first_cluster = struct.unpack_from("<H", self.data, at + 26)[0]
            size = struct.unpack_from("<I", self.data, at + 28)[0]
            rows.append((path_name, attr, first_cluster, size, at))
        return rows

    def find(self, directory: int | None, name: str) -> tuple[str, int, int, int, int]:
        found = [row for row in self.directory(directory) if row[0] == name]
        if len(found) != 1:
            raise ValueError(f"expected one {name} directory entry, found {len(found)}")
        return found[0]

    def read_file(self, first: int, size: int) -> bytes:
        clusters = self.chain(first)
        if len(clusters) != math.ceil(size / self.cluster_size):
            raise ValueError("file size and FAT chain length disagree")
        return b"".join(self.data[self.cluster_offset(c):self.cluster_offset(c) + self.cluster_size]
                        for c in clusters)[:size]

    def read_scene_pak(self) -> bytes:
        folder = self.find(None, "KIZUATO")
        if not folder[1] & 0x10:
            raise ValueError("KIZUATO is not a directory")
        file = self.find(folder[2], "MAX2_SCN.PAK")
        if file[1] & 0x10:
            raise ValueError("MAX2_SCN.PAK is a directory")
        return self.read_file(file[2], file[3])

    def file_hashes(self) -> dict[str, str]:
        """Hash every regular file for a post-install preservation check."""
        import hashlib

        found = {}
        def visit(first: int | None, prefix: str) -> None:
            for name, attr, cluster, size, _ in self.directory(first):
                if name in (".", ".."):
                    continue
                path = prefix + name
                if attr & 0x10:
                    visit(cluster, path + "/")
                else:
                    found[path] = hashlib.sha256(self.read_file(cluster, size)).hexdigest()
        visit(None, "")
        return found

    def replace_scene_pak(self, new_file: bytes) -> None:
        folder = self.find(None, "KIZUATO")
        file = self.find(folder[2], "MAX2_SCN.PAK")
        old_chain = self.chain(file[2])
        need = math.ceil(len(new_file) / self.cluster_size)
        candidates = [c for c in range(2, self.cluster_count + 2)
                      if self.fat_get(c) == 0 or c in old_chain]
        if need > len(candidates):
            raise ValueError(f"not enough free disk space: need {need} clusters, have {len(candidates)}")
        chosen = candidates[:need]
        for cluster in old_chain:
            self.fat_set(cluster, 0)
        for index, cluster in enumerate(chosen):
            self.fat_set(cluster, chosen[index + 1] if index + 1 < need else 0xFFF)
            at = self.cluster_offset(cluster)
            chunk = new_file[index * self.cluster_size:(index + 1) * self.cluster_size]
            self.data[at:at + self.cluster_size] = chunk.ljust(self.cluster_size, b"\0")
        for index in range(self.fats):
            start = self.fat_start + index * self.fat_bytes
            self.data[start:start + self.fat_bytes] = self.fat
        struct.pack_into("<H", self.data, file[4] + 26, chosen[0] if chosen else 0)
        struct.pack_into("<I", self.data, file[4] + 28, len(new_file))
        if self.read_scene_pak() != new_file:
            raise AssertionError("HDI PAK readback differs")


def replace_file(source: Path, target: Path, original_hash: str, original_pak_hash: str,
                 replacement: bytes, replacement_hash: str) -> None:
    import hashlib

    if source.resolve() == target.resolve() or target.exists():
        raise ValueError("output must be a new path distinct from source")
    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != original_hash:
        raise ValueError("unsupported source HDI revision")
    image = FAT12Image(source_bytes)
    if hashlib.sha256(image.read_scene_pak()).hexdigest() != original_pak_hash:
        raise ValueError("original scene PAK hash mismatch")
    original_files = image.file_hashes()
    if hashlib.sha256(replacement).hexdigest() != replacement_hash:
        raise ValueError("rebuilt scene PAK hash mismatch")
    image.replace_scene_pak(replacement)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    if partial.exists():
        raise ValueError("partial output already exists")
    try:
        partial.write_bytes(image.data)
        written = FAT12Image(partial.read_bytes())
        if hashlib.sha256(written.read_scene_pak()).hexdigest() != replacement_hash:
            raise AssertionError("written HDI readback failed")
        after_files = written.file_hashes()
        if set(original_files) != set(after_files) or [name for name in original_files if original_files[name] != after_files[name]] != ["KIZUATO/MAX2_SCN.PAK"]:
            raise AssertionError("an unexpected installed file changed")
        if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
            raise AssertionError("source HDI changed during install")
        partial.rename(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
