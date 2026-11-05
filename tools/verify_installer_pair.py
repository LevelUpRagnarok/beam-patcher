#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/verify_installer_pair.py
# Amac: BURAK-INS-001 dual-output installer metadata/byte ve paylasim kapi kontrati
# Modul - Python / QA policy checker
# Version: 1.1.0-candidate
# Aciklama: Identity/size/hash/report denetler; native CMS/AuthentiCode/Velopack E2E yerine gecmez
# Bagimli Oldugu Katman: docs/INSTALLER-STRATEGY-TURKUAZ.md | installer/windows

"""Fail-closed secondary gate for Windows dual-installer artifact metadata.

This cannot independently verify CMS or Authenticode signatures. Those must
have passed the real signed TurkuazInstaller runtime/Windows CI BEFORE use.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

# Supply-chain identity: matches the explicit checkout ref in
# .github/workflows/dual-installer-policy.yml. Change both only in a
# reviewed, separately tested upstream integration update.
PINNED_TURKUAZ_SOURCE_SHA = "1048931bf7498ab4d4440414c4463e6ee5e7421e"

ROLE_FILES = {
    "turkuaz_bootstrapper": "primary/TurkuazInstaller.Bootstrapper.exe",
    "turkuaz_winui": "primary/app/TurkuazInstaller.WinUI.exe",
    "turkuaz_cli": "primary/cli/TurkuazInstaller.Cli.exe",
    "velopack_setup": "primary/Beam-Velopack-Setup.exe",
    "velopack_full_nupkg": "primary/Beam-full.nupkg",
    "manifest": "primary/installer-manifest.yml",
    "manifest_detached_signature": "primary/installer-manifest.yml.p7s",
    "external_trust_policy": "primary/manifest-trust.yml",
    "nsis_backup": "backup/TurkuazRagnarokOnline-NSIS-BACKUP-QA-Setup.exe",
}
REQUIRED_ACCEPTANCE = (
    "turkuaz_signed_manifest_and_trust",
    "turkuaz_authenticode_publisher",
    "turkuaz_install",
    "turkuaz_update",
    "turkuaz_repair",
    "turkuaz_rollback",
    "turkuaz_uninstall",
    "nsis_install",
    "nsis_uninstall",
    "user_config_preserved",
)


def ensure(condition, message):
    if not condition:
        raise ValueError("BURAK-INS-001 FAIL: " + message)


def verify(bundle_root: Path, metadata: dict, source_sha: str, version: str) -> dict:
    root = bundle_root.resolve(strict=True)
    ensure(root.is_dir(), "pair directory is missing")
    ensure(len(source_sha) == 40 and all(c in "0123456789abcdef" for c in source_sha.lower()),
           "exact 40-hex commit is required")
    ensure(metadata.get("schema") == "levelupgt.dual-installer-proof.v1",
           "unsupported evidence schema")
    ensure(metadata.get("source_sha") == source_sha, "source commit mismatch")
    ensure(metadata.get("turkuaz_source_sha") == PINNED_TURKUAZ_SOURCE_SHA,
           "upstream Turkuaz source commit does not match pinned checkout")
    ensure(metadata.get("version") == version, "version mismatch")
    ensure(metadata.get("architecture") == "win-x64", "only pinned win-x64 is accepted")
    ensure(metadata.get("product_id") == "levelupgt.beampatcher.qa",
           "permanent QA product ID mismatch")
    ensure(metadata.get("primary_role") == "turkuazinstaller", "primary must be Turkuaz")
    ensure(metadata.get("fallback_role") == "nsis-backup-only", "NSIS must be backup only")
    ensure(metadata.get("public_fallback") is False, "NSIS cannot be public/downloadable")
    ensure(metadata.get("release_ready") is True,
           "upstream native security/installer E2E gates are not complete")
    results = metadata.get("acceptance")
    ensure(isinstance(results, dict), "acceptance proof missing")
    for name in REQUIRED_ACCEPTANCE:
        ensure(results.get(name) == "PASS", name + " has not passed")
    pinned = metadata.get("artifact_sha256")
    ensure(isinstance(pinned, dict) and set(pinned) == set(ROLE_FILES),
           "all artifact checksums are mandatory")
    actual = {}
    for role, path in ROLE_FILES.items():
        candidate = root / path
        ensure(candidate.is_file() and not candidate.is_symlink(),
               role + " missing or symlinked")
        ensure(candidate.resolve().is_relative_to(root), role + " leaves bundle root")
        size = candidate.stat().st_size
        ensure(size >= (256 if role in ("manifest", "external_trust_policy") else 512),
               role + " is suspiciously small")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        ensure(pinned.get(role) == digest, role + " checksum mismatch")
        actual[role] = {"path": path, "sha256": digest, "bytes": size}

    # This is an additional read-only structural gate. Cryptographic CMS,
    # signer pinning and Windows E2E are separately required by the workflow.
    ensure("TurkuazInstaller.Bootstrapper" in ROLE_FILES["turkuaz_bootstrapper"],
           "first-party bootstrapper identity invalid")
    ensure(metadata.get("signed_production_binary") is True,
           "unsigned Turkuaz bootstrapper is not a distributable primary")
    ensure(metadata.get("signed_cms_manifest") is True,
           "detached CMS not verified")
    ensure(metadata.get("external_cert_pin_verified") is True,
           "external trust pin not verified")
    return {
        "schema": "levelupgt.dual-installer-gate.v1",
        "source_sha": source_sha,
        "turkuaz_source_sha": PINNED_TURKUAZ_SOURCE_SHA,
        "version": version,
        "primary": actual["turkuaz_bootstrapper"],
        "fallback_private": {"sha256": actual["nsis_backup"]["sha256"]},
        "verified_files": actual,
        "primary_download_only": True,
        "gate": "PASS",
        "note": "Cryptographic and install E2E evidence requires independent Windows QA.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
        report = verify(args.bundle, evidence, args.source_sha, args.version)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("BURAK-INS-001 PASS; Turkuaz primary is the only user-facing setup")
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("BURAK-INS-001 FAIL CLOSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
