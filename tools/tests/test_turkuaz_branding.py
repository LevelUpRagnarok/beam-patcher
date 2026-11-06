#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_turkuaz_branding.py
# Amac: Turkuaz Ragnarok Online gorunur marka ve QA uyumluluk kontrati
# Modul - Python unittest
# Version: 2.0.0-candidate
# Aciklama: Eski tema ID'lerini, izole QA profilini ve tek Rust installer politikasini korur
# Bagimli Oldugu Katman: beam-ui/public/index.html | beam-core/src/config.rs | installer/windows

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "beam-ui/public/index.html").read_text(encoding="utf-8")
TAURI = json.loads((ROOT / "beam-ui/tauri.conf.json").read_text(encoding="utf-8"))
QA = (ROOT / "installer/windows/config.qa.yml").read_text(encoding="utf-8")
CONFIG = (ROOT / "beam-core/src/config.rs").read_text(encoding="utf-8")
GUARD = (ROOT / "beam-core/src/qa_guard.rs").read_text(encoding="utf-8")


class TurkuazBrandingTests(unittest.TestCase):
    def test_launcher_identity_is_not_goatmmo_or_levelup(self):
        self.assertIn("<title>Turkuaz Ragnarok Online</title>", HTML)
        self.assertIn('id="logo-text">TURKUAZ RAGNAROK ONLINE</span>', HTML)
        self.assertIn('aria-label="Turkuaz Ragnarok Online"', HTML)
        self.assertIn("TURKUAZ · RAGNAROK ONLINE", HTML)
        for old in ("GOATMMO", "LEVELUP GAMES", "goatmmo.com",
                    "Ragnar Ragnarok Online", "LevelUp Games"):
            self.assertNotIn(old, HTML)
        self.assertEqual(TAURI["package"]["productName"], "Turkuaz Ragnarok Online")
        self.assertIn("Turkuaz Ragnarok Online", TAURI["tauri"]["windows"][0]["title"])
        # Keep platform identity stable until a separate signed migration.
        self.assertEqual(TAURI["tauri"]["bundle"]["identifier"], "com.beampatcher.app")

    def test_four_display_names_keep_original_persistent_theme_keys(self):
        names = {
            "default": "Turkuaz Standart",
            "ragnar-legacy": "Turkuaz Nostalji",
            "ragnar-classic": "Turkuaz Klasik",
            "levelup-modern": "Turkuaz Modern",
        }
        for key, name in names.items():
            self.assertIn(f'data-launcher-theme="{key}"', HTML)
            self.assertIn(f'<option value="{key}">{name}</option>', HTML)
            self.assertIn(f'class="theme-choice-name">{name}</span>', HTML)
        self.assertEqual(HTML.count('data-launcher-theme="'), 4)
        self.assertIn("'beam.launcher.theme.v1'", HTML)
        self.assertIn("'about:blank'", HTML)

    def test_existing_and_new_qa_names_remain_isolated(self):
        self.assertIn('name: "Turkuaz Ragnarok Online QA"', QA)
        self.assertIn('server_name: "TURKUAZ RAGNAROK ONLINE (QA)"', QA)
        self.assertIn("qa_only: true", QA)
        self.assertIn('client_exe: "NO_CLIENT_CONFIGURED.exe"', QA)
        self.assertIn('target_grf: "levelup-qa.grf"', QA)
        self.assertIn("enabled: false", QA)
        self.assertIn('QA_APP_NAME: &str = "Turkuaz Ragnarok Online QA"', GUARD)
        self.assertIn('LEGACY_QA_APP_NAME: &str = "LevelUp Games Beam QA"', GUARD)
        self.assertIn("is_qa_app_name(&config.app.name)", CONFIG)
        self.assertIn("is_qa_app_name(&self.app.name)", CONFIG)
        self.assertIn("config.patcher.qa_only = true;", CONFIG)

    def test_rust_is_the_only_active_installer_policy(self):
        retired = (
            "installer/windows/BeamPatcher-NSIS-Backup.nsi",
            "installer/windows/BeamPatcher-QA.iss",
            "tools/verify_installer_pair.py",
            "tools/Assert-BeamManifestSetupBinding.ps1",
            ".github/workflows/dual-installer-policy.yml",
        )
        for relative in retired:
            with self.subTest(path=relative):
                self.assertFalse((ROOT / relative).exists())

        installer = ROOT / "installer"
        self.assertFalse(any(installer.rglob("*.nsi")))
        self.assertFalse(any(installer.rglob("*.iss")))

        primary_workflow = ROOT / ".github/workflows/turkuaz-primary-policy.yml"
        candidate_workflow = ROOT / ".github/workflows/rust-installer-beam-compat.yml"
        primary_verifier = ROOT / "tools/verify_installer_primary.py"
        workflow_policy = ROOT / "tools/check_installer_workflows.py"
        for required in (primary_workflow, candidate_workflow, primary_verifier, workflow_policy):
            with self.subTest(path=required.relative_to(ROOT)):
                self.assertTrue(required.is_file())

        policy = workflow_policy.read_text(encoding="utf-8")
        release_gate = primary_workflow.read_text(encoding="utf-8")
        self.assertIn("TurkuazInstaller", policy)
        self.assertIn("tools/verify_installer_primary.py", policy)
        self.assertIn("build-primary-and-gate:", release_gate)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", release_gate)
        self.assertNotIn("actions/setup-dotnet", release_gate)
        self.assertNotIn("dotnet publish", release_gate)


if __name__ == "__main__":
    unittest.main()
