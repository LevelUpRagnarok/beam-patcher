#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/check_rust_installer_candidate.py
# Amac: Rust TurkuazInstaller .tzpkg ve unsigned manifest onizleme kontratini dogrulamak
# Modul - Python / Offline candidate package contract
# Version: 1.0.0-candidate
# Aciklama: Kaynak SHA, archive payload, package metadata ve manifest byte bagini denetler; imza dogrulamaz
# Bagimli Oldugu Katman: TurkuazInstaller/rust/PACKAGE_FORMAT.md | tools/tests/test_rust_installer_candidate.py

"""Read-only, fail-closed structural audit of a Rust TurkuazInstaller candidate.

This is NOT a CMS, Authenticode, Windows installation or release gate.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

PINNED_RUST_SOURCE_SHA = "456a34679661978afc717cc5b08ece11cb0b9a94"
PACKAGE_FORMAT_VERSION = 2
PACKAGE_META = "turkuaz-package.json"
PAYLOAD_PREFIX = "payload/"
REQUIRED_QA_FILES = {"beam-patcher.exe", "config.yml", "README-QA.txt"}


def refuse(message: str) -> None:
    raise ValueError("RUST_BEAM_CANDIDATE_FAIL: " + message)


def section_scalars(source: str, section: str, fields: tuple[str, ...]) -> dict:
    """Parse only the simple scalar subset emitted by Rust describe-package."""
    top = list(re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_]*):[ \t]*\r?$", source))
    selected = [m for m in top if m.group(1) == section]
    if len(selected) != 1:
        refuse("missing or repeated manifest section: " + section)
    m = selected[0]
    next_top = next((a for a in top if a.start() > m.start()), None)
    body = source[m.end():next_top.start() if next_top else len(source)]
    found = {}
    for line in body.splitlines():
        match = re.fullmatch(r"  ([a-z_]+):[ \t]*(.*)", line)
        if not match or match.group(1) not in fields:
            continue
        key, value = match.groups()
        if key in found:
            refuse("duplicate manifest field: " + section + "." + key)
        value = value.strip()
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                refuse("invalid quoted manifest scalar: " + key)
            value = value[1:-1]
        if not value or "#" in value or any(c in value for c in ('"', "'")):
            refuse("unsafe manifest scalar: " + key)
        found[key] = value
    for key in fields:
        if key not in found:
            refuse("missing manifest field: " + section + "." + key)
    return found


def audit(package: Path, manifest: Path, payload: Path, upstream_sha: str,
          package_id: str, version: str) -> dict:
    if upstream_sha != PINNED_RUST_SOURCE_SHA:
        refuse("Rust upstream source revision differs from audited checkout")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", package_id):
        refuse("invalid package id")
    if not re.fullmatch(r"0|[1-9][0-9]*", version.split(".")[0]) or not re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+", version):
        refuse("unsupported QA package version")
    if any(not f.is_file() or f.is_symlink() for f in (package, manifest)):
        refuse("missing or linked package/manifest")
    if not payload.is_dir() or payload.is_symlink():
        refuse("missing or linked payload root")
    if manifest.stat().st_size > 1048576 or manifest.stat().st_size == 0:
        refuse("invalid manifest size")

    raw_package = package.read_bytes()
    digest = hashlib.sha256(raw_package).hexdigest()
    drafted = manifest.read_text(encoding="utf-8-sig")
    declared_pkg = section_scalars(drafted, "package", ("id", "version"))
    declared_artifact = section_scalars(drafted, "artifact", ("sha256", "size_bytes"))
    if declared_pkg != {"id": package_id, "version": version}:
        refuse("manifest package identity mismatch")
    if declared_artifact["sha256"].lower() != digest:
        refuse("unsigned draft SHA-256 mismatch")
    if declared_artifact["size_bytes"] != str(len(raw_package)):
        refuse("unsigned draft byte count mismatch")

    expected_files = {}
    for p in payload.rglob("*"):
        if p.is_symlink():
            refuse("payload symlink is forbidden")
        if p.is_dir():
            continue
        if not p.is_file():
            refuse("nonregular source payload file")
        relative = p.relative_to(payload).as_posix()
        if relative.casefold() in (key.casefold() for key in expected_files):
            refuse("case collision in payload source")
        expected_files[relative] = hashlib.sha256(p.read_bytes()).hexdigest()
    if not REQUIRED_QA_FILES.issubset(expected_files):
        refuse("Beam QA executable/config/guide missing")
    if "qa_only: true" not in (payload / "config.yml").read_text(encoding="utf-8"):
        refuse("Beam QA-only config not enforced")

    try:
        with zipfile.ZipFile(package) as archive:
            entries = archive.infolist()
            names = set()
            actual_files = {}
            for item in entries:
                name = item.filename
                path = PurePosixPath(name)
                if (not name or "\\" in name or name.startswith("/") or
                        any(part in ("..", ".") for part in path.parts) or
                        (item.external_attr >> 16) & 0o170000 == 0o120000):
                    refuse("unsafe archive entry path/type")
                if name.casefold() in names:
                    refuse("duplicate archive entry")
                names.add(name.casefold())
                if name == PACKAGE_META:
                    continue
                if not name.startswith(PAYLOAD_PREFIX):
                    refuse("unknown archive root entry")
                if item.is_dir():
                    continue
                relative = name[len(PAYLOAD_PREFIX):]
                if not relative:
                    refuse("empty payload archive entry")
                actual_files[relative] = hashlib.sha256(archive.read(item)).hexdigest()

            if PACKAGE_META not in archive.namelist():
                refuse("missing Rust archive metadata")
            metadata_bytes = archive.read(PACKAGE_META)
            if len(metadata_bytes) > 65536:
                refuse("Rust archive metadata exceeds cap")
            data = json.loads(metadata_bytes)
            if (not isinstance(data, dict) or set(data) !=
                    {"formatVersion", "packageId", "version", "entryPoint"}):
                refuse("unknown Rust v2 archive identity fields")
            if (data["formatVersion"] != PACKAGE_FORMAT_VERSION or
                    data["packageId"] != package_id or data["version"] != version or
                    data["entryPoint"] != "beam-patcher.exe"):
                refuse("Rust archive version/package/entrypoint mismatch")
            if actual_files != expected_files:
                refuse("Rust archive payload differs from staged Beam files")
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError) as exc:
        refuse("invalid Rust archive/metadata: " + type(exc).__name__)

    return {
        "status": "PASS_UNSIGNED_STRUCTURAL_ONLY",
        "upstream_source_sha": upstream_sha,
        "package_id": package_id,
        "version": version,
        "package_sha256": digest,
        "package_bytes": len(raw_package),
        "verified_payload_files": len(expected_files),
        "release_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--upstream-sha", required=True)
    parser.add_argument("--package-id", default="levelupgt.beampatcher.qa")
    parser.add_argument("--version", default="1.0.1")
    args = parser.parse_args()
    try:
        result = audit(args.package, args.manifest, args.payload,
                       args.upstream_sha, args.package_id, args.version)
        print("RUST_BEAM_CANDIDATE_CONTRACT_PASS_NO_SIGNING")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.LargeZipFile) as exc:
        print("RUST_BEAM_CANDIDATE_FAIL_CLOSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
