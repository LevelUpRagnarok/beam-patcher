#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_installer_distribution_policy.py
# Amac: Rust Turkuaz-only signed bundle kaniti, eski installer reddi ve CI negatif testleri
# Modul - Python unittest / Release policy
# Version: 3.0.0-candidate
# Aciklama: Gercek signer yerine sentetik ZIP fixture; CMS/AuthentiCode PRODUCTION iddiasi yok
# Bagimli Oldugu Katman: tools/verify_installer_primary.py | tools/check_installer_workflows.py
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from verify_installer_primary import (  # noqa: E402
    PINNED_TURKUAZ_SOURCE_SHA, ROLE_FILES, REQUIRED_ACCEPTANCE, verify, PACKAGE_ID, SCHEMA,
)
from check_installer_workflows import (  # noqa: E402
    policy_errors, REQUIRED, RETIRED, RELEASE_WORKFLOW, REQUIRED_RUST_GATE_TOKENS,
)

SOURCE_SHA = "a" * 40
VERSION = "1.0.1"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class RustPrimaryOnlyContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rust-turkuaz-primary-")
        self.root = Path(self.temp.name)
        self.primary = self.root / "primary"
        self.primary.mkdir()
        self.package = b"tzpkg-payload-qa" * 100
        self.signature = b"fixture-cms-never-a-real-signature" * 7
        self.manifest = (
            "schema_version: 1\n"
            "package:\n"
            f"  id: {PACKAGE_ID}\n"
            f"  version: {VERSION}\n"
            "artifact:\n"
            f"  sha256: {digest(self.package)}\n"
            f"  size_bytes: {len(self.package)}\n"
        ).encode("utf-8")
        self.theme = b'{"brandName":"CI fixture"}'
        self._write("rust_package", self.package)
        self._write("manifest", self.manifest)
        self._write("manifest_detached_signature", self.signature)
        self._write("external_trust_policy", b"CI structural trust, not real" * 25)
        self._write("turkuaz_setup", b"MZ" + b"test setup only" * 120)
        self._make_bundle()
        self._refresh_evidence()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, role, raw):
        f = self.root / ROLE_FILES[role]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(raw)

    def _refresh_evidence(self):
        hashes = {}
        for name, path in ROLE_FILES.items():
            hashes[name] = digest((self.root / path).read_bytes())
        self.proof = {
            "schema": SCHEMA,
            "source_sha": SOURCE_SHA,
            "turkuaz_source_sha": PINNED_TURKUAZ_SOURCE_SHA,
            "version": VERSION,
            "architecture": "win-x64",
            "product_id": PACKAGE_ID,
            "primary_role": "rust-turkuazinstaller",
            "release_ready": True,
            "signed_production_binary": True,
            "signed_cms_manifest": True,
            "external_cert_pin_verified": True,
            "acceptance": {name: "PASS" for name in REQUIRED_ACCEPTANCE},
            "artifact_sha256": hashes,
        }

    def _make_bundle(self, **overrides):
        entries = {
            "release.yaml": self.manifest,
            "release.p7s": self.signature,
            "application.tzpkg": self.package,
            "setup-theme.json": self.theme,
        }
        metadata = {
            "formatVersion": 2,
            "packageId": PACKAGE_ID,
            "version": VERSION,
            "manifestSizeBytes": len(self.manifest),
            "manifestSha256": digest(self.manifest),
            "signatureSizeBytes": len(self.signature),
            "signatureSha256": digest(self.signature),
            "artifactSizeBytes": len(self.package),
            "artifactSha256": digest(self.package),
            "themeSizeBytes": len(self.theme),
            "themeSha256": digest(self.theme),
        }
        metadata.update(overrides)
        path = self.root / ROLE_FILES["rust_bundle"]
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("bundle.json", json.dumps(metadata))
            for key, value in entries.items():
                archive.writestr(key, value)

    def check(self, expected_package=None):
        return verify(self.root, self.proof, SOURCE_SHA, VERSION, expected_package)

    def test_rust_structural_proof_passes_but_is_not_cryptographic(self):
        report = self.check()
        self.assertEqual(report["gate"], "PASS")
        self.assertEqual(report["primary"]["path"], ROLE_FILES["turkuaz_setup"])
        self.assertEqual(set(report["verified_files"]), set(ROLE_FILES))
        self.assertIn("STRUCTURAL ONLY", report["note"])
        self.assertNotIn("turkuaz_bootstrapper", ROLE_FILES)
        self.assertNotIn("velopack_setup", ROLE_FILES)

    def test_pinned_upstream_is_exact_rust_sha(self):
        self.assertEqual(PINNED_TURKUAZ_SOURCE_SHA,
                         "456a34679661978afc717cc5b08ece11cb0b9a94")
        flow = (ROOT / ".github/workflows/turkuaz-primary-policy.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("ref: " + PINNED_TURKUAZ_SOURCE_SHA, flow)
        self.proof["turkuaz_source_sha"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "pinned Rust Turkuaz source"):
            self.check()

    def test_missing_payload_or_wrong_hash_rejected(self):
        for role in ROLE_FILES:
            with self.subTest(role=role):
                file = self.root / ROLE_FILES[role]
                content = file.read_bytes()
                file.unlink()
                with self.assertRaises(ValueError):
                    self.check()
                file.write_bytes(content)
        target = self.root / ROLE_FILES["rust_package"]
        target.write_bytes(self.package + b"tampered")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.check()

    def test_rust_setup_zip_member_hash_must_match_sidecar(self):
        self._make_bundle(artifactSha256="f" * 64)
        self._refresh_evidence()
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.check()

    def test_rust_bundle_version_and_identity_rejected(self):
        for changed in ({"formatVersion": 1}, {"version": "9.9.9"},
                        {"packageId": "other.pkg"}):
            with self.subTest(changed=changed):
                self._make_bundle(**changed)
                self._refresh_evidence()
                with self.assertRaisesRegex(ValueError, "schema|identity"):
                    self.check()

    def test_manifest_package_digest_or_version_rejected(self):
        for changed in (
            self.manifest.replace(f"  version: {VERSION}".encode(),
                                  b"  version: 9.9.9"),
            self.manifest.replace(digest(self.package).encode(), b"f" * 64),
            self.manifest.replace(f"  size_bytes: {len(self.package)}".encode(),
                                  b"  size_bytes: 1"),
        ):
            with self.subTest(changed=changed[:40]):
                self.manifest = changed
                self._write("manifest", changed)
                self._make_bundle()
                self._refresh_evidence()
                with self.assertRaisesRegex(ValueError, "signed Rust manifest"):
                    self.check()
        # Restore fixture for consistency in the rest of this isolated test.
        self.manifest = (
            f"schema_version: 1\npackage:\n  id: {PACKAGE_ID}\n  version: {VERSION}\n"
            f"artifact:\n  sha256: {digest(self.package)}\n"
            f"  size_bytes: {len(self.package)}\n"
        ).encode()

    def test_required_external_approval_cannot_be_not_run(self):
        for stage in REQUIRED_ACCEPTANCE:
            with self.subTest(stage=stage):
                self.proof["acceptance"][stage] = "NOT_RUN"
                with self.assertRaisesRegex(ValueError, stage):
                    self.check()
                self.proof["acceptance"][stage] = "PASS"

    def test_production_flags_source_and_role_required(self):
        for key in ("release_ready", "signed_production_binary",
                    "signed_cms_manifest", "external_cert_pin_verified"):
            self.proof[key] = False
            with self.assertRaisesRegex(ValueError, "production signature"):
                self.check()
            self.proof[key] = True
        self.proof["primary_role"] = "legacy-installer"
        with self.assertRaisesRegex(ValueError, "Rust Turkuaz primary"):
            self.check()
        self.proof["primary_role"] = "rust-turkuazinstaller"
        with self.assertRaisesRegex(ValueError, "Beam source mismatch"):
            verify(self.root, self.proof, "f" * 40, VERSION)

    def test_stray_installer_or_backup_directory_rejected(self):
        for name in ("backup", "primary/TurkuazInstallerBackup.exe",
                     "primary/TurkuazInstaller.Bootstrapper.exe",
                     "primary/another-setup.exe"):
            with self.subTest(name=name):
                path = self.root / name
                if name == "backup":
                    path.mkdir()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"MZunauthorized-legacy")
                with self.assertRaisesRegex(ValueError, "installer artifact|unexpected"):
                    self.check()
                if path.is_dir():
                    path.rmdir()
                else:
                    path.unlink()

    def test_wrong_source_package_bytes_are_not_publishable(self):
        with tempfile.TemporaryDirectory(prefix="outside-rust-release-root-") as separate:
            alternate = Path(separate) / "expected-source.tzpkg"
            alternate.write_bytes(b"different-build" * 90)
            with self.assertRaisesRegex(ValueError, "freshly built"):
                self.check(alternate)
            alternate.write_bytes(self.package)
            self.assertEqual(self.check(alternate)["gate"], "PASS")

    def _policy_fixture(self, root):
        for relative in REQUIRED:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture", encoding="utf-8")
        flow = root / ".github/workflows" / RELEASE_WORKFLOW
        flow.write_text(
            "TurkuazInstaller\n"
            "tools/verify_installer_primary.py\nwindows-latest\n"
            "actions/upload-artifact@v4\nenvironment: windows-installer-signing\n"
            "build-primary-and-gate:\nif: github.event_name == 'workflow_dispatch'\n"
            "Confirm-TurkuazTrust.ps1\nTest-BeamTrustNegative.ps1\n"
            "ref: 456a34679661978afc717cc5b08ece11cb0b9a94\n"
            "build-package\nbuild-self-extracting-setup\n"
            + "\n".join(REQUIRED_RUST_GATE_TOKENS) + "\n",
            encoding="utf-8",
        )
        return flow

    def test_policy_rejects_old_installer_compilers_and_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._policy_fixture(base)
            self.assertFalse(policy_errors(base))
            legacy = base / RETIRED[0]
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("deprecated setup", encoding="utf-8")
            self.assertTrue(policy_errors(base))
            legacy.unlink()
            for extension in (".iss", ".nsi"):
                old = base / "installer/windows" / ("legacy" + extension)
                old.parent.mkdir(parents=True, exist_ok=True)
                old.write_text("deprecated setup", encoding="utf-8")
                self.assertTrue(policy_errors(base))
                old.unlink()
            rogue = base / ".github/workflows/rogue.yml"
            rogue.write_text("choco install nsis --yes\n", encoding="utf-8")
            self.assertTrue(policy_errors(base))
            rogue.unlink()

    def test_policy_rejects_dotnet_or_velopack_reintroduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            flow = self._policy_fixture(base)
            flow.write_text(flow.read_text(encoding="utf-8") +
                            "actions/setup-dotnet@v4\n", encoding="utf-8")
            self.assertTrue(any("legacy" in issue for issue in policy_errors(base)))
            flow.write_text(flow.read_text(encoding="utf-8").replace(
                "actions/setup-dotnet@v4", "dotnet tool install vpk"
            ), encoding="utf-8")
            self.assertTrue(any("legacy" in issue for issue in policy_errors(base)))

    def test_real_workflows_are_rust_only_and_manual_gate_protected(self):
        self.assertFalse(policy_errors(ROOT))
        flow = (ROOT / ".github/workflows/turkuaz-primary-policy.yml").read_text(
            encoding="utf-8"
        )
        trust = (ROOT / "tools/Confirm-TurkuazTrust.ps1").read_text(encoding="utf-8")
        native = (ROOT / "tools/Test-BeamRustProtectedPrimary.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("environment: windows-installer-signing", flow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", flow)
        self.assertIn("needs: [policy-contract, trust-negative-fixtures]", flow)
        self.assertIn("build-package", flow)
        self.assertIn("verify_installer_primary.py", flow)
        self.assertIn("Test-BeamRustProtectedPrimary.ps1", flow)
        self.assertIn("Get-AuthenticodeSignature", trust)
        self.assertIn("$Cms.CheckSignature($false)", trust)
        self.assertIn("WaitForExit", native)
        self.assertNotIn("actions/setup-dotnet", flow)
        self.assertNotIn("dotnet publish", flow)
        self.assertNotIn("Beam-Velopack-Setup.exe", flow)


if __name__ == "__main__":
    unittest.main()
