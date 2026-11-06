#!/usr/bin/env python3
# Dosya Yolu: tools/tests/test_ragnar_legacy_theme.py
# Amac: Validate opt-in Ragnar Beam UI theme and prevent patch-channel config bleed
# Modul - Python unittest, offline source contract
# Version: 0.1.0-candidate
# Aciklama: No binaries, network, release, client files or game changes.
# Bagimli Oldugu Katman: beam-ui/public/index.html | beam-ui/public/assets/ragnar-legacy.css
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "beam-ui/public/index.html").read_text("utf-8")
CSS = (ROOT / "beam-ui/public/assets/ragnar-legacy.css").read_text("utf-8")
GUIDE = (ROOT / "themes/ragnar-legacy/README.md").read_text("utf-8")


class RagnarThemeContractTests(unittest.TestCase):
    def test_new_theme_does_not_replace_default_style(self):
        self.assertIn('id="ragnar-legacy-theme-css"', HTML)
        self.assertIn('href="assets/ragnar-legacy.css" disabled>', HTML)
        self.assertIn("sheet.disabled = !legacy;", HTML)
        self.assertIn("choice === 'ragnar-legacy'", HTML)
        self.assertIn("(config?.ui?.theme || 'default')", HTML)

    def test_theme_is_config_driven_not_injected_from_public_url_in_tauri(self):
        self.assertIn("const previewTheme = !isTauri &&", HTML)
        self.assertIn("new URLSearchParams(window.location.search).get('theme') === 'ragnar-legacy'", HTML)
        self.assertIn("applyConfiguredTheme(config);", HTML)
        self.assertIn("classList.toggle('theme-ragnar-legacy', legacy)", HTML)
        self.assertIn("classList.toggle('theme-preview-only', isThemePreview)", HTML)

    def test_preview_has_no_patch_controls_and_no_news_api(self):
        self.assertIn("'#play-button, .btn-action-small, #register-btn-main'", HTML)
        self.assertIn("button.disabled = true", HTML)
        self.assertIn("Preview Only", HTML)
        self.assertIn("if (previewTheme) return [", HTML)
        self.assertIn("url: 'about:blank'", HTML)
        self.assertIn("'Overlook Dungeon - legacy announcement'", HTML)

    def test_css_scoped_and_contains_historical_palette(self):
        self.assertIn("body.theme-ragnar-legacy {", CSS)
        self.assertIn(".news-item", CSS)
        self.assertIn(".btn-play-now", CSS)
        self.assertIn(".progress-bar", CSS)
        self.assertIn("#f1b9c4", CSS.lower())
        self.assertIn("#ff7d00", CSS.lower())
        self.assertNotRegex(CSS, r"(?m)^:root\s*\{")
        # Do not allow universal changes to default Beam appearance.
        self.assertNotRegex(CSS, r"(?m)^\s*body\s*\{")
        self.assertEqual(CSS.count("{"), CSS.count("}"))

    def test_documented_legacy_sources_and_correct_binary_boundaries(self):
        for evidence in (
            "patcher/web/legacy/index.html",
            "patcher/web/legacy/style.css",
            "2015/beam/config.yml",
            "custom-login-theme.thor",
            "not Beam frontend images",
            "ragnardata.grf",
            "ready: false",
        ):
            self.assertIn(evidence, GUIDE)
        self.assertNotIn("auto_publish: true", GUIDE)

    def test_theme_css_contains_no_patch_endpoints_or_executable_logic(self):
        for needle in (
            "raw.githubusercontent.com", "2015/data", "patchlist.txt",
            "file_url=", "launch_game", "start_patching", "client_exe_sha256",
        ):
            self.assertNotIn(needle, CSS)
        self.assertEqual(len(re.findall(r'id="ragnar-legacy-theme-css"', HTML)), 1)


if __name__ == "__main__":
    unittest.main()
