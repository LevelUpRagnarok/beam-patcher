#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_release_payload_gate.py
# Amac: Production Rust paketinin QA gibi yayinlanmasini negatif fixture ile engeller
# Modul - Python unittest / Release profile
# Version: 1.0.0-candidate
# Aciklama: Sadece sentetik ZIP ve JSON testidir, gercek imza ve native kurulum degildir
# Bagimli Oldugu Katman: tools/check_product_release_payload.py

import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_product_release_payload import audit  # noqa: E402

VERSION = "1.0.1"
PRODUCT_ID = "levelupgt.beampatcher"


def profile():
    return {
        "app": {
            "name": "LevelUp Ragnarok Online",
            "version": VERSION,
            "client_exe": "Ragnarok.exe",
            "game_directory": None,
        },
        "patcher": {
            "qa_only": False,
            "verify_checksums": True,
            "target_grf": "data.grf",
            "patch_list_url": "https://patch.release-fixture.net/patchlist.txt",
            "mirrors": [{"name": "primary", "url": "https://patch.release-fixture.net/"}],
            "compatibility_guard": {
                "profile_id": "region-one",
                "region": "levelupgt",
                "channel": "custom",
                "client_exe_sha256": "1" * 64,
                "manifest_file": "client-manifest.json",
            },
        },
        "updater": {"enabled": False},
    }


class ReleaseProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="beam-product-profile-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = self.root / "beam-patcher.exe"
        self.binary.write_bytes(b"MZ" + b"beam-release-fixture" * 80)
        self.package = self.root / "Beam.tzpkg"
        self.config = profile()
        self.metadata = {
            "formatVersion": 2,
            "packageId": PRODUCT_ID,
            "version": VERSION,
            "entryPoint": "beam-patcher.exe",
        }

    def pack(self, *, raw_config=None, extra=None, metadata=None):
        payload = (raw_config if raw_config is not None else
                   json.dumps(self.config).encode("utf-8"))
        meta = json.dumps(self.metadata if metadata is None else metadata).encode("utf-8")
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("turkuaz-package.json", meta)
            archive.writestr("payload/config.yml", payload)
            archive.writestr("payload/beam-patcher.exe", self.binary.read_bytes())
            for name, raw in (extra or {}).items():
                archive.writestr(name, raw)

    def check(self, package_id=PRODUCT_ID, version=VERSION):
        return audit(self.package, self.binary, package_id, version)

    def test_product_profile_passes_structurally_not_as_signed_release(self):
        self.pack()
        out = self.check()
        self.assertEqual(out["status"], "PRODUCT_PAYLOAD_PREFLIGHT_ONLY")
        self.assertFalse(out["release_ready"])
        self.assertEqual(out["package_id"], PRODUCT_ID)
        self.assertEqual(len(out["tzpkg_sha256"]), 64)

    def test_qa_product_identity_always_rejected(self):
        self.pack(metadata={**self.metadata, "packageId": PRODUCT_ID + ".qa"})
        with self.assertRaisesRegex(ValueError, "cannot be QA"):
            self.check(package_id=PRODUCT_ID + ".qa")

    def test_qa_only_true_or_missing_is_rejected(self):
        for bad in (True, None, 0, "false"):
            with self.subTest(bad=bad):
                self.config["patcher"]["qa_only"] = bad
                self.pack()
                with self.assertRaisesRegex(ValueError, "QA-only"):
                    self.check()
        self.config["patcher"].pop("qa_only", None)
        self.pack()
        with self.assertRaisesRegex(ValueError, "QA-only"):
            self.check()

    def test_unverified_client_guard_rejected(self):
        for key in ("profile_id", "region", "channel", "client_exe_sha256",
                    "manifest_file"):
            with self.subTest(missing=key):
                self.config = profile()
                del self.config["patcher"]["compatibility_guard"][key]
                self.pack()
                with self.assertRaises(ValueError):
                    self.check()
        self.config = profile()
        self.config["patcher"]["compatibility_guard"] = None
        self.pack()
        with self.assertRaisesRegex(ValueError, "compatibility_guard"):
            self.check()

    def test_qa_client_or_target_rejected(self):
        for key, value in (("client_exe", "NO_CLIENT_CONFIGURED.exe"),
                           ("client_exe", "../Ragnarok.exe")):
            with self.subTest(key=key, value=value):
                self.config = profile()
                self.config["app"][key] = value
                self.pack()
                with self.assertRaises(ValueError):
                    self.check()
        self.config = profile()
        self.config["patcher"]["target_grf"] = "levelup-qa.grf"
        self.pack()
        with self.assertRaisesRegex(ValueError, "GRF target"):
            self.check()

    def test_insecure_or_placeholder_urls_rejected(self):
        for url in ("http://patch.example.org/patchlist.txt",
                    "https://patch.example.com/patchlist.txt",
                    "https://127.0.0.1/patchlist.txt",
                    "https://patch.yourserver.com/patchlist.txt"):
            with self.subTest(url=url):
                self.config = profile()
                self.config["patcher"]["patch_list_url"] = url
                self.pack()
                with self.assertRaisesRegex(ValueError, "public HTTPS"):
                    self.check()

    def test_duplicate_json_keys_or_ambiguous_yaml_rejected(self):
        self.pack(raw_config=b'{"app": {}, "app": {}, "patcher": {}}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.check()
        self.pack(raw_config=b"patcher:\\n  qa_only: false\\n".replace(b"\\n", b"\n"))
        with self.assertRaises(ValueError):
            self.check()

    def test_version_or_executable_mismatch_rejected(self):
        self.pack()
        self.binary.write_bytes(b"MZ" + b"changed-source" * 80)
        with self.assertRaisesRegex(ValueError, "EXE differs"):
            self.check()
        self.binary.write_bytes(b"MZ" + b"beam-release-fixture" * 80)
        self.config["app"]["version"] = "8.8.8"
        self.pack()
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            self.check()

    def test_qa_readme_or_archive_traversal_rejected(self):
        self.pack(extra={"payload/README-QA.txt": b"QA fixture"})
        with self.assertRaisesRegex(ValueError, "QA guidance"):
            self.check()
        self.pack(extra={"payload/../danger.txt": b"bad"})
        with self.assertRaisesRegex(ValueError, "unsafe Rust archive entry"):
            self.check()

    def test_product_manifest_metadata_identity_rejected(self):
        self.pack(metadata={**self.metadata, "version": "9.9.9"})
        with self.assertRaisesRegex(ValueError, "package metadata"):
            self.check()


if __name__ == "__main__":
    unittest.main()
