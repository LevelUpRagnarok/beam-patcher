#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/verify_installer_primary.py
# Amac: Rust TurkuazInstaller single primary, tzsetup/tzpkg ve imzali manifest byte bagini dogrular
# Modul - Python / Release structural gate
# Version: 3.0.0-candidate
# Aciklama: Tek EXE, sabit arşiv girisleri, kesin hash ve product E2E evidence; CMS/AuthentiCode ayridir
# Bagimli Oldugu Katman: tools/Confirm-TurkuazTrust.ps1 | tools/check_rust_installer_candidate.py

"""Fail-closed Rust-only structural evidence gate.

This deliberately does NOT establish CMS/Authenticode trust or GUI acceptance.
Run the protected PowerShell signer and native Windows install checks separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

from check_rust_installer_candidate import PINNED_RUST_SOURCE_SHA, section_scalars

PINNED_TURKUAZ_SOURCE_SHA = PINNED_RUST_SOURCE_SHA
SCHEMA = "levelupgt.turkuaz-rust-primary-proof.v1"
GATE_SCHEMA = "levelupgt.turkuaz-rust-primary-gate.v1"
PACKAGE_ID = "levelupgt.beampatcher.qa"
ROLE_FILES = {
    "turkuaz_setup": "primary/TurkuazSetup.exe",
    "rust_package": "primary/Beam.tzpkg",
    "rust_bundle": "primary/Beam.tzsetup",
    "manifest": "primary/release.yaml",
    "manifest_detached_signature": "primary/release.p7s",
    "external_trust_policy": "primary/manifest-trust.yaml",
}
BUNDLE_ENTRIES = {
    "bundle.json",
    "release.yaml",
    "release.p7s",
    "application.tzpkg",
    "setup-theme.json",
}
REQUIRED_ACCEPTANCE = (
    "turkuaz_signed_manifest_and_trust",
    "turkuaz_authenticode_publisher",
    "turkuaz_install",
    "turkuaz_update",
    "turkuaz_repair",
    "turkuaz_rollback",
    "turkuaz_uninstall",
    "user_config_preserved",
    "windows_10_gui",
    "windows_11_gui",
    "non_admin_unicode_paths",
    "legacy_migration_consent",
)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("TURKUAZ-RUST-ONLY FAIL: " + message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _archive_member_digest(archive: zipfile.ZipFile, item: zipfile.ZipInfo) -> str:
    h = hashlib.sha256()
    with archive.open(item) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_bundle(root: Path, package_id: str, version: str,
                   roles: dict[str, dict]) -> None:
    bundle = root / ROLE_FILES["rust_bundle"]
    package = root / ROLE_FILES["rust_package"]
    manifest = root / ROLE_FILES["manifest"]
    signature = root / ROLE_FILES["manifest_detached_signature"]
    ensure(zipfile.is_zipfile(bundle), "Rust tzsetup bundle is not a ZIP")
    with zipfile.ZipFile(bundle) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        ensure(len(members) == 5 and set(names) == BUNDLE_ENTRIES,
               "Rust tzsetup entry set must exactly match format v2")
        ensure(len(set(n.casefold() for n in names)) == 5,
               "duplicate or case-colliding Rust setup entries")
        for item in members:
            mode = item.external_attr >> 16
            ensure(not item.is_dir() and not (mode & 0o170000) == 0o120000,
                   "Rust tzsetup must contain regular files only")
        meta = archive.getinfo("bundle.json")
        ensure(0 < meta.file_size <= 16384, "Rust tzsetup metadata too large")
        info = json.loads(archive.read(meta))
        required = {
            "formatVersion", "packageId", "version",
            "manifestSizeBytes", "manifestSha256",
            "signatureSizeBytes", "signatureSha256",
            "artifactSizeBytes", "artifactSha256",
            "themeSizeBytes", "themeSha256",
        }
        ensure(isinstance(info, dict) and set(info) == required,
               "Rust tzsetup schema is not version 2")
        ensure(info["formatVersion"] == 2 and info["packageId"] == package_id
               and info["version"] == version,
               "Rust tzsetup package identity mismatch")
        expected = {
            "release.yaml": ("manifest", "manifestSizeBytes", "manifestSha256", 1048576),
            "release.p7s": ("manifest_detached_signature", "signatureSizeBytes",
                            "signatureSha256", 262144),
            "application.tzpkg": ("rust_package", "artifactSizeBytes",
                                   "artifactSha256", 32 * 1024**3),
        }
        for name, (role, len_key, hash_key, cap) in expected.items():
            member = archive.getinfo(name)
            ensure(0 < member.file_size <= cap and member.file_size == roles[role]["bytes"],
                   "Rust setup entry size mismatch: " + name)
            ensure(member.file_size == info[len_key] and
                   roles[role]["sha256"] == info[hash_key] and
                   _archive_member_digest(archive, member) == roles[role]["sha256"],
                   "Rust setup entry digest mismatch: " + name)
        theme = archive.getinfo("setup-theme.json")
        ensure(0 < theme.file_size <= 1048576 and
               theme.file_size == info["themeSizeBytes"] and
               _archive_member_digest(archive, theme) == info["themeSha256"],
               "Rust setup theme digest mismatch")

    signed_manifest = manifest.read_text(encoding="utf-8-sig")
    identity = section_scalars(signed_manifest, "package", ("id", "version"))
    artifact = section_scalars(signed_manifest, "artifact", ("sha256", "size_bytes"))
    ensure(identity == {"id": package_id, "version": version},
           "signed Rust manifest identity mismatch")
    ensure(artifact["sha256"].lower() == roles["rust_package"]["sha256"] and
           artifact["size_bytes"] == str(package.stat().st_size),
           "signed Rust manifest does not bind exact tzpkg bytes")
    ensure(signature.stat().st_size > 0, "detached CMS is missing")


def verify(bundle_root: Path, metadata: dict, source_sha: str, version: str,
           expected_package: Path | None = None) -> dict:
    root = bundle_root.resolve(strict=True)
    ensure(root.is_dir(), "Rust distribution root missing")
    ensure(re.fullmatch(r"[a-f0-9]{40}", source_sha) is not None,
           "exact source commit required")
    ensure(isinstance(metadata, dict) and metadata.get("schema") == SCHEMA,
           "unsupported Rust distribution proof schema")
    ensure(metadata.get("source_sha") == source_sha, "Beam source mismatch")
    ensure(metadata.get("turkuaz_source_sha") == PINNED_TURKUAZ_SOURCE_SHA,
           "pinned Rust Turkuaz source mismatch")
    ensure(metadata.get("version") == version and
           re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version),
           "Rust product version mismatch")
    ensure(metadata.get("architecture") == "win-x64", "expected win-x64")
    ensure(metadata.get("product_id") == PACKAGE_ID, "Rust package id mismatch")
    ensure(metadata.get("primary_role") == "rust-turkuazinstaller",
           "only the Rust Turkuaz primary is allowed")
    ensure("fallback_role" not in metadata and "public_fallback" not in metadata,
           "secondary installer proof forbidden")
    ensure(metadata.get("release_ready") is True and
           metadata.get("signed_production_binary") is True and
           metadata.get("signed_cms_manifest") is True and
           metadata.get("external_cert_pin_verified") is True,
           "real production signature and release acceptance are mandatory")
    acceptance = metadata.get("acceptance")
    ensure(isinstance(acceptance, dict) and set(acceptance) == set(REQUIRED_ACCEPTANCE),
           "complete external native Rust acceptance proof required")
    for required in REQUIRED_ACCEPTANCE:
        ensure(acceptance[required] == "PASS", required + " is not accepted")

    # Do not permit stray or disguised executables beside the pinned primary.
    for name in ("backup", "secondary", "primary/Beam-Velopack-Setup.exe",
                 "primary/TurkuazInstaller.Bootstrapper.exe",
                 "primary/TurkuazInstallerBackup.exe"):
        other = root / name
        ensure(not other.exists() and not other.is_symlink(),
               "retired installer artifact is present: " + name)
    primary_dir = root / "primary"
    ensure(primary_dir.is_dir() and not primary_dir.is_symlink(),
           "primary is missing or a filesystem link")
    files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    ensure(files == set(ROLE_FILES.values()),
           "unexpected installer or unverified file in Rust product bundle")
    ensure(not any(p.is_symlink() for p in root.rglob("*")),
           "linked Rust release inputs forbidden")
    pins = metadata.get("artifact_sha256")
    ensure(isinstance(pins, dict) and set(pins) == set(ROLE_FILES),
           "all six Rust artifact roles must be hash-pinned")
    actual = {}
    for role, relative in ROLE_FILES.items():
        path = root / relative
        ensure(path.is_file() and not path.is_symlink() and
               path.resolve().is_relative_to(root), role + " missing or linked")
        size = path.stat().st_size
        minimum = 1024 if role in ("turkuaz_setup", "rust_package", "rust_bundle") else 1
        ensure(size >= minimum, role + " is suspiciously small")
        if role == "manifest":
            ensure(size <= 1048576, "Rust manifest too large")
        if role == "manifest_detached_signature":
            ensure(size <= 262144, "Rust CMS too large")
        if role == "external_trust_policy":
            ensure(size <= 65536, "Rust trust policy too large")
        digest = sha256_file(path)
        ensure(pins[role] == digest, role + " SHA-256 mismatch")
        actual[role] = {"path": relative, "sha256": digest, "bytes": size}
    with (root / ROLE_FILES["turkuaz_setup"]).open("rb") as exe:
        ensure(exe.read(2) == b"MZ", "Rust TurkuazSetup is not a Windows PE")
    if expected_package is not None:
        ensure(expected_package.is_file() and not expected_package.is_symlink(),
               "expected Beam Rust build .tzpkg missing")
        ensure(sha256_file(expected_package) == actual["rust_package"]["sha256"],
               "signed Rust release is not the freshly built Beam tzpkg")
    _verify_bundle(root, PACKAGE_ID, version, actual)
    return {
        "schema": GATE_SCHEMA,
        "source_sha": source_sha,
        "turkuaz_source_sha": PINNED_TURKUAZ_SOURCE_SHA,
        "version": version,
        "primary": actual["turkuaz_setup"],
        "verified_files": actual,
        "primary_download_only": True,
        "gate": "PASS",
        "note": "STRUCTURAL ONLY: CMS, Authenticode and native E2E must pass independently",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-package", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
        report = verify(args.bundle, evidence, args.source_sha, args.version,
                        args.expected_package)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("TURKUAZ_RUST_PRIMARY_STRUCTURAL_PASS_NOT_CRYPTOGRAPHIC")
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            json.JSONDecodeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        print("TURKUAZ_RUST_PRIMARY_FAIL_CLOSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
