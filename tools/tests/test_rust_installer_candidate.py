#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_rust_installer_candidate.py
# Amac: Rust TurkuazInstaller onizleme ZIP/manifest sozlesmesinde fail-closed testleri
# Modul - Python unittest
# Version: 1.3.0-candidate
# Aciklama: Sentetik .tzpkg pozitif/negatif fixture; imza veya gercek Windows install testi degil
# Bagimli Oldugu Katman: tools/check_rust_installer_candidate.py

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from check_rust_installer_candidate import audit, PINNED_RUST_SOURCE_SHA  # noqa: E402

PACKAGE_ID = "levelupgt.beampatcher.qa"
VERSION = "1.0.1"


class RustCandidateContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="beam-rust-candidate-")
        self.root = Path(self.temporary.name)
        self.payload = self.root / "payload"
        self.payload.mkdir()
        (self.payload / "beam-patcher.exe").write_bytes(b"SYNTHETIC-NON-EXECUTABLE-QA")
        (self.payload / "config.yml").write_text("patcher:\n  qa_only: true\n", encoding="utf-8")
        (self.payload / "README-QA.txt").write_text("No client or release", encoding="utf-8")
        self.package = self.root / "candidate.tzpkg"
        self.manifest = self.root / "unsigned-manifest.yaml"
        self._write_package()
        self._write_manifest()

    def tearDown(self):
        self.temporary.cleanup()

    def _write_package(self, *, metadata=None, extra_files=None):
        meta = metadata or {
            "formatVersion": 2,
            "packageId": PACKAGE_ID,
            "version": VERSION,
            "entryPoint": "beam-patcher.exe",
        }
        with zipfile.ZipFile(self.package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("turkuaz-package.json", json.dumps(meta))
            for filename in ("beam-patcher.exe", "config.yml", "README-QA.txt"):
                archive.write(self.payload / filename, "payload/" + filename)
            for name, contents in (extra_files or []):
                archive.writestr(name, contents)

    def _write_manifest(self, *, package_id=PACKAGE_ID, version=VERSION,
                        digest=None, size=None, comment=""):
        sha = digest if digest is not None else hashlib.sha256(self.package.read_bytes()).hexdigest()
        byte_count = size if size is not None else self.package.stat().st_size
        self.manifest.write_text(
            "# UNSIGNED QA FIXTURE ONLY\n" + comment +
            "schema_version: 1\n"
            "package:\n"
            f"  id: \"{package_id}\"\n"
            f"  version: \"{version}\"\n"
            "  channel: beta\n"
            "artifact:\n"
            "  uri: \"https://fixtures.invalid/candidate.tzpkg\"\n"
            f"  sha256: \"{sha}\"\n"
            f"  size_bytes: {byte_count}\n",
            encoding="utf-8",
        )

    def verify(self, upstream=PINNED_RUST_SOURCE_SHA):
        return audit(self.package, self.manifest, self.payload, upstream, PACKAGE_ID, VERSION)

    def test_unsigned_structural_candidate_passes(self):
        result = self.verify()
        self.assertEqual(result["status"], "PASS_UNSIGNED_STRUCTURAL_ONLY")
        self.assertFalse(result["release_ready"])
        self.assertEqual(result["verified_payload_files"], 3)

    def test_different_rust_upstream_commit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "upstream source revision"):
            self.verify("a" * 40)

    def test_manifest_wrong_hash_and_size_are_rejected(self):
        self._write_manifest(digest="f" * 64)
        with self.assertRaisesRegex(ValueError, "draft SHA-256"):
            self.verify()
        self._write_manifest(size=self.package.stat().st_size + 1)
        with self.assertRaisesRegex(ValueError, "draft byte count"):
            self.verify()

    def test_manifest_identity_and_duplicate_section_are_rejected(self):
        self._write_manifest(package_id="another.product")
        with self.assertRaisesRegex(ValueError, "manifest package identity"):
            self.verify()
        self._write_manifest()
        with self.manifest.open("a", encoding="utf-8") as out:
            out.write("\nartifact:\n  sha256: 'f'\n")
        with self.assertRaisesRegex(ValueError, "repeated manifest section"):
            self.verify()

    def test_archive_metadata_identity_and_version_are_rejected(self):
        self._write_package(metadata={
            "formatVersion": 1, "packageId": PACKAGE_ID, "version": VERSION,
            "entryPoint": "beam-patcher.exe",
        })
        self._write_manifest()
        with self.assertRaisesRegex(ValueError, "archive version/package/entrypoint"):
            self.verify()

    def test_archive_path_escape_and_extra_root_are_rejected(self):
        for name in ("payload/../attack.txt", "unapproved.txt"):
            with self.subTest(name=name):
                self._write_package(extra_files=[(name, b"UNTRUSTED")])
                self._write_manifest()
                with self.assertRaisesRegex(ValueError, "unsafe archive|unknown archive"):
                    self.verify()

    def test_archive_duplicate_and_case_collision_are_rejected(self):
        self._write_package(extra_files=[("payload/CONFIG.yml", b"bad")])
        self._write_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate archive entry"):
            self.verify()

    def test_archive_tampering_and_payload_mismatch_are_rejected(self):
        self._write_package(extra_files=[("payload/rogue.txt", b"extra")])
        self._write_manifest()
        with self.assertRaisesRegex(ValueError, "payload differs"):
            self.verify()
        self._write_package()
        self._write_manifest()
        (self.payload / "config.yml").write_text("patcher:\n  qa_only: false\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "QA-only config"):
            self.verify()

    def test_ephemeral_windows_lifecycle_is_isolated_and_not_published(self):
        workflow = (ROOT / ".github/workflows/rust-installer-beam-compat.yml").read_text(
            encoding="utf-8"
        )
        fixture = (ROOT / "tools/Test-BeamRustEphemeralLifecycle.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Test-BeamRustEphemeralLifecycle.ps1", workflow)
        self.assertIn("BEAM_RUNNER_KIND:", workflow)
        self.assertNotIn("actions/upload-artifact", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertIn("New-SelfSignedCertificate", fixture)
        self.assertIn("GITHUB_ACTIONS", fixture)
        self.assertIn("github-hosted", fixture)
        for operation in ("'install'", "'update'", "'repair'", "'rollback'",
                          "'uninstall'"):
            with self.subTest(operation=operation):
                self.assertIn(operation, fixture)
        self.assertIn("Reject CMS tamper", fixture)
        self.assertIn("Reject tampered managed file", fixture)
        self.assertIn("user-owned.txt", fixture)
        self.assertIn("Cert:\\CurrentUser\\My", fixture)
        self.assertIn("finally {", fixture)
        self.assertIn("PASS_NOT_PRODUCTION", fixture)
        self.assertNotIn("choco install nsis", workflow.lower())
        self.assertIn("--features setup-gui", workflow)
        self.assertIn("-GuiStubPath $stub", workflow)
        self.assertIn("Assert-TurkuazPrimary", fixture)
        self.assertIn("build-self-extracting-setup", fixture)
        self.assertIn("TurkuazSetup.exe", fixture)
        self.assertNotIn("build-distribution-pair", fixture)
        self.assertNotIn("makensis", workflow.lower())
        self.assertNotIn("TurkuazInstallerBackup.exe", fixture)
        self.assertIn("Sign-And-CheckTestExecutable", fixture)
        self.assertIn("Get-AuthenticodeSignature", fixture)
        self.assertIn("Reject mismatched Turkuaz publisher pin", fixture)
        self.assertIn("install-self --package-id", fixture)
        self.assertIn("TURKUAZ_PRIMARY_PASS_NO_UPLOAD", fixture)


    def test_missing_payload_entrypoint_is_rejected(self):
        (self.payload / "beam-patcher.exe").unlink()
        with self.assertRaisesRegex(ValueError, "Beam QA executable"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
