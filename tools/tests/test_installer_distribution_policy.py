#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_installer_distribution_policy.py
# Amac: TURKUAZ-ONLY-001 Turkuaz primary kontrati, signer ve NSIS kaldirma regresyonu
# Modul - Python unittest / CI policy
# Version: 2.0.0-candidate
# Aciklama: Sentetik negatif kabul kaniti; production imza/E2E yerine gecmez
# Bagimli Oldugu Katman: tools/verify_installer_primary.py | tools/check_installer_workflows.py

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from verify_installer_primary import (  # noqa: E402
    PINNED_TURKUAZ_SOURCE_SHA, ROLE_FILES, REQUIRED_ACCEPTANCE, verify,
)
from check_installer_workflows import (  # noqa: E402
    policy_errors, REQUIRED, RETIRED, RELEASE_WORKFLOW,
)

SOURCE_SHA = "a" * 40
VERSION = "1.0.1"


class TurkuazOnlyDistributionContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="turkuaz-primary-fixture-")
        self.root = Path(self.tmp.name)
        files = {}
        for role, relative in ROLE_FILES.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            contents = ("QA-ONLY-" + role).encode() * 64
            target.write_bytes(contents)
            files[role] = hashlib.sha256(contents).hexdigest()
        self.data = {
            "schema": "levelupgt.turkuaz-primary-proof.v1",
            "source_sha": SOURCE_SHA,
            "turkuaz_source_sha": PINNED_TURKUAZ_SOURCE_SHA,
            "version": VERSION,
            "architecture": "win-x64",
            "product_id": "levelupgt.beampatcher.qa",
            "primary_role": "turkuazinstaller",
            "release_ready": True,
            "signed_production_binary": True,
            "signed_cms_manifest": True,
            "external_cert_pin_verified": True,
            "acceptance": {name: "PASS" for name in REQUIRED_ACCEPTANCE},
            "artifact_sha256": files,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self):
        return verify(self.root, self.data, SOURCE_SHA, VERSION)

    def test_primary_fixture_passes_structural_only(self):
        report = self.verify()
        self.assertEqual(report["gate"], "PASS")
        self.assertTrue(report["primary_download_only"])
        self.assertNotIn("fallback_private", report)
        self.assertEqual(set(report["verified_files"]), set(ROLE_FILES))
        self.assertNotIn("nsis_backup", ROLE_FILES)

    def test_upstream_revision_is_pinned_to_checkout(self):
        workflow = (ROOT / ".github/workflows/turkuaz-primary-policy.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"ref: {PINNED_TURKUAZ_SOURCE_SHA}", workflow)
        correct = self.data["turkuaz_source_sha"]
        for value in ("b" * 40, "", None, correct[:-1] + "0"):
            with self.subTest(value=value):
                self.data["turkuaz_source_sha"] = value
                with self.assertRaisesRegex(ValueError, "upstream Turkuaz source commit"):
                    self.verify()
        self.data["turkuaz_source_sha"] = correct
        self.assertEqual(self.verify()["turkuaz_source_sha"], correct)

    def test_missing_primary_sidecar_or_hash_mismatch_rejected(self):
        for role in ("turkuaz_bootstrapper", "manifest_detached_signature", "external_trust_policy"):
            with self.subTest(role=role):
                target = self.root / ROLE_FILES[role]
                body = target.read_bytes()
                target.unlink()
                with self.assertRaisesRegex(ValueError, "missing"):
                    self.verify()
                target.write_bytes(body)
        target = self.root / ROLE_FILES["turkuaz_bootstrapper"]
        target.write_bytes(b"tampered-qa-fixture" * 60)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.verify()

    def test_legacy_fallback_metadata_and_extra_artifact_are_rejected(self):
        self.data["fallback_role"] = "nsis-backup-only"
        with self.assertRaisesRegex(ValueError, "fallback"):
            self.verify()
        self.data.pop("fallback_role")
        self.data["public_fallback"] = False
        with self.assertRaisesRegex(ValueError, "fallback"):
            self.verify()
        self.data.pop("public_fallback")
        self.data["artifact_sha256"]["nsis_backup"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "artifact checksums"):
            self.verify()

    def test_version_source_role_and_readiness_rejected(self):
        with self.assertRaises(ValueError):
            verify(self.root, self.data, SOURCE_SHA, "1.0.2")
        with self.assertRaises(ValueError):
            verify(self.root, self.data, "f" * 40, VERSION)
        self.data["primary_role"] = "another-installer"
        with self.assertRaisesRegex(ValueError, "primary"):
            self.verify()
        self.data["primary_role"] = "turkuazinstaller"
        for field in ("release_ready", "signed_production_binary",
                      "signed_cms_manifest", "external_cert_pin_verified"):
            with self.subTest(field=field):
                self.data[field] = False
                with self.assertRaises(ValueError):
                    self.verify()
                self.data[field] = True

    def test_every_native_acceptance_stage_is_required(self):
        for name in REQUIRED_ACCEPTANCE:
            with self.subTest(name=name):
                self.data["acceptance"][name] = "NOT_RUN"
                with self.assertRaisesRegex(ValueError, name):
                    self.verify()
                self.data["acceptance"][name] = "PASS"

    def _policy_fixture(self, root):
        for relative in REQUIRED:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("policy fixture", encoding="utf-8")
        main = root / ".github/workflows" / RELEASE_WORKFLOW
        main.write_text(
            "TurkuazInstaller\nverify_installer_primary.py\nwindows-latest\n"
            "actions/upload-artifact@v4\nenvironment: windows-installer-signing\n"
            "build-primary-and-gate:\nif: github.event_name == 'workflow_dispatch'\n"
            "Confirm-TurkuazTrust.ps1\nTest-BeamTrustNegative.ps1\n",
            encoding="utf-8",
        )
        return main

    def test_policy_rejects_nsis_files_and_active_workflow_builds(self):
        with tempfile.TemporaryDirectory(prefix="turkuaz-policy-") as name:
            root = Path(name)
            self._policy_fixture(root)
            self.assertFalse(policy_errors(root))
            retired = root / RETIRED[0]
            retired.parent.mkdir(parents=True, exist_ok=True)
            retired.write_text("File installer.exe", encoding="utf-8")
            self.assertTrue(any("retired installer" in s for s in policy_errors(root)))
            retired.unlink()
            extra = root / "installer/windows/stray-backup.nsi"
            extra.write_text("script", encoding="utf-8")
            self.assertTrue(any("NSIS source" in s for s in policy_errors(root)))
            extra.unlink()
            workflow = root / ".github/workflows/windows-setup-patch-qa.yml"
            workflow.write_text("choco install nsis --yes", encoding="utf-8")
            self.assertTrue(any("deprecated NSIS" in s for s in policy_errors(root)))

    def test_standalone_setup_upload_is_denied(self):
        with tempfile.TemporaryDirectory(prefix="turkuaz-upload-") as name:
            root = Path(name)
            self._policy_fixture(root)
            rogue = root / ".github/workflows/rogue.yml"
            rogue.write_text(
                "- uses: actions/upload-artifact@v4\nname: custom-nsis-setup.exe\n",
                encoding="utf-8",
            )
            self.assertTrue(any("installer artifact bypasses" in s
                                for s in policy_errors(root)))

    def test_real_workflows_have_no_nsis_compiler_or_installer_artifact(self):
        self.assertFalse(policy_errors(ROOT), "repository must satisfy primary-only policy")
        workflow = (ROOT / ".github/workflows/rust-installer-beam-compat.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("build-self-extracting-setup", (
            ROOT / "tools/Test-BeamRustEphemeralLifecycle.ps1"
        ).read_text(encoding="utf-8"))
        self.assertNotIn("choco install nsis", workflow.lower())
        self.assertNotIn("build-distribution-pair", workflow.lower())
        self.assertNotIn("actions/upload-artifact", workflow)

    def test_protected_cms_negative_smoke_stays_required(self):
        workflow = (ROOT / ".github/workflows/turkuaz-primary-policy.yml").read_text(
            encoding="utf-8"
        )
        signer = (ROOT / "tools/Confirm-TurkuazTrust.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("trust-negative-fixtures:", workflow)
        self.assertIn("needs: [policy-contract, trust-negative-fixtures]", workflow)
        self.assertIn("Test-BeamTrustNegative.ps1", workflow)
        self.assertIn("$Cms.CheckSignature($false)", signer)
        self.assertIn("outside its validity period", signer)
        self.assertIn("Assert-BeamManifestSetupBinding.ps1", signer)


if __name__ == "__main__":
    unittest.main()
