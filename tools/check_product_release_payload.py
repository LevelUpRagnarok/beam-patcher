#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/check_product_release_payload.py
# Amac: QA-only Beam paketinin production TurkuazSetup icine girmesini engeller
# Modul - Python / Offline product release preflight
# Version: 1.0.0-candidate
# Aciklama: Rust tzpkg kimlik, executable byte ve JSON-as-YAML uretim profili kontrolu
# Bagimli Oldugu Katman: tools/verify_installer_primary.py | tools/tests/test_release_payload_gate.py

"""Fail-closed structural *preflight*, not a production signature or E2E approval.

The production config is deliberately encoded as strict JSON in config.yml
(JSON is valid YAML), so duplicate-key and ambiguous YAML bypasses fail closed.
This tool never installs files, launches a client or contacts patch endpoints.
"""

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit
import zipfile

META = "turkuaz-package.json"
EXE = "payload/beam-patcher.exe"
CONFIG = "payload/config.yml"
MAX_CONFIG = 256 * 1024
MAX_EXE = 1024 * 1024 * 1024
MAX_ENTRIES = 4096


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("BEAM_PRODUCT_RELEASE_BLOCKED: " + message)


def strict_json(raw: bytes) -> dict:
    def no_duplicates(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "duplicate JSON key: " + str(key))
            obj[key] = value
        return obj

    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=no_duplicates)
    require(type(value) is dict, "expected JSON object")
    return value


def non_test_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", value)) and not any(
        part in {"qa", "test", "sample", "demo"}
        for part in re.split(r"[._-]", value.casefold())
    )


def safe_basename(value) -> bool:
    # Match beam-core/src/patch_guard.rs::safe_basename on exact bytes.
    return (isinstance(value, str) and 0 < len(value) < 180 and
            value not in (".", "..") and ".." not in value and
            not value.startswith(".") and
            re.fullmatch(r"[A-Za-z0-9._-]+", value) is not None)


def safe_leaf(value, extension: str) -> bool:
    return safe_basename(value) and value.lower().endswith(extension)


def public_https(value) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        uri = urlsplit(value)
        host = uri.hostname
        if (uri.scheme != "https" or not host or not uri.netloc or
                uri.username or uri.password or not uri.path.startswith("/") or
                uri.fragment or host in {"localhost"}):
            return False
        if host.endswith((".invalid", ".test", ".example", ".localhost", ".local")):
            return False
        if "yourserver" in host.casefold() or "example" in host.casefold():
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return "." in host and all(part for part in host.split("."))
        return False
    except ValueError:
        return False


def nonplaceholder(value) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= 96 and
            value.strip() == value and
            not re.search(r"(?i)(?:^|[\\s_-])(qa|test|sample|demo)(?:$|[\\s_-])", value) and
            "placeholder" not in value.casefold())


def validate_config(config: dict, version: str) -> None:
    app = config.get("app")
    patcher = config.get("patcher")
    require(isinstance(app, dict) and isinstance(patcher, dict),
            "missing app or patcher profile")
    require(app.get("version") == version, "config and package version mismatch")
    require(nonplaceholder(app.get("name")), "QA/test application name")
    require(safe_leaf(app.get("client_exe"), ".exe") and
            app["client_exe"].lower() != "no_client_configured.exe",
            "unconfigured or unsafe game client EXE")
    require(app.get("game_directory") is None,
            "product config must not embed an install machine path")

    require(patcher.get("qa_only") is False, "QA-only profile is not a product")
    require(patcher.get("verify_checksums") is True, "checksum verification is required")
    require(safe_leaf(patcher.get("target_grf"), ".grf") and
            "qa" not in patcher["target_grf"].casefold(),
            "QA-only or unsafe GRF target")
    require(public_https(patcher.get("patch_list_url")),
            "product patch list URL must be public HTTPS")
    mirrors = patcher.get("mirrors")
    require(isinstance(mirrors, list) and bool(mirrors) and
            all(isinstance(m, dict) and public_https(m.get("url")) for m in mirrors),
            "production patch mirrors must be public HTTPS")

    guard = patcher.get("compatibility_guard")
    require(isinstance(guard, dict), "verified client compatibility_guard required")
    require(safe_basename(guard.get("profile_id")) and
            nonplaceholder(guard.get("profile_id")),
            "missing or unsafe product guard profile_id")
    pair = (guard.get("region"), guard.get("channel"))
    require(pair in {("levelupgt", "custom"), ("kro", "main"),
                     ("kro", "sakray"), ("iro", "main"), ("iro", "sakray")},
            "unsupported product guard region/channel pair")
    digest = guard.get("client_exe_sha256")
    require(isinstance(digest, str) and bool(re.fullmatch(r"[a-fA-F0-9]{64}", digest))
            and digest.lower() not in ("0" * 64, "f" * 64),
            "verified client SHA256 identity required")
    require(safe_leaf(guard.get("manifest_file"), ".json"),
            "unsafe or missing client manifest filename")

    updater = config.get("updater")
    if updater is not None:
        require(isinstance(updater, dict), "invalid updater config")
        if updater.get("enabled") is True:
            require(public_https(updater.get("check_url")) and
                    public_https(updater.get("update_url")),
                    "enabled product updater requires public HTTPS endpoints")


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_digest(archive: zipfile.ZipFile, member: zipfile.ZipInfo) -> str:
    h = hashlib.sha256()
    with archive.open(member) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(package: Path, expected_exe: Path, package_id: str, version: str) -> dict:
    require(non_test_id(package_id), "production package ID cannot be QA/test")
    require(bool(re.fullmatch(r"0|[1-9][0-9]*", version.split(".")[0])) and
            bool(re.fullmatch(r"[0-9]+\\.[0-9]+\\.[0-9]+", version)),
            "invalid product semantic version")
    require(package.is_file() and not package.is_symlink(), "missing Rust tzpkg")
    require(expected_exe.is_file() and not expected_exe.is_symlink(),
            "missing actual source-built Beam executable")
    require(zipfile.is_zipfile(package), "invalid Rust tzpkg archive")

    with zipfile.ZipFile(package) as archive:
        entries = archive.infolist()
        require(0 < len(entries) <= MAX_ENTRIES, "oversized Rust archive inventory")
        names = set()
        items = {}
        for item in entries:
            name = item.filename
            path = PurePosixPath(name)
            require(name and not name.startswith("/") and "\\" not in name and
                    all(part not in (".", "..") for part in path.parts) and
                    not ((item.external_attr >> 16) & 0o170000) == 0o120000,
                    "unsafe Rust archive entry")
            require(name.casefold() not in names, "duplicate or colliding Rust entry")
            names.add(name.casefold())
            require(name == META or name.startswith("payload/"),
                    "unexpected Rust archive root")
            require("readme-qa" not in name.casefold(),
                    "QA guidance included in product payload")
            items[name] = item

        for required in (META, EXE, CONFIG):
            require(required in items and not items[required].is_dir(),
                    "required product file missing: " + required)
        require(items[META].file_size <= 65536, "Rust metadata exceeds size limit")
        require(0 < items[CONFIG].file_size <= MAX_CONFIG,
                "product config exceeds size limit")
        require(1024 <= items[EXE].file_size <= MAX_EXE,
                "Beam executable exceeds size limits")

        metadata = strict_json(archive.read(META))
        require(set(metadata) == {"formatVersion", "packageId", "version", "entryPoint"} and
                metadata["formatVersion"] == 2 and
                metadata["packageId"] == package_id and metadata["version"] == version and
                metadata["entryPoint"] == "beam-patcher.exe",
                "package metadata does not match approved product identity")

        config = strict_json(archive.read(CONFIG))
        validate_config(config, version)
        expected_sha = file_digest(expected_exe)
        require(archive_digest(archive, items[EXE]) == expected_sha,
                "packaged Beam EXE differs from checked-out source build")

    return {
        "status": "PRODUCT_PAYLOAD_PREFLIGHT_ONLY",
        "package_id": package_id,
        "version": version,
        "beam_exe_sha256": expected_sha,
        "tzpkg_sha256": file_digest(package),
        "release_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--expected-exe", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        report = audit(args.package, args.expected_exe, args.package_id, args.version)
        print("BEAM_PRODUCT_PROFILE_PREFLIGHT_PASS_NOT_RELEASE_APPROVAL")
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            json.JSONDecodeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        print("BEAM_PRODUCT_PROFILE_FAIL_CLOSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
