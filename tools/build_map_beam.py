#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/build_map_beam.py
# Amac: RagnarokClient grouped maps/manifest.json -> safe offline BEAM v1 candidate
# Modul - Python CLI
# Version: 0.1.0-candidate
# Aciklama: Uses beam-formats/src/beam.rs BEAM v1 wire layout; never GRF/client writes.
# Bagimli Oldugu Katman: beam-formats/src/beam.rs | RagnarokClient map catalog v2
"""Create a GRF-path-correct BEAM v1 archive (offline only, never deploy)."""

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import zlib
from pathlib import Path

SCHEMA = "levelupgt.addon-map-assets.v2"
MAP_NAME = re.compile(r"[A-Za-z0-9_@-]{1,11}\Z")
GROUP = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")
MAGIC = {"gat": b"GRAT", "gnd": b"GRGN", "rsw": b"GRSW"}
HEADER_SIZE = 64
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_asset(path, ext):
    require(path.is_file() and not path.is_symlink(), "MISSING_OR_LINKED_ASSET: " + path.name)
    require(6 <= path.stat().st_size <= MAX_FILE, "INVALID_ASSET_SIZE: " + path.name)
    raw = path.read_bytes()
    require(raw[:4] == MAGIC[ext], "INVALID_MAP_HEADER: " + path.name)
    if ext == "gat":
        require(len(raw) >= 14, "GAT_HEADER_TRUNCATED")
        w, h = struct.unpack_from("<II", raw, 6)
        require(0 < w <= 4096 and 0 < h <= 4096 and
                len(raw) == 14 + w * h * 20, "GAT_DIMENSIONS_INVALID: " + path.name)
    return raw


def gather(assets_root, manifest_file):
    """Fail closed for missing/hidden/extra map assets, path collisions, hash drift."""
    require(assets_root.is_dir() and not assets_root.is_symlink(), "INVALID_CLIENT_MAPS_ROOT")
    require(manifest_file.is_file() and not manifest_file.is_symlink() and
            manifest_file.stat().st_size <= 128 * 1024, "INVALID_MAP_MANIFEST")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA,
            "UNSUPPORTED_GROUPED_MAP_SCHEMA")
    rows = manifest.get("maps")
    require(isinstance(rows, list) and 0 < len(rows) <= 50, "INVALID_MAP_COUNT")
    data_root = assets_root / "data"
    require(data_root.is_dir() and not data_root.is_symlink(), "CLIENT_MAP_DATA_DIRECTORY_MISSING")
    expected, used, payload, total = set(), set(), [], 0
    for row in rows:
        require(isinstance(row, dict), "INVALID_MAP_ENTRY")
        group, name = row.get("group"), row.get("name")
        require(isinstance(group, str) and GROUP.fullmatch(group) and
                isinstance(name, str) and MAP_NAME.fullmatch(name),
                "INVALID_MAP_GROUP_OR_NAME")
        folded = name.casefold()
        require(folded not in used, "MAP_NAME_COLLISION: " + name)
        used.add(folded)
        folder = data_root / group
        require(folder.is_dir() and not folder.is_symlink(), "MAP_GROUP_MISSING_OR_LINKED")
        for ext in ("gat", "gnd", "rsw"):
            filename = name + "." + ext
            digest = row.get(ext + "_sha256")
            require(isinstance(digest, str) and HASH.fullmatch(digest),
                    "MAP_SHA256_MISSING: " + filename)
            raw = safe_asset(folder / filename, ext)
            require(hashlib.sha256(raw).hexdigest() == digest,
                    "MAP_SHA256_MISMATCH: " + filename)
            total += len(raw)
            require(total <= MAX_TOTAL, "MAP_COLLECTION_TOO_LARGE")
            expected.add((group, filename))
            # Beam Patcher writes entry.filename to GRF if grf_path=None.
            # Never retain the group directory inside actual GRF paths.
            payload.append(("data\\" + filename, raw))
    actual = set()
    for directory in data_root.iterdir():
        if directory.name in (".gitkeep", "README.md") and directory.is_file():
            continue
        require(directory.is_dir() and not directory.is_symlink() and GROUP.fullmatch(directory.name),
                "UNEXPECTED_MAP_PACK_DIRECTORY")
        for entry in directory.iterdir():
            require(entry.is_file() and not entry.is_symlink(), "UNSAFE_MAP_ASSET_ENTRY")
            if entry.name not in (".gitkeep", "README.md"):
                actual.add((directory.name, entry.name))
    require(actual == expected, "CLIENT_MAP_CATALOG_STALE_OR_EXTRA_FILES")
    return sorted(payload, key=lambda pair: pair[0].casefold())


def make_archive(entries):
    require(entries and len(entries) <= 150, "INVALID_BEAM_ENTRY_COUNT")
    table, chunks, position = bytearray(), [], HEADER_SIZE
    for name, raw in entries:
        encoded = name.encode("ascii")
        require(0 < len(encoded) <= 255 and name.startswith("data\\") and
                "\\" not in name[5:] and "/" not in name and ".." not in name,
                "UNSAFE_BEAM_GRF_ENTRY")
        compressed = zlib.compress(raw, 6)
        chunks.append(compressed)
        position += 1 + len(encoded) + 16 + 4 + 4 + 8 + 1
    data_offset = position
    for (name, raw), compressed in zip(entries, chunks):
        encoded = name.encode("ascii")
        table.extend(bytes([len(encoded)]) + encoded)
        table.extend(hashlib.md5(raw).digest())  # Wire format is MD5; source pins are SHA256.
        table.extend(struct.pack("<IIQ", len(compressed), len(raw), data_offset))
        table.extend(b"\x00")  # No GRF alias; filename is the flat GRF path.
        data_offset += len(compressed)
    return (b"BEAM" + struct.pack("<II", 1, len(entries)) + bytes(52) +
            bytes(table) + b"".join(chunks))


def verify_archive(blob, originals):
    require(len(blob) >= HEADER_SIZE and blob[:4] == b"BEAM",
            "BAD_BEAM_SIGNATURE")
    version, count = struct.unpack_from("<II", blob, 4)
    require(version == 1 and count == len(originals), "BAD_BEAM_VERSION_OR_COUNT")
    require(blob[12:64] == bytes(52), "BEAM_RESERVED_BYTES_CHANGED")
    offset, seen, next_payload_offset = HEADER_SIZE, {}, None
    for _ in range(count):
        require(offset + 1 <= len(blob), "BEAM_TRUNCATED_TABLE")
        name_len = blob[offset]
        offset += 1
        require(name_len > 0 and offset + name_len + 33 <= len(blob),
                "BEAM_TRUNCATED_ENTRY")
        name = blob[offset:offset + name_len].decode("ascii")
        offset += name_len
        digest = blob[offset:offset + 16]
        offset += 16
        compressed_size, size, data_offset = struct.unpack_from("<IIQ", blob, offset)
        offset += 16
        alias_size = blob[offset]
        offset += 1
        require(alias_size == 0 and name not in seen, "UNEXPECTED_GRFPATH_OR_DUPLICATE")
        require(compressed_size > 0 and 0 < size <= MAX_FILE and
                data_offset + compressed_size <= len(blob), "BEAM_PAYLOAD_OUT_OF_RANGE")
        if next_payload_offset is None:
            first_payload_offset = data_offset
        else:
            require(data_offset == next_payload_offset, "BEAM_PAYLOAD_OFFSET_DRIFT")
        next_payload_offset = data_offset + compressed_size
        decoder = zlib.decompressobj()
        raw = decoder.decompress(blob[data_offset:next_payload_offset], size + 1)
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and
                len(raw) == size and hashlib.md5(raw).digest() == digest,
                "BEAM_PAYLOAD_HASH_MISMATCH")
        seen[name] = raw
    require(offset == first_payload_offset and next_payload_offset == len(blob),
            "BEAM_TABLE_OFFSET_DRIFT")
    require(seen == dict(originals), "BEAM_ROUNDTRIP_MISMATCH")


def build(assets_root, manifest_path, output):
    require(output.suffix.lower() == ".beam" and output.name == "custom-maps.beam",
            "ONLY_CUSTOM_MAPS_BEAM_CANDIDATE_SUPPORTED")
    entries = gather(assets_root, manifest_path)
    blob = make_archive(entries)
    verify_archive(blob, entries)
    require(output.parent.is_dir() and not output.parent.is_symlink(), "OUTPUT_PARENT_MISSING")
    # 'xb' is an atomic no-overwrite check, even when multiple processes race.
    with output.open("xb") as stream:
        try:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            output.unlink(missing_ok=True)
            raise
    return {"file": str(output), "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "map_count": len(entries) // 3, "asset_count": len(entries),
            "target_grf_candidate": "tdata1.grf",
            "deployed": False}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--assets-root", type=Path, required=True)
    cli.add_argument("--manifest", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    print("BEAM_MAP_BUILD_RESULT " +
          json.dumps(build(args.assets_root, args.manifest, args.output), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            struct.error, zlib.error, json.JSONDecodeError) as exc:
        print("BEAM_MAP_BUILD_BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(1)
