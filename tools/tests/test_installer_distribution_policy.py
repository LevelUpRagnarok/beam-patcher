#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_installer_distribution_policy.py
# Amac: BURAK-INS-001 primary ve backup dagitim bypass negatif regresyonlari
# Modul - Python unittest
# Version: 1.0.1-candidate
# Aciklama: Degisen manifest, eksik sidecar, farkli SHA, yanlış rol ve standalone upload reddi
# Bagimli Oldugu Katman: tools/verify_installer_pair.py | tools/check_installer_workflows.py

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from verify_installer_pair import ROLE_FILES, REQUIRED_ACCEPTANCE, verify  # noqa: E402
from check_installer_workflows import policy_errors  # noqa: E402

SHA = "a" * 40
VERSION = "1.0.1"


class InstallerDistributionContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="installer-dual-policy-")
        self.root = Path(self.tmp.name)
        pinned = {}
        for role, rel in ROLE_FILES.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            body = ("test-only-" + role).encode() * 32
            target.write_bytes(body)
            pinned[role] = hashlib.sha256(body).hexdigest()
        self.data = {
            "schema": "levelupgt.dual-installer-proof.v1",
            "source_sha": SHA, "turkuaz_source_sha": "b" * 40,
            "version": VERSION, "architecture": "win-x64",
            "product_id": "levelupgt.beampatcher.qa",
            "primary_role": "turkuazinstaller", "fallback_role": "nsis-backup-only",
            "public_fallback": False, "release_ready": True,
            "signed_production_binary": True, "signed_cms_manifest": True,
            "external_cert_pin_verified": True,
            "acceptance": {name: "PASS" for name in REQUIRED_ACCEPTANCE},
            "artifact_sha256": pinned,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self):
        return verify(self.root, self.data, SHA, VERSION)

    def test_pair_passes_structural_fixture_only(self):
        result = self.verify()
        self.assertEqual(result["gate"], "PASS")
        self.assertTrue(result["primary_download_only"])
        self.assertNotIn("path", result["fallback_private"])

    def test_missing_primary_or_nsis_is_rejected(self):
        for role in ("turkuaz_bootstrapper", "nsis_backup", "manifest_detached_signature"):
            target = self.root / ROLE_FILES[role]
            original = target.read_bytes()
            target.unlink()
            with self.assertRaisesRegex(ValueError, "missing"):
                self.verify()
            target.write_bytes(original)

    def test_hash_mismatch_and_version_drift_are_rejected(self):
        (self.root / ROLE_FILES["nsis_backup"]).write_bytes(b"changed" * 100)
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.verify()
        self.assertRaises(ValueError, verify, self.root, self.data, SHA, "1.0.2")
        self.assertRaises(ValueError, verify, self.root, self.data, "f" * 40, VERSION)

    def test_fallback_as_primary_or_public_is_rejected(self):
        self.data["primary_role"] = "nsis"
        with self.assertRaisesRegex(ValueError, "primary"):
            self.verify()
        self.data["primary_role"] = "turkuazinstaller"
        self.data["public_fallback"] = True
        with self.assertRaisesRegex(ValueError, "public"):
            self.verify()

    def test_all_required_native_smoke_results_enforced(self):
        for step in REQUIRED_ACCEPTANCE:
            self.data["acceptance"][step] = "NOT RUN"
            with self.assertRaisesRegex(ValueError, step):
                self.verify()
            self.data["acceptance"][step] = "PASS"

    def test_unsigned_or_untrusted_turkuaz_is_rejected(self):
        for key in ("release_ready", "signed_production_binary", "signed_cms_manifest",
                    "external_cert_pin_verified"):
            self.data[key] = False
            with self.assertRaises(ValueError):
                self.verify()
            self.data[key] = True

    def test_standalone_workflow_upload_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="test-policy-workflows-") as tmp:
            root = Path(tmp)
            for rel in ("installer/windows/BeamPatcher-NSIS-Backup.nsi",
                        "tools/verify_installer_pair.py",
                        "tools/check_installer_workflows.py",
                        "tools/Confirm-TurkuazTrust.ps1",
                        "docs/INSTALLER-STRATEGY-TURKUAZ.md",
                        "docs/WINDOWS-SETUP-PATCH-QA.md"):
                file = root / rel
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("policy stub")
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "dual-installer-policy.yml").write_text(
                "windows-latest\nTurkuazInstaller NSIS\nverify_installer_pair.py\nConfirm-TurkuazTrust.ps1\nactions/upload-artifact@v4"
            )
            standalone = workflows / "windows-setup-patch-qa.yml"
            standalone.write_text("- uses: actions/upload-artifact@v4\n  name: nsis-setup.exe\n")
            self.assertTrue(any("standalone setup upload" in err for err in policy_errors(root)))
            standalone.unlink()
            self.assertFalse(policy_errors(root))


    def test_retired_standalone_setup_guide_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="test-policy-docs-") as tmp:
            root = Path(tmp)
            for rel in ("installer/windows/BeamPatcher-NSIS-Backup.nsi",
                        "tools/verify_installer_pair.py",
                        "tools/check_installer_workflows.py",
                        "tools/Confirm-TurkuazTrust.ps1",
                        "docs/INSTALLER-STRATEGY-TURKUAZ.md",
                        "docs/WINDOWS-SETUP-PATCH-QA.md"):
                file = root / rel
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("policy stub", encoding="utf-8")
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "dual-installer-policy.yml").write_text(
                "windows-latest\nTurkuazInstaller NSIS\nverify_installer_pair.py\n"
                "Confirm-TurkuazTrust.ps1\nactions/upload-artifact@v4",
                encoding="utf-8",
            )
            self.assertFalse(policy_errors(root))
            guide = root / "docs/WINDOWS-SETUP-PATCH-QA.md"
            guide.write_text(
                "Download the short-lived `levelup-beam-windows-setup-qa-<SHA>` artifact",
                encoding="utf-8",
            )
            self.assertTrue(any("retired standalone setup" in err
                                for err in policy_errors(root)))




if __name__ == "__main__":
    unittest.main()
